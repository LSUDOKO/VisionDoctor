"""Runtime configuration (env prefix ``VD_``).

Thresholds are calibrated by ``eval/calibrate.py`` on clean footage (docs/03 §9): each check's
alarm threshold is the 99.5th percentile of its clean-frame z-score distribution, written to
``results/calibration/thresholds.json``. The defaults below are the frozen calibrated values.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VD_", env_file=".env", extra="ignore")

    backend: Literal["local", "aws"] = "local"
    agent: Literal["policy", "bedrock"] = "policy"

    state_dir: Path = ROOT / "vd_state"
    models_dir: Path = ROOT / "models"
    data_dir: Path = ROOT / "data"
    results_dir: Path = ROOT / "results"

    # Working resolution for health checks (frames are downscaled to this width).
    work_width: int = 960
    tile_grid: int = 8
    reference_frames: int = 60

    # z-score → severity bands (docs/03 §2): sev = number of edges crossed.
    severity_edges: tuple[float, ...] = (2.0, 3.0, 4.0, 6.0, 9.0)
    # Minimum std floor (relative to mean) so near-constant reference metrics don't explode z.
    std_floor_rel: float = 0.05

    # Hysteresis: fault must persist this many consecutive scans before an incident opens.
    hysteresis_scans: int = 2
    incident_min_severity: int = 2

    # Repair bounds enforced by the guard (docs/03 §4).
    max_realign_rot_deg: float = 10.0
    max_realign_disp_frac: float = 0.12
    min_realign_inlier_ratio: float = 0.5
    gamma_range: tuple[float, float] = (0.5, 2.0)
    max_dehaze_omega: float = 0.95
    wb_gain_range: tuple[float, float] = (0.5, 2.0)
    max_denoise_h: float = 15.0
    max_repair_attempts: int = 2
    max_agent_steps: int = 12
    max_agent_tokens: int = 20000

    # Escalation: priority = predicted_drop * criticality; dispatch at/above this.
    p_dispatch: float = 0.6

    # AWS
    aws_region: str = "us-east-1"
    bedrock_model_id: str | None = None
    bedrock_model_ssm_param: str = "/visiondoctor/bedrock_model_id"
    s3_bucket: str | None = None
    ddb_prefix: str = "visiondoctor"
    sqs_queue_url: str | None = None
    sns_topic_arn: str | None = None
    mcp_url: str | None = None
    mcp_shared_secret: str | None = Field(default=None, repr=False)

    # API auth (Cognito). When unset the API runs open (local demo only).
    cognito_user_pool_id: str | None = None
    cognito_client_id: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
