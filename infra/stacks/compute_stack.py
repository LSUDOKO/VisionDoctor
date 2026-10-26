"""COOL on Graviton: ASG of COOL-AMI workers (scan + repair + impact) and an MCP server instance.

The core vision workload runs here (award rule): user data activates /opt/cool's Python 3.12
venv, installs VisionDoctor WITHOUT the opencv extra (never shadow COOL's cv2), and starts
systemd units. Workers log ``is_cool`` at start; the MCP server sits behind an internal ALB.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_autoscaling as asg
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as sm
from cdk_nag import NagSuppressions
from constructs import Construct

from stacks.data_stack import DataStack

REPO = "https://github.com/LSUDOKO/VisionDoctor.git"


def user_data(role: str, data: DataStack, secret_arn: str, region: str) -> ec2.UserData:
    ud = ec2.UserData.for_linux()
    env = {
        "VD_BACKEND": "aws", "VD_S3_BUCKET": data.bucket.bucket_name, "VD_SQS_QUEUE_URL": data.queue.queue_url,
        "AWS_DEFAULT_REGION": region, "VD_AWS_REGION": region, "VD_EMF": "1", "VD_MONITOR": "1",
    }
    env_lines = "\n".join(f"{k}={v}" for k, v in env.items())
    exec_start = {
        "worker": "/opt/vd/venv/bin/python -m visiondoctor.cli serve --host 0.0.0.0 --port 8000",
        "mcp": "/opt/vd/venv/bin/python -m visiondoctor.mcp_server.server --transport streamable-http --host 0.0.0.0 --port 8765",
    }[role]
    ud.add_commands(
        "set -euxo pipefail",
        "apt-get update && apt-get install -y git amazon-cloudwatch-agent || true",
        "mkdir -p /opt/vd && cd /opt/vd",
        f"git clone --depth 1 {REPO} src",
        # COOL's interpreter + cv2: venv inherits /opt/cool site-packages; no opencv-python wheel.
        "/opt/cool/venvs/python_3.12/bin/python -m venv --system-site-packages /opt/vd/venv",
        "/opt/vd/venv/bin/pip install -e /opt/vd/src",
        "cd /opt/vd/src && bash scripts/download_models.sh && bash scripts/download_data.sh",
        f"cat > /etc/visiondoctor.env <<'EOF'\n{env_lines}\nVD_MCP_SECRET_ARN={secret_arn}\nEOF",
        "/opt/vd/venv/bin/python -m visiondoctor.cv_runtime | tee /var/log/vd-runtime.json",
        f"""cat > /etc/systemd/system/vd-{role}.service <<'EOF'
