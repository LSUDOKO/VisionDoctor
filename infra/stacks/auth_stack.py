"""Cognito user pool (groups operator/technician/admin), app client, SSM parameters."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_ssm as ssm
from cdk_nag import NagSuppressions
from constructs import Construct


class AuthStack(cdk.Stack):
    def __init__(self, scope: Construct, cid: str, **kw: object) -> None:
        super().__init__(scope, cid, **kw)  # type: ignore[arg-type]
        self.pool = cognito.UserPool(
            self, "Users", self_sign_up_enabled=False, sign_in_aliases=cognito.SignInAliases(email=True),
            password_policy=cognito.PasswordPolicy(min_length=12, require_digits=True, require_symbols=True,
                                                   require_lowercase=True, require_uppercase=True),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            # Lean (credit-only) deploys use the free Essentials tier; Plus adds threat protection.
            **({"feature_plan": cognito.FeaturePlan.ESSENTIALS} if self.node.try_get_context("lean") else
               {"feature_plan": cognito.FeaturePlan.PLUS,
                "standard_threat_protection_mode": cognito.StandardThreatProtectionMode.FULL_FUNCTION}),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        self.client = self.pool.add_client(
            "Dashboard", auth_flows=cognito.AuthFlow(user_srp=True, user_password=True),
            access_token_validity=cdk.Duration.hours(8), id_token_validity=cdk.Duration.hours(8),
        )
        for g in ("operator", "technician", "admin"):
            cognito.CfnUserPoolGroup(self, f"G-{g}", user_pool_id=self.pool.user_pool_id, group_name=g)
        self.model_param = ssm.StringParameter(
            self, "BedrockModel", parameter_name="/visiondoctor/bedrock_model_id",
            string_value=self.node.try_get_context("bedrockModelId") or "auto",
            description="Bedrock inference profile for the agent ('auto' = newest available Claude Sonnet).",
        )
        cdk.CfnOutput(self, "UserPoolId", value=self.pool.user_pool_id)
        cdk.CfnOutput(self, "ClientId", value=self.client.user_pool_client_id)
        NagSuppressions.add_resource_suppressions(self.pool, [
            {"id": "AwsSolutions-COG2", "reason": "MFA optional for the judge demo user; enable for production."},
            {"id": "AwsSolutions-COG3", "reason": "Threat protection needs the paid Plus plan; off in the lean deploy."},
            {"id": "AwsSolutions-COG8", "reason": "Plus feature plan is a paid tier; lean deploy uses Essentials."},
        ])
