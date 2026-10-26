"""Fault description for technicians (docs/03 §8).

Primary: PaliGemma2-3B through the OpenCV 5 DNN VLM path (cf. samples/dnn/vlm_inference.py:
SigLIP image encoder + embedding + Gemma decoder ONNX parts, ``cv.dnn.Tokenizer``), run only
on escalations, cached by region hash, guarded by a timeout. It needs ~12 GB RAM, so it is
enabled only when the model files exist (``VD_VLM=1`` download) on a large (m8g) instance.
Fallback (always available): a rule-based description from the check evidence, so an
incident never blocks on the VLM.
"""

from __future__ import annotations

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutTimeout
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from visiondoctor.config import get_settings

VLM_TIMEOUT_S = 60.0
_pool = ThreadPoolExecutor(max_workers=1)
_cache: dict[str, dict[str, Any]] = {}

TEMPLATES = {
    "drift": "Camera view has shifted {rot:.1f}° and {disp:.1f}% of the frame; mount or PTZ preset moved.",
    "vibration": "Image shakes by ~{jit:.1f}px between frames; check mount and nearby machinery/wind.",
    "haze": "Image is veiled and low-contrast ({cl:.0%} contrast loss){where}; likely fog or condensation in the dome.",
    "glare": "Bright flare covers {gf:.0%} of the view; a light source is shining into the lens.",
    "exposure": "Picture is {dir}-exposed (luminance {dl:+.0%} vs normal); check iris/gain settings or lighting.",
    "occlusion": "Something is blocking {of:.0%} of the view in the {pos} of the frame (tape, sign, foliage or object).",
    "smudge": "Blurry smear on the lens covering {sf:.0%} of textured areas in the {pos}{web}; clean the lens.",
    "color_cast": "Strong colour cast (ΔLab {ld:.1f}){hint}.",
    "noise": "Image is grainy ({nr:.1f}× normal sensor noise); low light or failing sensor.",
    "sharpness": "Whole image is out of focus ({loss:.0%} sharpness loss); refocus the lens.",
    "freeze": "Video stream is frozen or dead ({why}); check power, network and encoder.",
}


def _position(bbox: list[int] | None, w: int, h: int) -> str:
    if not bbox:
        return "frame"
    x, y, bw, bh = bbox
    cx, cy = (x + bw / 2) / w, (y + bh / 2) / h
    v = "upper" if cy < 0.33 else "lower" if cy > 0.66 else "middle"
    hz = "left" if cx < 0.33 else "right" if cx > 0.66 else "centre"
    return f"{v} {hz}"


def rule_based(fault: str, ev: dict[str, Any], bbox: list[int] | None, shape: tuple[int, int]) -> str:
    h, w = shape
    pos = _position(bbox, w, h)
    vals = {
        "rot": abs(float(ev.get("rot_deg", 0))),
        "disp": float(ev.get("disp_pct_diag", 0)),
        "jit": float(ev.get("jitter_px", 0)),
        "cl": float(ev.get("contrast_loss", 0)),
        "where": "" if ev.get("uniform", True) else " in patches",
        "gf": float(ev.get("glare_frac", 0)),
        "dir": ev.get("direction", "under"),
        "dl": float(ev.get("lum_delta_rel", 0)),
        "of": float(ev.get("occluded_frac", 0)),
        "sf": float(ev.get("smudged_frac", 0)),
        "web": " (thin bright strands: possible spider web)" if ev.get("spider_web_hint") else "",
        "ld": float(ev.get("lab_dist", 0)),
        "hint": f"; {ev['hint']}" if ev.get("hint") else "",
        "nr": float(ev.get("ratio", 1)),
        "loss": float(ev.get("loss", 0)),
        "why": "uniform frame" if ev.get("dead") else f"no change for {float(ev.get('frozen_s', 0)):.0f}s",
        "pos": pos,
    }
    return TEMPLATES.get(fault, "Camera fault: {f}").format(**vals, f=fault)


@lru_cache(maxsize=1)
def _vlm_parts() -> dict[str, Path] | None:
    d = Path(get_settings().models_dir) / "paligemma2"
    parts = {k: d / f for k, f in {"siglip": "siglip.onnx", "embedding": "embedding.onnx",
                                   "gemma": "gemma.onnx", "tokenizer": "tokenizer.json"}.items()}
    return parts if all(p.exists() for p in parts.values()) else None


def _vlm_caption(crop: np.ndarray, prompt: str = "cap en\n") -> str:  # pragma: no cover - needs 12 GB model
    """Greedy PaliGemma2 decoding following OpenCV's samples/dnn/vlm_inference.py."""
    parts = _vlm_parts()
    assert parts is not None
    tok = cv2.dnn.Tokenizer.load(str(parts["tokenizer"]))
    siglip = cv2.dnn.readNetFromONNX(str(parts["siglip"]))
    embed = cv2.dnn.readNetFromONNX(str(parts["embedding"]))
    gemma = cv2.dnn.readNetFromONNX(str(parts["gemma"]))
    img = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB), (224, 224)).astype(np.float32) / 127.5 - 1.0
    siglip.setInput(img.transpose(2, 0, 1)[None])
    img_emb = siglip.forward()
    ids = list(tok.encode(prompt))
    out_ids: list[int] = []
    for _ in range(24):
        embed.setInput(np.array([ids + out_ids], np.int64))
        txt_emb = embed.forward()
        gemma.setInput(np.concatenate([img_emb, txt_emb], axis=1))
        logits = gemma.forward()
        nxt = int(np.argmax(logits[0, -1]))
        if nxt == 1:  # <eos>
            break
        out_ids.append(nxt)
    return str(tok.decode(out_ids)).strip()


def describe(fault: str, evidence: dict[str, Any], frame: np.ndarray, bbox: list[int] | None) -> dict[str, Any]:
    """Caption the (already face-blurred) fault region; never raises."""
    t0 = time.perf_counter()
    h, w = frame.shape[:2]
    text = rule_based(fault, evidence, bbox, (h, w))
    result: dict[str, Any] = {"caption": text, "model": "rule-based (VLM unavailable)", "latency_ms": 0.0}
    if _vlm_parts() is not None:
        x, y, bw, bh = bbox or [0, 0, w, h]
        crop = frame[y : y + bh, x : x + bw] if bw > 8 and bh > 8 else frame
        key = hashlib.sha1(cv2.resize(crop, (32, 32)).tobytes()).hexdigest()
        if key in _cache:
            return _cache[key]
        try:
            cap = _pool.submit(_vlm_caption, crop).result(timeout=VLM_TIMEOUT_S)
            result = {"caption": cap, "rule_based": text, "model": "paligemma2-3b (OpenCV 5 DNN)"}
        except FutTimeout:
            result["model"] = "rule-based (VLM timeout)"
        except Exception as e:  # noqa: BLE001 - VLM is best-effort by design
            result["model"] = f"rule-based (VLM error: {type(e).__name__})"
        _cache[key] = result
    result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return result
