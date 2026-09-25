import csv
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

from . import config, db


def _box_blur(arr, k=3):
    if k <= 1:
        return arr
    kernel = np.ones(k) / k
    arr = np.apply_along_axis(lambda m: np.convolve(m, kernel, "same"), 0, arr)
    arr = np.apply_along_axis(lambda m: np.convolve(m, kernel, "same"), 1, arr)
    return arr


def _year(publish_time):
    if not publish_time:
        return None
    try:
        return datetime.fromtimestamp(publish_time, tz=timezone.utc).year
    except (OverflowError, OSError, ValueError):
        return None


def run(raw=False, by_year=False):
    conn = db.connect()
    rows = conn.execute(
        "SELECT * FROM tracks WHERE status='analyzed' AND bpm_final IS NOT NULL "
        "AND energy IS NOT NULL ORDER BY id"
    ).fetchall()
    if not rows:
        print("[plot] 没有已分析的数据，请先执行 python run.py analyze")
        return

    bpm = np.array([(r["bpm_raw"] if raw else r["bpm_final"]) for r in rows], dtype=float)
    energy = np.array([r["energy"] for r in rows], dtype=float)
    years = [_year(r["publish_time"]) for r in rows]
    use_years = by_year and all(y is not None for y in years)

    xlim, ylim = config.BPM_AXIS, config.ENERGY_AXIS
    fig = plt.figure(figsize=(10, 8))
    gs = GridSpec(4, 4, figure=fig, hspace=0.06, wspace=0.06)
    ax = fig.add_subplot(gs[1:, :-1])
    ax_top = fig.add_subplot(gs[0, :-1], sharex=ax)
    ax_right = fig.add_subplot(gs[1:, -1], sharey=ax)

    hist, xedges, yedges = np.histogram2d(bpm, energy, bins=[70, 50], range=[xlim, ylim])
    hist = _box_blur(hist, 3)
    if hist.max() > 0:
        xc = (xedges[:-1] + xedges[1:]) / 2
        yc = (yedges[:-1] + yedges[1:]) / 2
        grid_x, grid_y = np.meshgrid(xc, yc, indexing="ij")
        levels = np.linspace(hist.max() * 0.08, hist.max() * 0.9, 6)
        ax.contour(grid_x, grid_y, hist, levels=levels, colors="#0b3d66", linewidths=0.7, alpha=0.5)

    if use_years:
        sc = ax.scatter(
            bpm,
            energy,
            c=np.array([y for y in years], dtype=float),
            cmap="viridis",
            s=18,
            alpha=0.85,
            linewidths=0,
        )
        fig.colorbar(sc, ax=ax_right, label="发行年份")
    else:
        ax.scatter(bpm, energy, s=18, alpha=0.55, color="#1f77b4", linewidths=0)

    for guide in config.BPM_GUIDES:
        if xlim[0] <= guide <= xlim[1]:
            for target in (ax, ax_top):
                target.axvline(guide, color="grey", ls="--", lw=0.6, alpha=0.35)

    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xlabel("BPM")
    ax.set_ylabel("Energy")
    ax_top.hist(bpm, bins=70, range=xlim, color="#1f77b4", alpha=0.7)
    ax_right.hist(energy, bins=50, range=ylim, orientation="horizontal", color="#1f77b4", alpha=0.7)
    ax_top.tick_params(labelbottom=False)
    ax_right.tick_params(labelleft=False)
    ax_top.set_ylabel("count")
    ax_right.set_xlabel("count")
    title = "BPM x Energy" + (" (raw)" if raw else "")
    fig.suptitle(f"{title}   n={len(rows)}", fontsize=13)
    fig.savefig(config.PLOT_PATH, bbox_inches="tight", dpi=200)
    plt.close(fig)
    print(f"[plot] 已保存 {config.PLOT_PATH} (n={len(rows)})")

    with open(config.CSV_PATH, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "id",
                "name",
                "artists",
                "album",
                "bpm_raw",
                "bpm_final",
                "bpm_method",
                "bpm_beat_this",
                "bpm_essentia",
                "energy",
                "duration_ms",
                "publish_time",
                "fee",
                "source_br",
                "source_kind",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r["id"],
                    r["name"],
                    r["artists"],
                    r["album"],
                    r["bpm_raw"],
                    r["bpm_final"],
                    r["bpm_method"],
                    r["bpm_beat_this"],
                    r["bpm_essentia"],
                    r["energy"],
                    r["duration_ms"],
                    r["publish_time"],
                    r["fee"],
                    r["source_br"],
                    r["source_kind"],
                ]
            )
    print(f"[plot] 已导出 {config.CSV_PATH}")