[Unit]
Description=VisionDoctor {role}
After=network-online.target
[Service]
EnvironmentFile=/etc/visiondoctor.env
WorkingDirectory=/opt/vd/src
ExecStart={exec_start}
Restart=always
User=root
[Install]
WantedBy=multi-user.target
EOF""",
        f"systemctl daemon-reload && systemctl enable --now vd-{role}",
    )
    return ud


class CoolComputeStack(cdk.Stack):
    def __init__(self, scope: Construct, cid: str, *, vpc: ec2.IVpc, data: DataStack, cool_ami_id: str, **kw: object) -> None:
        super().__init__(scope, cid, **kw)  # type: ignore[arg-type]
        ami = ec2.MachineImage.generic_linux({self.region: cool_ami_id})
        self.secret = sm.Secret(self, "McpSecret", description="Shared secret header for the internal MCP endpoint",
                                generate_secret_string=sm.SecretStringGenerator(exclude_punctuation=True))
        role = iam.Role(self, "WorkerRole", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
                        managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
                                          iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchAgentServerPolicy")])
        data.bucket.grant_read_write(role)
        for t in data.tables.values():
            t.grant_read_write_data(role)
        data.queue.grant_consume_messages(role)
        self.secret.grant_read(role)
        role.add_to_policy(iam.PolicyStatement(actions=["bedrock:InvokeModel", "bedrock:Converse"],
                                               resources=[f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/*",
                                                          "arn:aws:bedrock:*::foundation-model/anthropic.*"]))
        role.add_to_policy(iam.PolicyStatement(actions=["ssm:GetParameter"], resources=[
            f"arn:aws:ssm:{self.region}:{self.account}:parameter/visiondoctor/*"]))
        self.worker_sg = ec2.SecurityGroup(self, "WorkerSg", vpc=vpc, description="COOL workers")
        self.mcp_sg = ec2.SecurityGroup(self, "McpSg", vpc=vpc, description="MCP server (internal ALB only)")

        def lt(name: str, itype: str, role_name: str, sg: ec2.SecurityGroup) -> ec2.LaunchTemplate:
            return ec2.LaunchTemplate(
                self, name, machine_image=ami, instance_type=ec2.InstanceType(itype), role=role,
                security_group=sg, require_imdsv2=True, detailed_monitoring=True,
                block_devices=[ec2.BlockDevice(device_name="/dev/sda1", volume=ec2.BlockDeviceVolume.ebs(60, encrypted=True))],
                user_data=user_data(role_name, data, self.secret.secret_arn, self.region),
            )

        itype = self.node.try_get_context("coolInstanceType") or "c8g.2xlarge"
        self.workers = asg.AutoScalingGroup(
            self, "Workers", vpc=vpc, vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            launch_template=lt("WorkerLt", itype, "worker", self.worker_sg), min_capacity=1, max_capacity=6,
        )
        self.workers.scale_on_metric(
            "QueueDepth", metric=data.queue.metric_approximate_number_of_messages_visible(),
            scaling_steps=[asg.ScalingInterval(upper=0, change=0), asg.ScalingInterval(lower=50, change=1),
                           asg.ScalingInterval(lower=200, change=2)],
            adjustment_type=asg.AdjustmentType.CHANGE_IN_CAPACITY,
        )
        mcp_asg = asg.AutoScalingGroup(
            self, "Mcp", vpc=vpc, vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            launch_template=lt("McpLt", self.node.try_get_context("vlmInstanceType") or "m8g.4xlarge", "mcp", self.mcp_sg),
            min_capacity=1, max_capacity=1,
        )
        alb_sg = ec2.SecurityGroup(self, "McpAlbSg", vpc=vpc, description="internal MCP ALB")
        self.alb = elbv2.ApplicationLoadBalancer(self, "McpAlb", vpc=vpc, internet_facing=False, security_group=alb_sg)
        listener = self.alb.add_listener("Http", port=8765, protocol=elbv2.ApplicationProtocol.HTTP, open=False)
        listener.add_targets("McpTargets", port=8765, protocol=elbv2.ApplicationProtocol.HTTP, targets=[mcp_asg],
                             health_check=elbv2.HealthCheck(path="/mcp", healthy_http_codes="200-499"))
        self.mcp_sg.add_ingress_rule(alb_sg, ec2.Port.tcp(8765), "ALB to MCP")
        self.mcp_url = f"http://{self.alb.load_balancer_dns_name}:8765/mcp"
        self.alb_sg = alb_sg
        NagSuppressions.add_stack_suppressions(self, [
            {"id": "AwsSolutions-IAM4", "reason": "SSM core + CloudWatch agent managed policies are the AWS-recommended baseline."},
            {"id": "AwsSolutions-IAM5", "reason": "Wildcards limited to the project bucket objects, inference profiles and /visiondoctor/* params."},
            {"id": "AwsSolutions-ELB2", "reason": "Internal-only ALB in private subnets; access logs not needed for the demo."},
            {"id": "AwsSolutions-SMG4", "reason": "Static shared secret rotated at redeploy; rotation Lambda out of scope."},
            {"id": "AwsSolutions-AS3", "reason": "ASG notifications covered by CloudWatch alarms in VdObservability."},
            {"id": "AwsSolutions-EC23", "reason": "No 0.0.0.0/0 ingress; SGs reference other SGs only."},
        ])
