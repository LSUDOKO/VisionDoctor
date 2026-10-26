"""Dashboard on S3 + CloudFront (OAC); /api/* and /health routed to the API ALB."""

from __future__ import annotations

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_cloudfront as cf
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3d
from cdk_nag import NagSuppressions
from constructs import Construct

DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


class WebStack(cdk.Stack):
    def __init__(self, scope: Construct, cid: str, *, api_alb: elbv2.IApplicationLoadBalancer, **kw: object) -> None:
        super().__init__(scope, cid, **kw)  # type: ignore[arg-type]
        site = s3.Bucket(self, "Site", block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                         encryption=s3.BucketEncryption.S3_MANAGED, enforce_ssl=True,
                         removal_policy=cdk.RemovalPolicy.DESTROY, auto_delete_objects=True)
        api_origin = origins.LoadBalancerV2Origin(api_alb, protocol_policy=cf.OriginProtocolPolicy.HTTP_ONLY)
        api_behavior = cf.BehaviorOptions(
            origin=api_origin, allowed_methods=cf.AllowedMethods.ALLOW_ALL,
            cache_policy=cf.CachePolicy.CACHING_DISABLED,
            origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        )
        self.dist = cf.Distribution(
            self, "Cdn",
            default_behavior=cf.BehaviorOptions(origin=origins.S3BucketOrigin.with_origin_access_control(site),
                                                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS),
            additional_behaviors={"/api/*": api_behavior, "/health": api_behavior},
            default_root_object="index.html", minimum_protocol_version=cf.SecurityPolicyProtocol.TLS_V1_2_2021,
            error_responses=[cf.ErrorResponse(http_status=404, response_http_status=200, response_page_path="/index.html")],
        )
        if DIST.exists():
            s3d.BucketDeployment(self, "Deploy", sources=[s3d.Source.asset(str(DIST))], destination_bucket=site,
                                 distribution=self.dist)
        cdk.CfnOutput(self, "Url", value=f"https://{self.dist.distribution_domain_name}")
        NagSuppressions.add_stack_suppressions(self, [
            {"id": "AwsSolutions-S1", "reason": "Static site bucket served only through CloudFront OAC."},
            {"id": "AwsSolutions-CFR1", "reason": "No geo restriction: judges are worldwide."},
            {"id": "AwsSolutions-CFR2", "reason": "WAF out of scope for the demo; Cognito protects the API."},
            {"id": "AwsSolutions-CFR3", "reason": "Access logs omitted for the demo distribution."},
            {"id": "AwsSolutions-CFR4", "reason": "Default CloudFront certificate (no custom domain)."},
            {"id": "AwsSolutions-CFR5", "reason": "ALB origin is HTTP inside AWS; viewer side is HTTPS-only."},
            {"id": "AwsSolutions-IAM4", "reason": "BucketDeployment helper Lambda uses the CDK-managed basic role."},
            {"id": "AwsSolutions-IAM5", "reason": "BucketDeployment helper needs object wildcards on the site bucket."},
            {"id": "AwsSolutions-L1", "reason": "BucketDeployment runtime is managed by CDK."},
        ])
