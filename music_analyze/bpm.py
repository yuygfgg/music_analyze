import csv

import essentia.standard as es
import numpy as np

from . import config


def median_bpm(beats):
    beats = np.asarray(beats, dtype=float)
    if beats.size < 3:
        return None
    intervals = np.diff(beats)
    intervals = intervals[intervals > 1e-3]
    if intervals.size == 0:
        return None
    return float(60.0 / np.median(intervals))


class BpmAnalyzer:
    def __init__(self, device="auto", checkpoint="final0"):
        import torch
        from beat_this.inference import Audio2Beats

        if device == "auto":
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = device
        self.model = Audio2Beats(checkpoint_path=checkpoint, device=device)

    def analyze(self, x, sr):
        import torch

        spect = self.model.signal2spect(x, sr)
        beat_logits, downbeat_logits = self.model.spect2frames(spect)
        beats, _ = self.model.frames2beats(beat_logits, downbeat_logits)
        beats = np.asarray(beats, dtype=float)
        bpm_bt = median_bpm(beats)
        midpoint_prob = midpoint_ratio = None
        if beats.size >= 4:
            probs = torch.sigmoid(beat_logits).detach().cpu().numpy()
            idx = np.clip(np.round(beats * 50).astype(int), 0, probs.size - 1)
            mids = (idx[:-1] + idx[1:]) // 2
            if mids.size:
                beat_prob = float(np.median(probs[idx]))
                mid_prob = float(np.median(probs[mids]))
                midpoint_prob = mid_prob
                midpoint_ratio = mid_prob / max(beat_prob, 1e-6)
        bpm_es = confidence = None
        try:
            outs = es.RhythmExtractor2013(method="multifeature")(x)
            bpm_es = float(outs[0])
            confidence = float(outs[2])
        except Exception:
            pass
        raw = bpm_bt if bpm_bt else bpm_es
        return {
            "bpm_beat_this": bpm_bt,
            "bpm_essentia": bpm_es,
            "bpm_essentia_confidence": confidence,
            "bpm_raw": raw,
            "midpoint_prob": midpoint_prob,
            "midpoint_ratio": midpoint_ratio,
            "n_beats": int(beats.size),
        }


def finalize_bpm(info, aggressive=False):
    bpm = info.get("bpm_raw")
    if not bpm:
        return None, "none"
    bpm = float(bpm)
    method = "beat_this" if info.get("bpm_beat_this") else "essentia"
    if bpm < config.DOUBLE_LOWER_BOUND and 2.0 * bpm <= config.DOUBLE_UPPER_BOUND:
        ratio = info.get("midpoint_ratio")
        prob = info.get("midpoint_prob") or 0.0
        midpoint_ok = (
            ratio is not None
            and ratio >= config.MIDPOINT_PROB_RATIO
            and prob >= config.MIDPOINT_MIN_PROB
        )
        if midpoint_ok:
            bpm *= 2.0
            method += "+doubled"
        elif aggressive:
            bpm *= 2.0
            method += "+doubled(forced)"
    while bpm > config.BPM_MAX:
        bpm /= 2.0
        method += "+halved"
    return float(bpm), method


def load_overrides():
    path = config.OVERRIDES_PATH
    if not path.exists():
        return {}
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                out[int(row["id"])] = float(row["bpm"])
            except (KeyError, TypeError, ValueError):
                continue
    return out
