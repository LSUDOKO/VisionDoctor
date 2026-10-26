"""Render docs/img/architecture.png and agent_loop.png locally with OpenCV (sources: *.mmd)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "docs" / "img"
FONT = cv2.FONT_HERSHEY_SIMPLEX
COOL = (60, 140, 40)


def box(img: np.ndarray, x: int, y: int, w: int, h: int, lines: list[str], color: tuple[int, int, int] = (90, 60, 20),
        fill: tuple[int, int, int] = (250, 244, 235)) -> tuple[int, int, int, int]:
    cv2.rectangle(img, (x, y), (x + w, y + h), fill, -1)
    cv2.rectangle(img, (x, y), (x + w, y + h), color, 2, cv2.LINE_AA)
    for i, t in enumerate(lines):
        scale, th = (0.55, 2) if i == 0 else (0.45, 1)
        (tw, _), _ = cv2.getTextSize(t, FONT, scale, th)
        cv2.putText(img, t, (x + (w - tw) // 2, y + 24 + 20 * i), FONT, scale, (20, 20, 20), th, cv2.LINE_AA)
    return x, y, w, h


def arrow(img: np.ndarray, a: tuple[int, int, int, int], b: tuple[int, int, int, int], label: str = "") -> None:
    ax, ay = a[0] + a[2] // 2, a[1] + a[3] // 2
    bx, by = b[0] + b[2] // 2, b[1] + b[3] // 2
    # attach to box edges
    if abs(bx - ax) > abs(by - ay):
        p1 = (a[0] + a[2], ay) if bx > ax else (a[0], ay)
        p2 = (b[0], by) if bx > ax else (b[0] + b[2], by)
    else:
        p1 = (ax, a[1] + a[3]) if by > ay else (ax, a[1])
        p2 = (bx, b[1]) if by > ay else (bx, b[1] + b[3])
    cv2.arrowedLine(img, p1, p2, (70, 70, 70), 2, cv2.LINE_AA, tipLength=0.03)
    if label:
        cv2.putText(img, label, ((p1[0] + p2[0]) // 2 + 4, (p1[1] + p2[1]) // 2 - 6), FONT, 0.42, (40, 40, 160), 1, cv2.LINE_AA)


def architecture() -> None:
    img = np.full((820, 1500, 3), 255, np.uint8)
    cv2.putText(img, "VisionDoctor on AWS - OpenCV 5 + COOL on Graviton + agent via MCP", (30, 40), FONT, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.rectangle(img, (300, 70), (1480, 800), (150, 150, 150), 1)
    cv2.putText(img, "AWS account", (310, 92), FONT, 0.5, (100, 100, 100), 1)
    cv2.rectangle(img, (330, 270), (870, 560), COOL, 2)
    cv2.putText(img, "EC2 ASG c8g/m8g - COOL 3.1 AMI (OpenCV 5 + Arm KleidiCV)", (338, 292), FONT, 0.48, COOL, 1, cv2.LINE_AA)
    cams = box(img, 30, 330, 230, 80, ["Camera fleet", "simulator / RTSP"])
    ops = box(img, 30, 640, 230, 70, ["Operator / technician"])
    eb = box(img, 340, 110, 220, 70, ["EventBridge Scheduler", "periodic scans"])
    sqs = box(img, 620, 110, 220, 70, ["SQS scan-jobs", "+ DLQ"])
    s3 = box(img, 340, 190, 220, 60, ["S3", "frames / evidence (SSE)"])
    w = box(img, 350, 310, 240, 90, ["Health workers", "11 OpenCV 5 checks", "repairs + verify"], COOL, (235, 248, 232))
    imp = box(img, 610, 310, 240, 90, ["Impact predictor", "YOLOX OpenCV DNN", "+ HGB regressor"], COOL, (235, 248, 232))
    mcp = box(img, 480, 440, 260, 90, ["MCP tool server", "13 tools, streamable HTTP", "shared-secret header"], COOL, (235, 248, 232))
    ddb = box(img, 950, 110, 240, 70, ["DynamoDB", "cameras/health/incidents/traces"])
    ag = box(img, 950, 330, 250, 90, ["Agent (Fargate ARM64)", "policy or Bedrock Converse", "guard + traces"])
    br = box(img, 1260, 330, 200, 70, ["Amazon Bedrock", "Claude Sonnet"])
    sns = box(img, 1260, 450, 200, 60, ["SNS approvals"])
    api = box(img, 950, 600, 250, 70, ["FastAPI (ECS Fargate)", "Cognito JWT"])
    cf = box(img, 560, 640, 260, 70, ["CloudFront + S3", "React dashboard"])
    cog = box(img, 950, 715, 250, 60, ["Cognito user pool"])
    cw = box(img, 1260, 600, 200, 80, ["CloudWatch", "EMF metrics, alarms", "dashboard, budget"])
    for a, b, lab in [(cams, s3, "frames"), (eb, sqs, ""), (sqs, w, "jobs"), (w, imp, ""), (w, ddb, "reports"),
                      (w, ag, "incident"), (ag, mcp, "MCP tools"), (ag, br, ""), (ag, sns, "approval"),
                      (api, ddb, ""), (cf, api, "/api/*"), (cog, api, ""), (ops, cf, "HTTPS"), (ag, cw, "")]:
        arrow(img, a, b, lab)
    cv2.imwrite(str(OUT / "architecture.png"), img)


def agent_loop() -> None:
    img = np.full((760, 1100, 3), 255, np.uint8)
    cv2.putText(img, "Agent loop: OpenCV results decide the next tool call", (30, 40), FONT, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
    s = box(img, 40, 80, 200, 60, ["scan_camera"])
    t = box(img, 300, 80, 240, 60, ["close_incident", "(transient)"])
    d = box(img, 40, 180, 200, 60, ["diagnose"])
    p = box(img, 40, 280, 200, 60, ["predict_ai_impact"])
    a = box(img, 300, 280, 200, 60, ["apply_repair", "(guard: bounds)"])
    v = box(img, 560, 280, 220, 60, ["verify_repair", "re-scan + re-predict"])
    ok = box(img, 840, 280, 220, 60, ["close_incident", "(auto_fixed)"])
    rb = box(img, 560, 400, 220, 60, ["rollback_repair"])
    de = box(img, 40, 520, 220, 60, ["describe_fault", "(VLM, blurred)"])
    ap = box(img, 320, 640, 260, 60, ["request_human_approval"])
    wa = box(img, 40, 640, 220, 60, ["set_watch"])
    for x, y, lab in [(s, t, "healthy"), (s, d, "faults"), (d, p, ""), (p, a, "fixable"), (a, v, ""), (v, ok, "recovered"),
                      (v, rb, "not recovered"), (rb, de, ""), (p, de, "physical"), (de, ap, "drop x crit >= 0.6"), (de, wa, "low impact")]:
        arrow(img, x, y, lab)
    cv2.imwrite(str(OUT / "agent_loop.png"), img)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    architecture()
    agent_loop()
