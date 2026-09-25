import json

from tqdm import tqdm

from . import audio, config, db, energy
from .bpm import BpmAnalyzer, finalize_bpm, load_overrides
from .ncm import NcmClient


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def run(
    limit=None,
    retry_errors=False,
    device="auto",
    keep_audio=False,
    aggressive=False,
    allow_trial=False,
):
    conn = db.connect()
    db.init_db(conn)
    rows = db.pending_tracks(conn, limit=limit, retry_errors=retry_errors)
    if not rows:
        print("[analyze] 没有待分析的曲目，请先执行 python run.py fetch")
        return
    client = NcmClient()
    client.ensure_server()
    if not client.cookie:
        print("[analyze] 提示：未登录时仅有可免费播放的歌曲能取到完整音频")
    else:
        vip = client.vip_info() or {}
        level = vip.get("redVipLevel") or vip.get("vipLevel")
        if level:
            print(f"[analyze] 已登录且检测到 VIP（等级 {level}），VIP 歌曲将获取完整音频")
        else:
            print("[analyze] 已登录但未检测到 VIP，VIP 歌曲可能只返回试听片段")
    config.TMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    overrides = load_overrides()
    analyzer = BpmAnalyzer(device=device)
    print(f"[analyze] 待分析 {len(rows)} 首，BPM 模型设备: {analyzer.device}")
    stats = {"analyzed": 0, "skipped": 0, "error": 0}
    progress = tqdm(total=len(rows), desc="analyze", unit="track")
    try:
        for batch_index, chunk in enumerate(_chunks(list(rows), config.URL_BATCH_SIZE), 1):
            if len(rows) > config.URL_BATCH_SIZE:
                progress.set_description(f"analyze batch {batch_index}")
            try:
                urls = audio.fetch_urls(client, [r["id"] for r in chunk])
            except Exception as exc:
                urls = {}
                print(f"[analyze] 批量获取播放地址失败: {exc}")
            for row in chunk:
                try:
                    track_id = row["id"]
                    raw_item = urls.get(track_id)
                    reason, url = audio.classify(raw_item)
                    if reason:
                        db.mark(conn, track_id, "skipped", reason=reason)
                        stats["skipped"] += 1
                        continue
                    item = raw_item or {}
                    truncated = audio.is_truncated(item, row["duration_ms"] or 0)
                    if truncated and not allow_trial:
                        db.mark(conn, track_id, "skipped", reason="trial_or_partial")
                        stats["skipped"] += 1
                        continue
                    dest = config.TMP_AUDIO_DIR / f"{track_id}.mp3"
                    try:
                        audio.download(url, dest)
                        x, sr = energy.load_audio(dest)
                        eng, feats = energy.analyze_energy(x, sr)
                        bpm_info = analyzer.analyze(x, sr)
                        final, method = finalize_bpm(bpm_info, aggressive=aggressive)
                        if track_id in overrides:
                            final, method = float(overrides[track_id]), "override"
                        features = dict(feats)
                        features.update({k: v for k, v in bpm_info.items()})
                        db.save_analysis(
                            conn,
                            track_id,
                            bpm_beat_this=bpm_info.get("bpm_beat_this"),
                            bpm_essentia=bpm_info.get("bpm_essentia"),
                            bpm_raw=bpm_info.get("bpm_raw"),
                            bpm_final=final,
                            bpm_method=method,
                            bpm_confidence=bpm_info.get("bpm_essentia_confidence"),
                            energy=eng,
                            features_json=json.dumps(features, ensure_ascii=False),
                            source_br=item.get("br"),
                            source_size=item.get("size"),
                            source_kind="trial" if truncated else "full",
                        )
                        stats["analyzed"] += 1
                    except KeyboardInterrupt:
                        raise
                    except Exception as exc:
                        db.mark(conn, track_id, "error", error=f"{type(exc).__name__}: {exc}")
                        stats["error"] += 1
                    finally:
                        if not keep_audio and dest.exists():
                            try:
                                dest.unlink()
                            except OSError:
                                pass
                finally:
                    progress.update(1)
    finally:
        progress.close()
    print(f"[analyze] 完成: {stats}")
    _write_review(conn)


def _write_review(conn, bpm_floor=95.0, disagree_ratio=0.05):
    import csv

    rows = conn.execute(
        "SELECT id, name, artists, bpm_raw, bpm_beat_this, bpm_essentia, bpm_final, bpm_method "
        "FROM tracks WHERE status='analyzed' AND bpm_raw IS NOT NULL"
    ).fetchall()
    flagged = []
    for row in rows:
        bt, es = row["bpm_beat_this"], row["bpm_essentia"]
        disagree = bool(bt and es and abs(bt - es) / max(bt, es) > disagree_ratio)
        if row["bpm_final"] < bpm_floor or disagree:
            flagged.append(row)
    path = config.DATA_DIR / "bpm_review.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "name", "artists", "bpm_beat_this", "bpm_essentia", "bpm_raw", "bpm_final", "bpm_method"])
        for row in flagged:
            writer.writerow(
                [row["id"], row["name"], row["artists"], row["bpm_beat_this"], row["bpm_essentia"], row["bpm_raw"], row["bpm_final"], row["bpm_method"]]
            )
    if flagged:
        print(f"[analyze] {len(flagged)} 首低 BPM 或双引擎分歧曲目已写入 {path}（可人工复核后写入 bpm_overrides.csv）")
