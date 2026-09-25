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


def _norm(value, lo, hi):
    if hi <= lo:
        return 0.0
    return float(min(1.0, max(0.0, (value - lo) / (hi - lo))))


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


def analyze_energy(x, sr):
    loudness = integrated_loudness(x)
    feats = spectral_features(x, sr)
    onsets, onset_rate = es.OnsetRate()(x)
    feats["onset_rate"] = float(onset_rate)
    feats["n_onsets"] = int(len(onsets))
    feats["loudness_lufs"] = loudness
    weights = config.ENERGY_WEIGHTS
    norm = {
        "loudness": _norm(loudness, *config.LOUDNESS_RANGE),
        "onset": _norm(onset_rate, 0.0, config.ONSET_RATE_MAX),
        "flux": _norm(feats["flux_rel"], 0.0, config.FLUX_MAX),
        "centroid": _norm(
            math.log2(max(feats["centroid_hz"], 1.0)),
            math.log2(config.CENTROID_RANGE_HZ[0]),
            math.log2(config.CENTROID_RANGE_HZ[1]),
        ),
    }
    feats.update({f"norm_{k}": v for k, v in norm.items()})
    energy = sum(weights[k] * norm[k] for k in weights)
    return float(min(1.0, max(0.0, energy))), feats
