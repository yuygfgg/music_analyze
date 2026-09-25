import math

import essentia.standard as es
import numpy as np
import soundfile as sf
import soxr

from . import config


def load_audio(path):
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = data.mean(axis=1).astype(np.float32)
    if sr != config.SAMPLE_RATE:
        mono = soxr.resample(mono, sr, config.SAMPLE_RATE).astype(np.float32)
        sr = config.SAMPLE_RATE
    return mono, sr


def _sigmoid(value, center, scale):
    return 1.0 / (1.0 + math.exp(-(value - center) / scale))


def integrated_loudness(x):
    try:
        stereo = np.stack([x, x], axis=1).astype(np.float32)
        outs = es.LoudnessEBUR128()(stereo)
        return float(outs[2])
    except Exception:
        rms = float(np.sqrt(np.mean(x**2)) + 1e-12)
        return 20.0 * math.log10(rms)


def spectral_features(x, sr):
    frame = 2048
    hop = 1024
    if len(x) < frame * 2:
        return {"flux_rel": 0.0, "centroid_hz": 0.0, "zcr": 0.0, "rms": float(np.sqrt(np.mean(x**2)))}
    win = np.hanning(frame).astype(np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(x, frame)[::hop] * win
    mag = np.abs(np.fft.rfft(frames, axis=1))
    freqs = np.fft.rfftfreq(frame, 1.0 / sr)
    total = mag.sum(axis=1) + 1e-9
    centroid = float(np.mean((mag * freqs).sum(axis=1) / total))
    diff = np.diff(mag, axis=0)
    np.maximum(diff, 0.0, out=diff)
    flux = float(np.mean(diff.sum(axis=1) / (total[1:] + 1e-9)))
    zcr = float(np.mean((x[:-1] * x[1:]) < 0))
    rms = float(np.sqrt(np.mean(x**2)))
    return {"flux_rel": flux, "centroid_hz": centroid, "zcr": zcr, "rms": rms}


def feature_maps(feats):
    values = {
        "onset": feats["onset_rate"],
        "flux": feats["flux_rel"],
        "centroid": math.log2(max(feats["centroid_hz"], 1.0)),
        "zcr": feats["zcr"],
    }
    return {k: _sigmoid(values[k], *config.ENERGY_MAPS[k]) for k in config.ENERGY_MAPS}


def energy_from_features(feats):
    norm = feature_maps(feats)
    raw = sum(config.ENERGY_WEIGHTS[k] * norm[k] for k in config.ENERGY_WEIGHTS)
    anchors_x = [point[0] for point in config.ENERGY_ANCHORS]
    anchors_y = [point[1] for point in config.ENERGY_ANCHORS]
    return float(np.interp(raw, anchors_x, anchors_y)), norm


def analyze_energy(x, sr):
    loudness = integrated_loudness(x)
    feats = spectral_features(x, sr)
    onsets, onset_rate = es.OnsetRate()(x)
    feats["onset_rate"] = float(onset_rate)
    feats["n_onsets"] = int(len(onsets))
    feats["loudness_lufs"] = loudness
    energy, norm = energy_from_features(feats)
    feats.update({f"norm_{k}": v for k, v in norm.items()})
    return energy, feats
