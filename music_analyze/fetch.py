import random
import time

from . import config, db
from .ncm import NcmError


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _sleep():
    time.sleep(random.uniform(config.REQUEST_MIN_DELAY, config.REQUEST_MAX_DELAY))


def fetch_library(client, conn, uid=None, progress=True):
    db.init_db(conn)
    if uid is None:
        account = client.account()
        if not account:
            raise NcmError("未登录，无法确定 uid；请先执行 python run.py login")
        uid = account["userId"]
    resp = client.request("/likelist", {"uid": uid})
    ids = resp.get("ids") or []
    if not ids:
        print("没有获取到收藏歌曲")
        return 0
    print(f"收藏歌曲共 {len(ids)} 首，开始拉取元数据")
    tracks = []
    for batch in _chunks(ids, config.DETAIL_BATCH_SIZE):
        resp = client.request("/song/detail", {"ids": ",".join(str(i) for i in batch)})
        for song in resp.get("songs", []):
            tracks.append(
                {
                    "id": song["id"],
                    "name": song.get("name", ""),
                    "artists": " / ".join(a.get("name", "") for a in song.get("ar", [])),
                    "album": (song.get("al") or {}).get("name", ""),
                    "duration_ms": song.get("dt"),
                    "publish_time": (song.get("publishTime") or 0) // 1000 or None,
                    "fee": song.get("fee"),
                }
            )
        if progress:
            print(f"  已获取 {len(tracks)}/{len(ids)}")
        _sleep()
    db.upsert_tracks(conn, tracks)
    missing = len(ids) - len(tracks)
    print(f"入库 {len(tracks)} 首" + (f"，{missing} 首详情缺失" if missing else ""))
    return len(tracks)
