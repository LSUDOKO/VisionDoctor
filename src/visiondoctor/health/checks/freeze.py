"""Freeze / dead stream (docs/03 §3.11).

Frozen = consecutive burst frames identical (mean absdiff < 0.5 and equal 64×36 thumbnail md5)
while the reference says the scene normally moves. Dead = uniform frame. Duration is tracked
across scans; > 20 s escalates to severity 5.
"""

from __future__ import annotations

import cv2

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.types import CheckResult

FROZEN_DIFF = 0.5
MIN_ACTIVITY = 0.8
FROZEN_ESCALATE_S = 20.0


def check(ctx: ScanContext) -> CheckResult:
    st = ctx.state
    diffs = [float(cv2.absdiff(a.gray, b.gray).mean()) for a, b in zip(ctx.feats, ctx.feats[1:], strict=False)]
    same_hash = len({f.thumb for f in ctx.feats}) == 1 and (st.last_thumb in (None, ctx.feats[0].thumb))
    frozen = bool(diffs) and max(diffs) < FROZEN_DIFF and same_hash
    dead = ctx.glob["std"] < 3.0
    activity = ctx.bucket.activity
    ev: dict[str, object] = {
        "max_frame_diff": max(diffs) if diffs else None,
        "ref_activity": activity,
        "dead": dead,
        "frozen": frozen,
    }
    st.last_thumb = ctx.feats[-1].thumb
    if dead:
        st.frozen_since = st.frozen_since or ctx.now
        return CheckResult("freeze", 5, ev | {"reason": "uniform_frame"})
    if not frozen:
        st.frozen_since = None
        return CheckResult("freeze", 0, ev)
    if activity < MIN_ACTIVITY:
        return CheckResult("freeze", 0, ev | {"reason": "static_scene"}, abstained=True)
    st.frozen_since = st.frozen_since or ctx.now
    dur = ctx.now - st.frozen_since
    ev["frozen_s"] = dur
    return CheckResult("freeze", 5 if dur >= FROZEN_ESCALATE_S else 4, ev)
