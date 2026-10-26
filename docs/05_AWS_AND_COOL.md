# 05 — AWS Deployment and COOL (Cloud delivery 10% + Best Use of COOL Award)

## 1. COOL facts (verified from the AWS Marketplace listing, Oct 2026)
- Product: **Cloud Optimized OpenCV For AWS Graviton4** (seller: OpenCV), listing `prodview-fdvbfiewzuehs`.
- **Version 3.1**, built on **OpenCV 5.0**, with **Arm KleidiCV** optimizations plus tuned parallelization.
- Delivery: **64-bit Arm AMI, Ubuntu 24.04 LTS**. Docker variant: "Cloud-Optimized OpenCV for AWS
  Graviton4 [Docker]" (`prodview-fsbcuniykfunw`) for ECS/EKS. Graviton2/3/5 builds also listed.
- Install paths: libraries under `/opt/cool`; Python venvs `/opt/cool/venvs/python_3.10`,
  `python_3.11`, `python_3.12`; C++ SDK `/opt/cool/cpp_sdk` (CMake `OpenCV_DIR=/opt/cool/cpp_sdk/lib/cmake/opencv4`).
- Activate: `source /opt/cool/venvs/python_3.12/bin/activate`. Or system Python:
  `export LD_LIBRARY_PATH=/opt/cool/cpp_sdk/lib:$LD_LIBRARY_PATH` and
  `export PYTHONPATH=/opt/cool/python_3.12/site-packages/`.
- Instances: recommended `m8g.4xlarge`+; compatible families `c8g`, `m8g`, `r8g`.
- Pricing: 7-day free trial, then hourly software fee per instance (e.g. listed c8g.xlarge $0.01/h,
  c8g.4xlarge $0.04/h, m8g.4xlarge $0.04/h) **plus** normal EC2 cost.
- Vendor benchmark: 78 widely used imgproc/core/IO functions vs. default OpenCV 5.0.0 build.

> ⚠️ The free trial auto-converts to paid after 7 days — cancel the subscription after judging if not needed.

**Hard rule:** on COOL machines **never `pip install opencv-python`** — it would shadow COOL's `cv2`.
Our package declares OpenCV as an *optional extra* (`visiondoctor[opencv]`) used only on non-COOL hosts.
`cv_runtime.py` logs `cv2.__file__` and `is_cool` at every worker start; the benchmark saves
`cv2.getBuildInformation()` to prove COOL executes the workload.

## 2. Target architecture
| Concern | Service | Why |
|---|---|---|
| Core vision workload (scan, repair, impact, MCP tools) | **EC2 Auto Scaling group on COOL AMI**, `c8g.2xlarge` (workers), 1× `m8g.4xlarge` (VLM + MCP) | COOL must execute the core workload on Graviton (award rule) |
| Job queue | SQS standard queue + DLQ (maxReceiveCount 3) | decouples scheduler/agent from workers; scales ASG on queue depth |
| Schedules | EventBridge Scheduler → Lambda (arm64) enqueuer | periodic fleet scans |
| Agent + API | ECS Fargate **ARM64** (FastAPI + agent workers) | no COOL needed; talks to MCP over HTTP |
| LLM | Amazon Bedrock (Converse API) | agent reasoning |
| Storage | S3 (frames 7-day lifecycle, evidence 90-day, results), DynamoDB on-demand + PITR | |
| Auth | Cognito user pool (groups: `operator`, `technician`, `admin`) | judges get a test user |
| Web | S3 + CloudFront (OAC); CloudFront also fronts the API ALB for HTTPS | no custom domain needed |
| Notifications | SNS topic `visiondoctor-approvals` (email) | human-in-the-loop |
| Config/secrets | SSM Parameter Store (model ID, thresholds version), Secrets Manager (MCP shared secret) | |
| Observability | CloudWatch Logs/Metrics/Dashboard/Alarms, ADOT → X-Ray traces | |
| Network | VPC, 2 AZs, private subnets for compute; Gateway endpoints S3/DynamoDB; Interface endpoints SQS, Bedrock Runtime, SSM, Secrets Manager, CloudWatch Logs | minimal NAT traffic |

The x86 baseline (benchmark only) is a separate, destroyable stack.

## 3. Finding the COOL AMI
1. Subscribe to the listing in the AWS Marketplace console (one-time, human step; free trial).
2. Find the AMI ID in your region:
   `aws ec2 describe-images --owners aws-marketplace --filters "Name=architecture,Values=arm64" "Name=name,Values=*OpenCV*" --query "Images[].[ImageId,Name,CreationDate]" --output table`
   (**VERIFY** the name pattern; fall back to the "Launch" page of the subscription, which shows the AMI ID).
3. Pass it to CDK: `cdk deploy -c coolAmiId=ami-xxxx` (no hardcoding).

## 4. CDK app (`infra/`, Python, CDK v2 pinned)
Stacks (deploy order):
1. `NetworkStack` — VPC (2 AZ, 1 NAT for package installs only), endpoints, security groups.
2. `DataStack` — S3 buckets (BlockPublicAccess.BLOCK_ALL, SSE-S3, enforceSSL, versioning on results),
   DynamoDB tables (docs/02 §4), SQS + DLQ.
