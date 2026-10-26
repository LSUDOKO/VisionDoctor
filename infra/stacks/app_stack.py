"""API + agent on ECS Fargate ARM64 behind a public ALB (fronted by CloudFront in WebStack)."""

from __future__ import annotations

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subs
from cdk_nag import NagSuppressions
from constructs import Construct

from stacks.auth_stack import AuthStack
from stacks.data_stack import DataStack

ROOT = Path(__file__).resolve().parents[2]


class AppStack(cdk.Stack):
    def __init__(self, scope: Construct, cid: str, *, vpc: ec2.IVpc, data: DataStack, auth: AuthStack,
                 mcp_url: str, mcp_sg: ec2.ISecurityGroup, **kw: object) -> None:
        super().__init__(scope, cid, **kw)  # type: ignore[arg-type]
        self.topic = sns.Topic(self, "Approvals", topic_name="visiondoctor-approvals", enforce_ssl=True)
        email = self.node.try_get_context("alertEmail")
        if email:
            self.topic.add_subscription(subs.EmailSubscription(email))
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc, container_insights_v2=ecs.ContainerInsights.ENABLED)
        task = ecs.FargateTaskDefinition(
            self, "Task", cpu=2048, memory_limit_mib=4096,
            runtime_platform=ecs.RuntimePlatform(cpu_architecture=ecs.CpuArchitecture.ARM64,
                                                 operating_system_family=ecs.OperatingSystemFamily.LINUX),
        )
        log_group = logs.LogGroup(self, "ApiLogs", retention=logs.RetentionDays.ONE_MONTH,
                                  removal_policy=cdk.RemovalPolicy.DESTROY)
        task.add_container(
            "api",
            image=ecs.ContainerImage.from_asset(str(ROOT), file="docker/Dockerfile.api"),
            port_mappings=[ecs.PortMapping(container_port=8000)],
            logging=ecs.LogDriver.aws_logs(stream_prefix="api", log_group=log_group),
            environment={
                "VD_BACKEND": "aws", "VD_AGENT": "bedrock", "VD_AWS_REGION": self.region,
                "VD_S3_BUCKET": data.bucket.bucket_name, "VD_SNS_TOPIC_ARN": self.topic.topic_arn,
                "VD_COGNITO_USER_POOL_ID": auth.pool.user_pool_id, "VD_COGNITO_CLIENT_ID": auth.client.user_pool_client_id,
                "VD_MCP_URL": mcp_url, "VD_EMF": "1", "VD_CAMERAS": "12", "VD_SCAN_INTERVAL": "20",
            },
            health_check=ecs.HealthCheck(command=["CMD-SHELL", "curl -fs http://localhost:8000/health || exit 1"],
                                         start_period=cdk.Duration.seconds(180)),
        )
        data.bucket.grant_read_write(task.task_role)
        for t in data.tables.values():
            t.grant_read_write_data(task.task_role)
        data.queue.grant_send_messages(task.task_role)
        self.topic.grant_publish(task.task_role)
        auth.model_param.grant_read(task.task_role)
        task.task_role.add_to_principal_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:Converse", "bedrock:ListInferenceProfiles"],
            resources=[f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/*",
                       "arn:aws:bedrock:*::foundation-model/anthropic.*"]))
        sg = ec2.SecurityGroup(self, "ApiSg", vpc=vpc, description="API tasks")
        self.service = ecs.FargateService(self, "Api", cluster=cluster, task_definition=task, desired_count=1,
                                          security_groups=[sg], assign_public_ip=False,
                                          health_check_grace_period=cdk.Duration.seconds(240))
        mcp_sg.add_ingress_rule(sg, ec2.Port.tcp(8765), "API/agent to MCP")
        self.alb = elbv2.ApplicationLoadBalancer(self, "Alb", vpc=vpc, internet_facing=True)
        listener = self.alb.add_listener("Http", port=80, open=True)
        listener.add_targets("Api", port=8000, targets=[self.service],
                             health_check=elbv2.HealthCheck(path="/health", interval=cdk.Duration.seconds(30)))
        cdk.CfnOutput(self, "AlbDns", value=self.alb.load_balancer_dns_name)
        NagSuppressions.add_stack_suppressions(self, [
            {"id": "AwsSolutions-IAM5", "reason": "Scoped to project bucket objects and Bedrock inference profiles."},
            {"id": "AwsSolutions-ELB2", "reason": "CloudFront standard logs cover access logging for the demo."},
            {"id": "AwsSolutions-EC23", "reason": "Public ALB on :80 is the CloudFront origin; HTTPS terminates at CloudFront."},
            {"id": "AwsSolutions-ECS2", "reason": "Env vars hold resource names/ARNs only; secrets come from Secrets Manager/SSM."},
        ])
