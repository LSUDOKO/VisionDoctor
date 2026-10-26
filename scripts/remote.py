"""Run a shell command on the lean instance through SSM Run Command (no SSH) and print output."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: str, region: str = "ap-south-1", timeout: int = 600) -> str:
    iid = json.loads((ROOT / "results" / "final" / "aws_outputs.json").read_text())["InstanceId"]
    ssm = boto3.client("ssm", region_name=region)
    cid = ssm.send_command(InstanceIds=[iid], DocumentName="AWS-RunShellScript",
                           Parameters={"commands": [cmd], "executionTimeout": [str(timeout)]})["Command"]["CommandId"]
    for _ in range(timeout // 3):
        time.sleep(3)
        try:
            r = ssm.get_command_invocation(CommandId=cid, InstanceId=iid)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if r["Status"] not in ("Pending", "InProgress", "Delayed"):
            return f"[{r['Status']}]\n{r['StandardOutputContent']}\n{r['StandardErrorContent']}"
    return "[timeout]"


if __name__ == "__main__":
    print(run(" ".join(sys.argv[1:])))
