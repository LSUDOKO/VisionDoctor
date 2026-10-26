"""YOLOX-S object detector on the OpenCV 5 DNN engine (model: huggingface.co/opencv/object_detection_yolox).

Pre/post-processing follows the model card's reference code: RGB, letterbox to 640×640 with
pad value 114, no normalisation; decode grid/stride anchors; class-aware NMS
(``cv2.dnn.NMSBoxesBatched``). The engine is requested explicitly (``ENGINE_NEW``) and the one
that actually loaded is recorded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from visiondoctor.config import get_settings
from visiondoctor.observability.metrics import timer

COCO_OF_INTEREST = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
GROUP = {0: "person", 1: "vehicle", 2: "vehicle", 3: "vehicle", 5: "vehicle", 7: "vehicle"}
INPUT = 640
STRIDES = (8, 16, 32)


def _anchors() -> tuple[np.ndarray, np.ndarray]:
    grids, strides = [], []
    for s in STRIDES:
        n = INPUT // s
        xv, yv = np.meshgrid(np.arange(n), np.arange(n))
        grids.append(np.stack((xv, yv), 2).reshape(-1, 2))
        strides.append(np.full((n * n, 1), s))
    return np.concatenate(grids).astype(np.float32), np.concatenate(strides).astype(np.float32)


@dataclass
class Detections:
    boxes: np.ndarray  # (N,4) x1,y1,x2,y2 in source pixels
    scores: np.ndarray  # (N,)
    classes: np.ndarray  # (N,) COCO ids

    def __len__(self) -> int:
        return len(self.scores)

    def filter(self, conf: float) -> Detections:
        k = self.scores >= conf
        return Detections(self.boxes[k], self.scores[k], self.classes[k])


class Detector:
    def __init__(self, model_path: Path | None = None, conf: float = 0.25, nms: float = 0.5) -> None:
        path = model_path or get_settings().models_dir / "yolox.onnx"
        if not Path(path).exists():
            raise FileNotFoundError(f"{path} missing — run scripts/download_models.sh")
        want = os.environ.get("VD_DNN_ENGINE", "ENGINE_NEW")
        try:
            self.net = cv2.dnn.readNetFromONNX(str(path), engine=getattr(cv2.dnn, want))
            self.engine = want
        except cv2.error:
            self.net = cv2.dnn.readNetFromONNX(str(path), engine=cv2.dnn.ENGINE_AUTO)
            self.engine = "ENGINE_AUTO"
        self.conf, self.nms = conf, nms
        self.grids, self.strides = _anchors()

    def detect(self, bgr: np.ndarray) -> Detections:
        h, w = bgr.shape[:2]
        r = min(INPUT / h, INPUT / w)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        pad = np.full((INPUT, INPUT, 3), 114, np.float32)
        pad[: int(h * r), : int(w * r)] = cv2.resize(rgb, (int(w * r), int(h * r)), interpolation=cv2.INTER_LINEAR)
        blob = pad.transpose(2, 0, 1)[None]
        with timer("dnn_forward"):
            self.net.setInput(blob)
            out = self.net.forward()
        dets = out[0] if out.ndim == 3 else out
        xy = (dets[:, :2] + self.grids) * self.strides
        wh = np.exp(dets[:, 2:4]) * self.strides
        boxes = np.concatenate([xy - wh / 2, xy + wh / 2], axis=1) / r
        scores_all = dets[:, 4:5] * dets[:, 5:]
        cls = scores_all.argmax(1)
        score = scores_all.max(1)
        keep = np.isin(cls, list(COCO_OF_INTEREST)) & (score >= self.conf)
        boxes, score, cls = boxes[keep], score[keep], cls[keep]
        if len(score) == 0:
            return Detections(np.zeros((0, 4)), np.zeros(0), np.zeros(0, int))
        with timer("NMSBoxesBatched"):
            idx = cv2.dnn.NMSBoxesBatched(boxes.tolist(), score.tolist(), cls.tolist(), self.conf, self.nms)
        idx = np.asarray(idx, int).ravel()
        b = boxes[idx]
        b[:, [0, 2]] = b[:, [0, 2]].clip(0, w)
        b[:, [1, 3]] = b[:, [1, 3]].clip(0, h)
        return Detections(b, score[idx], cls[idx])


_DETECTOR: Detector | None = None


def get_detector() -> Detector:
    global _DETECTOR
    if _DETECTOR is None:
        _DETECTOR = Detector()
    return _DETECTOR
