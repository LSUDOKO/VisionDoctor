#!/usr/bin/env python3
"""VisionDoctor CDK app (docs/05 §4). Deploy order: network → data → auth → compute → app → web → obs."""

from __future__ import annotations

import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks

from stacks.app_stack import AppStack
from stacks.auth_stack import AuthStack
from stacks.bench_stack import BenchStack
from stacks.compute_stack import CoolComputeStack
from stacks.data_stack import DataStack
from stacks.network_stack import NetworkStack
from stacks.observability_stack import ObservabilityStack
from stacks.web_stack import WebStack

app = cdk.App()
region = app.node.try_get_context("region") or "us-east-1"
env = cdk.Environment(account=app.node.try_get_context("account"), region=region)
cool_ami = app.node.try_get_context("coolAmiId")
if not cool_ami:
    raise SystemExit("pass -c coolAmiId=ami-... (find it after subscribing to COOL in AWS Marketplace; docs/05 §3)")

net = NetworkStack(app, "VdNetwork", env=env)
data = DataStack(app, "VdData", env=env)
auth = AuthStack(app, "VdAuth", env=env)
compute = CoolComputeStack(app, "VdCoolCompute", vpc=net.vpc, data=data, cool_ami_id=cool_ami, env=env)
web_app = AppStack(app, "VdApp", vpc=net.vpc, data=data, auth=auth, mcp_url=compute.mcp_url,
                   mcp_sg=compute.alb_sg, env=env)
web = WebStack(app, "VdWeb", api_alb=web_app.alb, env=env)
ObservabilityStack(app, "VdObservability", data=data, compute=compute, app_stack=web_app, env=env)
if app.node.try_get_context("bench"):
    BenchStack(app, "VdBench", vpc=net.vpc, data=data, cool_ami_id=cool_ami, env=env)

cdk.Tags.of(app).add("project", "visiondoctor")
cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))
app.synth()
