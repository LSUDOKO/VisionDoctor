"""Deploy (or destroy) the lean, credit-friendly VisionDoctor stacks without CDK bootstrap.

Synthesises infra/ with `-c lean=1` (BootstraplessSynthesizer, no asset Lambdas) and applies
the templates with CloudFormation in dependency order: VdData → VdAuth → VdLean.

    python scripts/deploy_lean.py --email you@example.com            # deploy / update
    python scripts/deploy_lean.py --destroy                          # delete stacks
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, WaiterError

ROOT = Path(__file__).resolve().parents[1]
STACKS = ["VdData", "VdAuth", "VdLean"]


def synth(region: str, account: str, email: str | None, extra: dict[str, str]) -> Path:
    out = ROOT / "infra" / "cdk.out.lean"
    ec2 = boto3.client("ec2", region_name=region)
    pl = ec2.describe_managed_prefix_lists(
        Filters=[{"Name": "prefix-list-name", "Values": ["com.amazonaws.global.cloudfront.origin-facing"]}])
    ctx = {"lean": "1", "region": region, "account": account,
           "cloudfrontPrefixList": pl["PrefixLists"][0]["PrefixListId"], **extra}
    if email:
        ctx["alertEmail"] = email
    env = os.environ | {"CDK_CONTEXT_JSON": json.dumps(ctx), "CDK_OUTDIR": str(out)}
    py = ROOT / "infra" / ".venv" / "bin" / "python"
    subprocess.run([str(py), "app.py"], cwd=ROOT / "infra", env=env, check=True)
    return out


def deploy(cfn: object, name: str, body: str) -> None:
    caps = ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"]
    try:
        cfn.describe_stacks(StackName=name)  # type: ignore[attr-defined]
        exists = True
    except ClientError:
        exists = False
    try:
        if exists:
            cfn.update_stack(StackName=name, TemplateBody=body, Capabilities=caps)  # type: ignore[attr-defined]
            waiter = "stack_update_complete"
        else:
            cfn.create_stack(StackName=name, TemplateBody=body, Capabilities=caps,  # type: ignore[attr-defined]
                             Tags=[{"Key": "project", "Value": "visiondoctor"}], OnFailure="ROLLBACK")
            waiter = "stack_create_complete"
    except ClientError as e:
        if "No updates are to be performed" in str(e):
            print(f"{name}: up to date")
            return
        raise
    print(f"{name}: {waiter.split('_')[1]} in progress…", flush=True)
    try:
        cfn.get_waiter(waiter).wait(StackName=name, WaiterConfig={"Delay": 15, "MaxAttempts": 160})  # type: ignore[attr-defined]
    except WaiterError:
        events = cfn.describe_stack_events(StackName=name)["StackEvents"][:15]  # type: ignore[attr-defined]
        for ev in events:
            if "FAILED" in ev["ResourceStatus"]:
                print(" ", ev["LogicalResourceId"], ev["ResourceStatus"], ev.get("ResourceStatusReason", ""))
        sys.exit(f"{name} failed")
    print(f"{name}: done")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-south-1"))
    ap.add_argument("--email")
    ap.add_argument("--instance-type", default="c8g.large")
    ap.add_argument("--cool-ami", help="use the COOL AMI (requires Marketplace subscription)")
    ap.add_argument("--destroy", action="store_true")
    args = ap.parse_args()
    account = boto3.client("sts").get_caller_identity()["Account"]
    cfn = boto3.client("cloudformation", region_name=args.region)
    if args.destroy:
        for name in reversed(STACKS):
            print("deleting", name)
            cfn.delete_stack(StackName=name)
            cfn.get_waiter("stack_delete_complete").wait(StackName=name, WaiterConfig={"Delay": 15, "MaxAttempts": 160})
        print("Deleted. S3 buckets are retained (empty and delete them in the console if you want them gone).")
        return
    extra = {"leanInstanceType": args.instance_type}
    if args.cool_ami:
        extra |= {"ami": "cool", "coolAmiId": args.cool_ami}
    out = synth(args.region, account, args.email, extra)
    for name in STACKS:
        deploy(cfn, name, (out / f"{name}.template.json").read_text())
    outs = {o["OutputKey"]: o["OutputValue"] for s in STACKS
            for o in cfn.describe_stacks(StackName=s)["Stacks"][0].get("Outputs", [])}
    print(json.dumps(outs, indent=2))
    (ROOT / "results" / "final").mkdir(parents=True, exist_ok=True)
    (ROOT / "results" / "final" / "aws_outputs.json").write_text(json.dumps(outs, indent=2))


if __name__ == "__main__":
    main()
