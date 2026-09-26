import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import config

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _year(publish_time):
    if not publish_time:
        return None
    try:
        ts = publish_time / 1000 if publish_time > 1e11 else publish_time
        return datetime.fromtimestamp(ts, tz=timezone.utc).year
    except (OverflowError, OSError, ValueError):
        return None


def _format_duration(ms):
    if not ms:
        return "--:--"
    total_sec = max(0, int(ms) // 1000)
    m = total_sec // 60
    s = total_sec % 60
    return f"{m:02d}:{s:02d}"


def _box_blur(arr, k=3):
    if k <= 1:
        return arr
    kernel = np.ones(k) / k
    arr = np.apply_along_axis(lambda m: np.convolve(m, kernel, "same"), 0, arr)
    arr = np.apply_along_axis(lambda m: np.convolve(m, kernel, "same"), 1, arr)
    return arr


def _kde(values, grid):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size < 2:
        return np.zeros_like(grid)
    std = float(values.std())
    bandwidth = 1.06 * (std if std > 0 else 1.0) * values.size ** (-0.2)
    diff = (grid[:, None] - values[None, :]) / bandwidth
    return np.exp(-0.5 * diff**2).sum(axis=1) / (values.size * bandwidth * math.sqrt(2.0 * math.pi))


def _extract_contours(bpm, energy, xlim, ylim):
    hist, xedges, yedges = np.histogram2d(bpm, energy, bins=[70, 50], range=[xlim, ylim])
    hist = _box_blur(hist, 3)
    if hist.max() <= 0:
        return []

    xc = (xedges[:-1] + xedges[1:]) / 2
    yc = (yedges[:-1] + yedges[1:]) / 2
    levels = np.linspace(hist.max() * 0.08, hist.max() * 0.9, 6)

    fig, ax = plt.subplots()
    cs = ax.contour(xc, yc, hist.T, levels=levels)
    contours = []
    for level_idx, level_segs in enumerate(cs.allsegs):
        for seg in level_segs:
            if len(seg) >= 2:
                contours.append({
                    "level": int(level_idx),
                    "coords": [[round(float(p[0]), 2), round(float(p[1]), 4)] for p in seg]
                })
    plt.close(fig)
    return contours


def _compute_marginals(bpm, energy, xlim, ylim):
    b_counts, b_edges = np.histogram(bpm, bins=70, range=xlim)
    b_centers = ((b_edges[:-1] + b_edges[1:]) / 2).round(2).tolist()
    b_counts = b_counts.tolist()
    b_grid = np.linspace(xlim[0], xlim[1], 128)
    b_kde = _kde(bpm, b_grid)
    b_max_cnt = max(max(b_counts), 1)
    b_kde_scaled = (
        (b_kde / b_kde.max() * b_max_cnt * 0.95).round(2).tolist()
        if b_kde.max() > 0
        else [0.0] * len(b_grid)
    )

    e_counts, e_edges = np.histogram(energy, bins=50, range=ylim)
    e_centers = ((e_edges[:-1] + e_edges[1:]) / 2).round(4).tolist()
    e_counts = e_counts.tolist()
    e_grid = np.linspace(ylim[0], ylim[1], 128)
    e_kde = _kde(energy, e_grid)
    e_max_cnt = max(max(e_counts), 1)
    e_kde_scaled = (
        (e_kde / e_kde.max() * e_max_cnt * 0.95).round(2).tolist()
        if e_kde.max() > 0
        else [0.0] * len(e_grid)
    )

    return {
        "bpm_hist": [[c, cnt] for c, cnt in zip(b_centers, b_counts)],
        "bpm_kde": [[round(float(x), 2), y] for x, y in zip(b_grid, b_kde_scaled)],
        "bpm_max": b_max_cnt,
        "energy_hist": [[round(float(cnt), 2), round(float(c), 4)] for c, cnt in zip(e_centers, e_counts)],
        "energy_kde": [[round(float(x), 2), round(float(y), 4)] for y, x in zip(e_grid, e_kde_scaled)],
        "energy_max": e_max_cnt,
    }


def _build_tracks_data(rows, raw=False):
    tracks = []
    for idx, r in enumerate(rows):
        d = dict(r)
        fj = {}
        if d.get("features_json"):
            try:
                fj = json.loads(d["features_json"])
            except Exception:
                fj = {}

        bpm_val = float(d["bpm_raw"] if raw else (d["bpm_final"] or d["bpm_raw"] or 0))
        energy_val = float(d["energy"] if d["energy"] is not None else 0)
        y = _year(d.get("publish_time"))

        full_raw = dict(d)
        full_raw["acoustic_features"] = fj
        full_raw["publish_year"] = y

        tracks.append({
            "index": idx,
            "id": d["id"],
            "name": d.get("name") or "未知曲目",
            "artists": d.get("artists") or "未知歌手",
            "album": d.get("album") or "",
            "bpm": round(bpm_val, 2),
            "bpm_final": round(float(d["bpm_final"]), 2) if d.get("bpm_final") is not None else None,
            "bpm_raw": round(float(d["bpm_raw"]), 2) if d.get("bpm_raw") is not None else None,
            "bpm_beat_this": round(float(d["bpm_beat_this"]), 2) if d.get("bpm_beat_this") is not None else None,
            "bpm_essentia": round(float(d["bpm_essentia"]), 2) if d.get("bpm_essentia") is not None else None,
            "bpm_method": d.get("bpm_method") or "unknown",
            "bpm_confidence": round(float(d["bpm_confidence"]), 3) if d.get("bpm_confidence") is not None else None,
            "energy": round(energy_val, 4),
            "duration_ms": d.get("duration_ms"),
            "duration_str": _format_duration(d.get("duration_ms")),
            "publish_time": d.get("publish_time"),
            "year": y,
            "fee": d.get("fee", 0),
            "source_br": d.get("source_br", 128000),
            "source_kind": d.get("source_kind") or "full",
            "analyzed_at": d.get("analyzed_at") or "",
            "features": {
                "onset_rate": round(float(fj.get("onset_rate", 0)), 2),
                "flux_rel": round(float(fj.get("flux_rel", 0)), 4),
                "centroid_hz": round(float(fj.get("centroid_hz", 0)), 1),
                "zcr": round(float(fj.get("zcr", 0)), 4),
                "rms": round(float(fj.get("rms", 0)), 4),
                "loudness_lufs": round(float(fj.get("loudness_lufs", -20)), 1),
                "norm_onset": round(float(fj.get("norm_onset", 0)), 3),
                "norm_flux": round(float(fj.get("norm_flux", 0)), 3),
                "norm_centroid": round(float(fj.get("norm_centroid", 0)), 3),
                "norm_zcr": round(float(fj.get("norm_zcr", 0)), 3),
                "norm_loudness": round(float(fj.get("norm_loudness", 0)), 3),
                "n_onsets": fj.get("n_onsets"),
                "n_beats": fj.get("n_beats"),
            },
            "raw_record": full_raw,
        })
    return tracks


def _aggregate_points(tracks):
    coord_map = {}
    for t in tracks:
        key = (round(t["bpm"], 1), round(t["energy"], 3))
        if key not in coord_map:
            coord_map[key] = []
        coord_map[key].append(t["index"])

    points = []
    for (bpm, energy), indices in coord_map.items():
        count = len(indices)
        years = [tracks[i]["year"] for i in indices if tracks[i]["year"] is not None]
        avg_year = round(float(np.mean(years))) if years else None

        j_x = []
        j_y = []
        if count == 1:
            j_x.append(bpm)
            j_y.append(energy)
        else:
            for i in range(count):
                angle = (2 * math.pi * i) / count
                r_x = 0.55
                r_y = 0.0075
                j_x.append(round(bpm + r_x * math.cos(angle), 2))
                j_y.append(round(energy + r_y * math.sin(angle), 4))

        points.append({
            "x": bpm,
            "y": energy,
            "count": count,
            "indices": indices,
            "year": avg_year,
            "source_kind": tracks[indices[0]]["source_kind"] if count == 1 else "mixed",
            "jitter_x": j_x,
            "jitter_y": j_y,
        })
    return points


def generate_html_content(rows, raw=False, by_year=False):
    tracks = _build_tracks_data(rows, raw=raw)
    points = _aggregate_points(tracks)

    bpm_arr = np.array([t["bpm"] for t in tracks], dtype=float)
    energy_arr = np.array([t["energy"] for t in tracks], dtype=float)
    xlim, ylim = config.BPM_AXIS, config.ENERGY_AXIS

    contours = _extract_contours(bpm_arr, energy_arr, xlim, ylim)
    marginals = _compute_marginals(bpm_arr, energy_arr, xlim, ylim)

    years = [t["year"] for t in tracks if t["year"] is not None]
    min_year = min(years) if years else 2000
    max_year = max(years) if years else 2026

    stats = {
        "total_tracks": len(tracks),
        "unique_points": len(points),
        "bpm_min": round(float(np.min(bpm_arr)), 1),
        "bpm_max": round(float(np.max(bpm_arr)), 1),
        "bpm_mean": round(float(np.mean(bpm_arr)), 1),
        "bpm_median": round(float(np.median(bpm_arr)), 1),
        "energy_min": round(float(np.min(energy_arr)), 3),
        "energy_max": round(float(np.max(energy_arr)), 3),
        "energy_mean": round(float(np.mean(energy_arr)), 3),
        "energy_median": round(float(np.median(energy_arr)), 3),
        "min_year": min_year,
        "max_year": max_year,
        "year_span": max_year - min_year + 1,
        "full_count": sum(1 for t in tracks if t["source_kind"] == "full"),
        "trial_count": sum(1 for t in tracks if t["source_kind"] == "trial"),
        "raw_mode": raw,
        "default_by_year": by_year,
        "bpm_guides": config.BPM_GUIDES,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    data_payload = {
        "tracks": tracks,
        "points": points,
        "contours": contours,
        "marginals": marginals,
        "stats": stats,
        "axis": {
            "bpm": list(xlim),
            "energy": list(ylim),
            "guides": config.BPM_GUIDES,
        },
    }

    json_str = json.dumps(data_payload, ensure_ascii=False).replace("</", "<\\/")

    html_tpl = (TEMPLATES_DIR / "report.html").read_text(encoding="utf-8")
    css_content = (TEMPLATES_DIR / "report.css").read_text(encoding="utf-8")
    js_content = (TEMPLATES_DIR / "report.js").read_text(encoding="utf-8")

    vendor_echarts = TEMPLATES_DIR / "vendor" / "echarts.min.js"
    if vendor_echarts.exists():
        echarts_js = vendor_echarts.read_text(encoding="utf-8")
    else:
        echarts_js = 'var s = document.createElement("script"); s.src = "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"; document.head.appendChild(s);'

    rendered = html_tpl.replace("/* __VENDOR_ECHARTS__ */", echarts_js)
    rendered = rendered.replace("/* __INLINE_CSS__ */", css_content)
    rendered = rendered.replace("/* __INLINE_JS__ */", js_content)
    rendered = rendered.replace("/* __DATA_JSON__ */", json_str)

    for k, v in stats.items():
        rendered = rendered.replace(f"{{{{ stats.{k} }}}}", str(v))

    return rendered


def generate(rows, out_path=None, raw=False, by_year=False):
    out_path = Path(out_path or config.HTML_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html_content = generate_html_content(rows, raw=raw, by_year=by_year)
    out_path.write_text(html_content, encoding="utf-8")
    print(f"[plot] 已导出交互式网页 {out_path} (n={len(rows)})")
    return out_path
