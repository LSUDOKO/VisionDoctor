"""S3 (frames 7 d, evidence 90 d, results versioned), DynamoDB tables (docs/02 §4), SQS + DLQ."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from cdk_nag import NagSuppressions
from constructs import Construct

TABLES = ("cameras", "health_reports", "incidents", "traces", "approvals", "profiles", "tickets")


class DataStack(cdk.Stack):
    def __init__(self, scope: Construct, cid: str, **kw: object) -> None:
        super().__init__(scope, cid, **kw)  # type: ignore[arg-type]
        self.access_logs = s3.Bucket(
            self, "AccessLogs", block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED, enforce_ssl=True,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
            lifecycle_rules=[s3.LifecycleRule(expiration=cdk.Duration.days(90))],
            removal_policy=cdk.RemovalPolicy.DESTROY, auto_delete_objects=True,
        )
        self.bucket = s3.Bucket(
            self, "Media", block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED, enforce_ssl=True, versioned=True,
            server_access_logs_bucket=self.access_logs, server_access_logs_prefix="media/",
            lifecycle_rules=[
                s3.LifecycleRule(prefix="frames/", expiration=cdk.Duration.days(7)),
                s3.LifecycleRule(prefix="live/", expiration=cdk.Duration.days(7)),
                s3.LifecycleRule(prefix="evidence/", expiration=cdk.Duration.days(90)),
                s3.LifecycleRule(noncurrent_version_expiration=cdk.Duration.days(30)),
            ],
            removal_policy=cdk.RemovalPolicy.DESTROY, auto_delete_objects=True,
        )
        self.tables: dict[str, ddb.Table] = {}
        for name in TABLES:
            self.tables[name] = ddb.Table(
                self, f"T-{name}", table_name=f"visiondoctor-{name}",
                partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
                sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING),
                billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
                point_in_time_recovery_specification=ddb.PointInTimeRecoverySpecification(point_in_time_recovery_enabled=True),
                encryption=ddb.TableEncryption.AWS_MANAGED,
                time_to_live_attribute="ttl" if name == "health_reports" else None,
                removal_policy=cdk.RemovalPolicy.DESTROY,
            )
        self.dlq = sqs.Queue(self, "ScanDlq", enforce_ssl=True, encryption=sqs.QueueEncryption.SQS_MANAGED,
                             retention_period=cdk.Duration.days(14))
        self.queue = sqs.Queue(
            self, "ScanJobs", enforce_ssl=True, encryption=sqs.QueueEncryption.SQS_MANAGED,
            visibility_timeout=cdk.Duration.seconds(120),
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=self.dlq),
        )
        NagSuppressions.add_resource_suppressions(self.access_logs, [
            {"id": "AwsSolutions-S1", "reason": "This is the access-log destination bucket."},
        ])
        NagSuppressions.add_resource_suppressions(self.dlq, [
            {"id": "AwsSolutions-SQS3", "reason": "This queue is the DLQ."},
        ])
