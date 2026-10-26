"""VPC across 2 AZs, private compute subnets, one NAT (package installs only), VPC endpoints."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from cdk_nag import NagSuppressions
from constructs import Construct


class NetworkStack(cdk.Stack):
    def __init__(self, scope: Construct, cid: str, **kw: object) -> None:
        super().__init__(scope, cid, **kw)  # type: ignore[arg-type]
        self.vpc = ec2.Vpc(
            self, "Vpc", max_azs=2, nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=22),
            ],
            flow_logs={"all": ec2.FlowLogOptions(traffic_type=ec2.FlowLogTrafficType.REJECT)},
        )
        self.vpc.add_gateway_endpoint("S3", service=ec2.GatewayVpcEndpointAwsService.S3)
        self.vpc.add_gateway_endpoint("Ddb", service=ec2.GatewayVpcEndpointAwsService.DYNAMODB)
        for name, svc in {
            "Sqs": ec2.InterfaceVpcEndpointAwsService.SQS,
            "BedrockRt": ec2.InterfaceVpcEndpointAwsService.BEDROCK_RUNTIME,
            "Ssm": ec2.InterfaceVpcEndpointAwsService.SSM,
            "Secrets": ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
            "Logs": ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
        }.items():
            self.vpc.add_interface_endpoint(name, service=svc, private_dns_enabled=True)
        NagSuppressions.add_stack_suppressions(self, [
            {"id": "AwsSolutions-EC23", "reason": "Interface endpoint SGs allow VPC CIDR on 443 only (CDK default)."},
        ])
