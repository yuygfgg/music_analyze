import random
import time

import requests

from . import config


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def fetch_urls(client, ids):
    out = {}
    for batch in _chunks(list(ids), config.URL_BATCH_SIZE):
        resp = client.request(
            "/song/url/v1",
            {"id": ",".join(str(i) for i in batch), "level": config.AUDIO_LEVEL},
        )
        for item in resp.get("data", []):
            out[item["id"]] = item
        time.sleep(random.uniform(config.REQUEST_MIN_DELAY, config.REQUEST_MAX_DELAY))
    return out


def classify(item):
    if not item:
        return "unavailable", None
    code = item.get("code")
    if code not in (200, None):
        return f"api_code_{code}", None
    url = item.get("url")
    if not url:
        if item.get("freeTrialInfo"):
            return "trial_only", None
        return "no_url", None
    return None, url


def is_trial(item):
    return bool(item.get("freeTrialInfo"))


def is_truncated(item, duration_ms):
    size = item.get("size") or 0
    br = item.get("br") or 0
    if not (size and br and duration_ms):
        return False
    expected = duration_ms / 1000.0 * br / 8.0
    return size < expected * 0.6


def download(url, dest, timeout=180):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Referer": "https://music.163.com/",
    }
    with requests.get(url, stream=True, headers=headers, timeout=timeout) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                if chunk:
                    fh.write(chunk)
    return dest
