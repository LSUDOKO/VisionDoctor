"""Temporary benchmark instances (docs/05 §6): COOL vs stock OpenCV 5 on Graviton4 vs x86.

Each instance runs bench/run.py at boot, uploads results to S3 and shuts down (terminate on
shutdown). Deploy with ``-c bench=1``; destroy right after.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from cdk_nag import NagSuppressions
from constructs import Construct

from stacks.compute_stack import REPO
from stacks.data_stack import DataStack

CONFIGS = {
    "A": ("c8g.4xlarge", "cool"),
    "B": ("c8g.4xlarge", "stock"),
    "C": ("c7i.4xlarge", "stock"),
}


class BenchStack(cdk.Stack):
    def __init__(self, scope: Construct, cid: str, *, vpc: ec2.IVpc, data: DataStack, cool_ami_id: str, **kw: object) -> None:
        super().__init__(scope, cid, **kw)  # type: ignore[arg-type]
        role = iam.Role(self, "BenchRole", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
                        managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")])
        data.bucket.grant_put(role, "bench/*")
        role.add_to_policy(iam.PolicyStatement(actions=["pricing:GetProducts"], resources=["*"]))
        for cfg, (itype, cv) in CONFIGS.items():
            arm = itype.startswith(("c8g", "m8g"))
            if cv == "cool":
                ami = ec2.MachineImage.generic_linux({self.region: cool_ami_id})
                py = "/opt/cool/venvs/python_3.12/bin/python -m venv --system-site-packages /opt/b/venv"
                extra = ""
            else:
                ami = ec2.MachineImage.from_ssm_parameter(
                    "/aws/service/canonical/ubuntu/server/24.04/stable/current/"
                    + ("arm64" if arm else "amd64") + "/hvm/ebs-gp3/ami-id")
                py = "apt-get install -y python3-venv && python3 -m venv /opt/b/venv"
                extra = "[opencv]"
            ud = ec2.UserData.for_linux()
            ud.add_commands(
                "set -eux", "apt-get update && apt-get install -y git unzip awscli || snap install aws-cli --classic",
                "mkdir -p /opt/b && cd /opt/b", f"git clone --depth 1 {REPO} src", py,
                f"/opt/b/venv/bin/pip install -e 'src{extra}'",
                "cd src && bash scripts/download_data.sh && bash scripts/download_models.sh",
                f"VD_BENCH_CONFIG={cfg} /opt/b/venv/bin/python bench/run.py --reps 50 --warmup 10 --runs 3",
                f"aws s3 cp --recursive results/bench s3://{data.bucket.bucket_name}/bench/",
                "shutdown -h now",
            )
            ec2.Instance(self, f"Bench{cfg}", vpc=vpc, instance_type=ec2.InstanceType(itype), machine_image=ami, role=role,
                         user_data=ud, require_imdsv2=True, instance_initiated_shutdown_behavior=ec2.InstanceInitiatedShutdownBehavior.TERMINATE,
                         vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                         block_devices=[ec2.BlockDevice(device_name="/dev/sda1", volume=ec2.BlockDeviceVolume.ebs(40, encrypted=True))])
        NagSuppressions.add_stack_suppressions(self, [
            {"id": "AwsSolutions-IAM4", "reason": "SSM core managed policy for Run Command access."},
            {"id": "AwsSolutions-IAM5", "reason": "Pricing API has no resource-level permissions; S3 limited to bench/*."},
            {"id": "AwsSolutions-EC28", "reason": "Short-lived benchmark instances."},
            {"id": "AwsSolutions-EC29", "reason": "Instances self-terminate after the run."},
        ])
