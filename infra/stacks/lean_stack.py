"""Lean, credit-friendly deployment (~$1.3/day): one Graviton4 instance + CloudFront.

The full architecture (COOL worker ASG, Fargate API, NAT, interface endpoints) costs ~$31/day.
For judging we run API + fleet monitor + agent + MCP-equivalent tools + dashboard on a single
c8g instance in a public subnet whose only ingress is CloudFront's origin-facing prefix list
on :8000; CloudFront terminates HTTPS. Data stays in the shared S3/DynamoDB stack, auth in
Cognito. With ``-c ami=cool -c coolAmiId=...`` the same instance boots the COOL AMI instead of
stock Ubuntu + the official OpenCV 5 wheel.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_cloudfront as cf
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subs
from cdk_nag import NagSuppressions
from constructs import Construct

from stacks.auth_stack import AuthStack
from stacks.compute_stack import REPO
from stacks.data_stack import DataStack

UBUNTU_ARM = "/aws/service/canonical/ubuntu/server/24.04/stable/current/arm64/hvm/ebs-gp3/ami-id"


class LeanStack(cdk.Stack):
    def __init__(self, scope: Construct, cid: str, *, data: DataStack, auth: AuthStack, **kw: object) -> None:
        super().__init__(scope, cid, **kw)  # type: ignore[arg-type]
        ctx = self.node.try_get_context
        email = ctx("alertEmail")
        itype = ctx("leanInstanceType") or "c8g.large"
        use_cool = ctx("ami") == "cool"
        model = ctx("bedrockModelId") or "apac.amazon.nova-lite-v1:0"
        cf_prefix_list = ctx("cloudfrontPrefixList")  # com.amazonaws.global.cloudfront.origin-facing
        if not cf_prefix_list:
            raise ValueError("pass -c cloudfrontPrefixList=pl-... (scripts/deploy_lean.py looks it up)")

        topic = sns.Topic(self, "Alerts", topic_name="visiondoctor-alerts", enforce_ssl=True)
        if email:
            topic.add_subscription(subs.EmailSubscription(email))

        vpc = ec2.Vpc(self, "Vpc", max_azs=2, nat_gateways=0,
                      subnet_configuration=[ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC,
                                                                    cidr_mask=24)])
        vpc.add_gateway_endpoint("S3", service=ec2.GatewayVpcEndpointAwsService.S3)
        vpc.add_gateway_endpoint("Ddb", service=ec2.GatewayVpcEndpointAwsService.DYNAMODB)
        sg = ec2.SecurityGroup(self, "AppSg", vpc=vpc, description="VisionDoctor app: CloudFront only",
                               allow_all_outbound=True)
        sg.add_ingress_rule(ec2.Peer.prefix_list(cf_prefix_list), ec2.Port.tcp(8000), "CloudFront origin-facing")

        role = iam.Role(self, "AppRole", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
                        managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")])
        data.bucket.grant_read_write(role)
        for t in data.tables.values():
            t.grant_read_write_data(role)
        topic.grant_publish(role)
        role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:Converse", "bedrock:ListInferenceProfiles"],
            resources=[f"arn:aws:bedrock:*:{self.account}:inference-profile/*", "arn:aws:bedrock:*::foundation-model/*"]))
        role.add_to_policy(iam.PolicyStatement(actions=["cloudwatch:PutMetricData"], resources=["*"],
                                               conditions={"StringEquals": {"cloudwatch:namespace": "VisionDoctor"}}))

        env = {
            "VD_BACKEND": "aws", "VD_AWS_REGION": self.region, "AWS_DEFAULT_REGION": self.region,
            "VD_S3_BUCKET": data.bucket.bucket_name, "VD_SNS_TOPIC_ARN": topic.topic_arn,
            "VD_COGNITO_USER_POOL_ID": auth.pool.user_pool_id, "VD_COGNITO_CLIENT_ID": auth.client.user_pool_client_id,
            "VD_AGENT": "bedrock", "VD_BEDROCK_MODEL_ID": model, "VD_CAMERAS": "8", "VD_SCAN_INTERVAL": "20",
            "VD_STATE_DIR": "/opt/vd/state", "VD_CORS": "*",
        }
        env_lines = "\\n".join(f"{k}={v}" for k, v in env.items())
        if use_cool:
            ami = ec2.MachineImage.generic_linux({self.region: ctx("coolAmiId")})
            mkvenv = "/opt/cool/venvs/python_3.12/bin/python -m venv --system-site-packages /opt/vd/venv"
            install = "/opt/vd/venv/bin/pip install -e /opt/vd/src"  # COOL's cv2, never the wheel
        else:
            ami = ec2.MachineImage.from_ssm_parameter(UBUNTU_ARM)
            mkvenv = "python3 -m venv /opt/vd/venv"
            install = ("/opt/vd/venv/bin/pip install --require-hashes -r /opt/vd/src/requirements.lock && "
                       "/opt/vd/venv/bin/pip install --no-deps -e /opt/vd/src")
        ud = ec2.UserData.for_linux()
        ud.add_commands(
            "set -euxo pipefail",
            "export DEBIAN_FRONTEND=noninteractive",
            "apt-get update && apt-get install -y git curl unzip python3-venv python3-pip nodejs npm libgl1",
            "mkdir -p /opt/vd/state && cd /opt/vd",
            f"git clone --depth 1 {REPO} src",
            mkvenv,
            install,
            "cd /opt/vd/src && bash scripts/download_models.sh && bash scripts/download_data.sh",
            "cd /opt/vd/src/web && npm ci --no-audit --no-fund && npm run build",
            f"printf '{env_lines}\\n' > /etc/visiondoctor.env",
            "/opt/vd/venv/bin/python -m visiondoctor.cv_runtime > /var/log/vd-runtime.json",
            "useradd -r -d /opt/vd -s /usr/sbin/nologin vd || true",
            "chown -R vd /opt/vd",
            "printf '[Unit]\\nDescription=VisionDoctor\\nAfter=network-online.target\\n[Service]\\n"
            "EnvironmentFile=/etc/visiondoctor.env\\nWorkingDirectory=/opt/vd/src\\nUser=vd\\n"
            "ExecStart=/opt/vd/venv/bin/python -m visiondoctor.cli serve --host 0.0.0.0 --port 8000\\n"
            "Restart=always\\n[Install]\\nWantedBy=multi-user.target\\n' > /etc/systemd/system/visiondoctor.service",
            "systemctl daemon-reload && systemctl enable --now visiondoctor",
        )
        self.instance = ec2.Instance(
            self, "App", vpc=vpc, vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            instance_type=ec2.InstanceType(itype), machine_image=ami, role=role, security_group=sg,
            user_data=ud, require_imdsv2=True, associate_public_ip_address=True, detailed_monitoring=False,
            block_devices=[ec2.BlockDevice(device_name="/dev/sda1", volume=ec2.BlockDeviceVolume.ebs(30, encrypted=True))],
        )
        origin = origins.HttpOrigin(self.instance.instance_public_dns_name, http_port=8000,
                                    protocol_policy=cf.OriginProtocolPolicy.HTTP_ONLY,
                                    read_timeout=cdk.Duration.seconds(60))
        self.dist = cf.Distribution(
            self, "Cdn",
            default_behavior=cf.BehaviorOptions(
                origin=origin, allowed_methods=cf.AllowedMethods.ALLOW_ALL, cache_policy=cf.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS),
            minimum_protocol_version=cf.SecurityPolicyProtocol.TLS_V1_2_2021,
            price_class=cf.PriceClass.PRICE_CLASS_200,
        )

        alarm = cw.Alarm(self, "InstanceStatus", metric=cw.Metric(
            namespace="AWS/EC2", metric_name="StatusCheckFailed", dimensions_map={"InstanceId": self.instance.instance_id},
            statistic="Maximum", period=cdk.Duration.minutes(5)), threshold=1, evaluation_periods=2)
        from aws_cdk import aws_cloudwatch_actions as cwa

        alarm.add_alarm_action(cwa.SnsAction(topic))
        dash = cw.Dashboard(self, "Dash", dashboard_name="VisionDoctor-lean")
        dash.add_widgets(cw.GraphWidget(title="Instance CPU", left=[cw.Metric(
            namespace="AWS/EC2", metric_name="CPUUtilization", dimensions_map={"InstanceId": self.instance.instance_id})]),
            cw.GraphWidget(title="VisionDoctor fleet", left=[cw.Metric(namespace="VisionDoctor", metric_name=n,
                                                                     statistic="Average") for n in
                                                           ("PredictedFleetAccuracy", "CamerasHealthy", "CamerasDegraded")]))
        if email:
            for amount in (20, 50):
                budgets.CfnBudget(self, f"Budget{amount}", budget=budgets.CfnBudget.BudgetDataProperty(
                    budget_type="COST", time_unit="MONTHLY", budget_name=f"visiondoctor-{amount}usd",
                    budget_limit=budgets.CfnBudget.SpendProperty(amount=amount, unit="USD")),
                    notifications_with_subscribers=[budgets.CfnBudget.NotificationWithSubscribersProperty(
                        notification=budgets.CfnBudget.NotificationProperty(comparison_operator="GREATER_THAN",
                                                                            notification_type="ACTUAL", threshold=100),
                        subscribers=[budgets.CfnBudget.SubscriberProperty(subscription_type="EMAIL", address=email)])])
        cdk.CfnOutput(self, "Url", value=f"https://{self.dist.distribution_domain_name}")
        cdk.CfnOutput(self, "InstanceId", value=self.instance.instance_id)
        NagSuppressions.add_stack_suppressions(self, [
            {"id": "AwsSolutions-VPC7", "reason": "Lean demo VPC; flow logs omitted to stay within credits."},
            {"id": "AwsSolutions-EC23", "reason": "Ingress only from the CloudFront origin-facing prefix list on 8000."},
            {"id": "AwsSolutions-EC28", "reason": "Single demo instance; detailed monitoring off to save cost."},
            {"id": "AwsSolutions-EC29", "reason": "Demo instance without termination protection so `make down` works."},
            {"id": "AwsSolutions-IAM4", "reason": "SSM core managed policy for Session Manager access (no SSH)."},
            {"id": "AwsSolutions-IAM5", "reason": "Scoped to project bucket objects, Bedrock profiles and the VisionDoctor metric namespace."},
            {"id": "AwsSolutions-CFR1", "reason": "No geo restriction: judges are worldwide."},
            {"id": "AwsSolutions-CFR2", "reason": "WAF out of scope; Cognito protects the API."},
            {"id": "AwsSolutions-CFR3", "reason": "Access logs omitted for the demo distribution."},
            {"id": "AwsSolutions-CFR4", "reason": "Default CloudFront certificate (no custom domain)."},
            {"id": "AwsSolutions-CFR5", "reason": "Origin is HTTP inside AWS (CloudFront-only SG); viewers are HTTPS-only."},
            {"id": "AwsSolutions-SNS3", "reason": "Topic enforces SSL via enforce_ssl."},
        ])