3. `AuthStack` — Cognito user pool + app client + groups; SSM params.
4. `CoolComputeStack` — launch template (COOL AMI, IMDSv2 required, no SSH key, SSM agent role),
   user data: activate `/opt/cool/venvs/python_3.12`, `pip install` our wheel **without** OpenCV,
   install systemd units `vd-worker@.service` and `vd-mcp.service`; ASG min 1 / max 6, target tracking
   on `ApproximateNumberOfMessagesVisible` per instance; internal ALB for MCP (port 8765, SG restricted
   to the Fargate service SG).
5. `AppStack` — ECS cluster, Fargate service (ARM64, 0.5 vCPU / 1 GB) for API + agent, public ALB behind
   CloudFront; task role with only: DynamoDB tables, S3 prefixes, SQS send, `bedrock:InvokeModel`/
   `bedrock:Converse` on the chosen inference profile, SNS publish, SSM read.
6. `WebStack` — S3 + CloudFront distribution (OAC), behaviours: `/api/*` → ALB origin.
7. `ObservabilityStack` — dashboard + alarms (§5).
8. `BenchStack` (optional, temporary) — `c8g.4xlarge` COOL, `c8g.4xlarge` stock OpenCV 5,
   `c7i.4xlarge` stock OpenCV 5 (x86), each running `bench/run.sh` via SSM Run Command and uploading
   results to S3, then terminating.

Acceptance: `cdk synth` with `cdk-nag` (AwsSolutions pack) — fix or justify every finding in
`docs/DEVIATIONS.md`.

## 5. Observability and responsible operation
Custom metrics (namespace `VisionDoctor`, EMF): `ScanLatencyMs` (dims: check, instance_type, is_cool),
`OpMs` (op), `CamerasHealthy/Degraded/Failed`, `IncidentsOpened`, `AutoFixed`, `Escalated`,
`FalseAlarm`, `RepairVerifiedRate`, `AgentSteps`, `AgentTokens`, `GuardBlocks`, `PredictedFleetAccuracy`.
Alarms: DLQ depth > 0, worker p95 scan latency > SLO, `GuardBlocks` spike, Bedrock throttling, ASG at max.
Dashboard: fleet health, incident funnel, COOL vs. baseline latency, agent cost per incident.
Logs: structured JSON with `trace_id`, `camera_id`, `incident_id`; 30-day retention.
Responsible-use controls (put in REPORT.md): no face recognition; face blur on evidence; retention
lifecycles; human approval for physical actions; audit trail of every agent decision; Cognito roles.

## 6. COOL benchmark protocol (`bench/`) — reproducible
**Configurations (same vCPU count = 16, same OS where possible):**
| ID | Instance | OpenCV |
|---|---|---|
| A | c8g.4xlarge (Graviton4) | **COOL 3.1** (`/opt/cool/venvs/python_3.12`) |
| B | c8g.4xlarge (Graviton4) | stock OpenCV 5.0 built from source (default flags) or official wheel if one exists (**VERIFY**) |
| C | c7i.4xlarge (x86) | stock OpenCV 5.0, same build method as B |

**Workloads:**
1. *Micro*: `resize`, `cvtColor`, `GaussianBlur`, `Laplacian`, `Sobel`, `Canny`, `adaptiveThreshold`,
   `morphologyEx`, `findContours`, `warpPerspective`, `remap`, `calcHist`, `filter2D`, `dft`,
   `calcOpticalFlowPyrLK`, `findHomography` — on 1080p and 4K frames.
2. *End-to-end*: full `scan.py` on 12 simulated 1080p cameras → **scans/min**, p50/p95 latency.
3. *Fleet*: how many cameras one instance can check at 1 scan/min (saturation test).

**Method:** `cv2.setNumThreads(16)` everywhere; 10 warm-up + 50 timed reps per op; report median,
p95, coefficient of variation; 3 independent runs on fresh instances; same input frames (checked in by
SHA-256). Record environment JSON: instance type (IMDSv2), kernel, Python, `cv2.__version__`,
`cv2.__file__`, full `getBuildInformation()`.

**Outputs:** `results/bench/{A,B,C}/*.json`, `results/bench/summary.csv`, figures: speedup per op
(A vs B, A vs C), e2e throughput, and **cost per 1M camera-scans** =
`(EC2 $/h + COOL $/h) / scans_per_hour × 1e6` using on-demand prices fetched from the AWS Price List
API at run time (never hardcode prices).

**Evidence for the award:** environment JSON showing `/opt/cool` path + KleidiCV in build info,
CloudWatch `ScanLatencyMs{is_cool=true}` from the deployed fleet, and the summary table.

## 7. Cost guardrails
AWS Budgets alert at $50; `make down` = `cdk destroy --all` + reminder to cancel the Marketplace
subscription; BenchStack instances self-terminate after the run (shutdown behaviour = terminate).
