"""Download clinical vitiligo photos from Wikimedia Commons with per-file license/attribution.

Uses the MediaWiki API only. Keeps free licenses that allow commercial use
(CC0, public domain, CC BY, CC BY-SA — the latter flagged ``share_alike``);
skips NC/ND/unknown, genital/intimate images (out of scope per the annotator
guideline), portraits, animals and diagrams.

Usage:
    python -I scripts/harvest_commons_vitiligo_images.py --out data/external/commons_vitiligo
"""

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = "SubSkin-research-harvester/1.0 (vitiligo segmentation dataset; contact via subskin.cn)"
CATEGORIES = ["Category:Vitiligo", "Category:People with vitiligo"]
SKIP_NAME = re.compile(
    r"penis|scrot|genital|intim|anus|vulva|geschlecht|erection|leopard girl|driver|cannes|"
    r"macaca|rottweiler|horse|baliuag|baloch|campinas|india \(|hen|svg|gif|ogg|\.png$|plate|treatise|"
    r"newspaper|stages in development|script|vkhs|corebereich",
    re.I,
)
FREE = re.compile(r"^(cc0|public domain|pd|cc by(-sa)? [0-9.]+( [a-z]{2})?|cc-by(-sa)?-[0-9.]+)", re.I)


def fetch(url: str) -> bytes:
    """GET with polite backoff on 429/5xx (Wikimedia rate limits)."""
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503) or attempt == 5:
                raise
            time.sleep(15 * (attempt + 1))
    raise RuntimeError("unreachable")


def api(params: dict) -> dict:
    return json.loads(fetch(API + "?" + urllib.parse.urlencode({**params, "format": "json"})))


def members(category: str) -> list:
    out, cont = [], {}
    while True:
        data = api({"action": "query", "list": "categorymembers", "cmtitle": category,
                    "cmtype": "file", "cmlimit": 500, **cont})
        out += [m["title"] for m in data["query"]["categorymembers"]]
        if "continue" not in data:
            return out
        cont = data["continue"]


def strip(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html or "").split())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-width", type=int, default=1920)  # a standard thumbnail step
    args = parser.parse_args()
    out = Path(args.out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    titles = sorted({t for c in CATEGORIES for t in members(c)})
    previous = out / "manifest.json"
    kept = json.loads(previous.read_text())["kept"] if previous.exists() else []  # resume after rate limits
    done = {k["title"] for k in kept}
    skipped = []
    for title in titles:
        if title in done:
            continue
        if SKIP_NAME.search(title):
            skipped.append({"title": title, "reason": "out_of_scope_or_not_clinical"})
            continue
        page = next(iter(api({"action": "query", "titles": title, "prop": "imageinfo",
                              "iiprop": "url|size|sha1|extmetadata|mime", "iiurlwidth": args.max_width})
                         ["query"]["pages"].values()))
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        license_name = strip(meta.get("LicenseShortName", {}).get("value", ""))
        if not FREE.match(license_name) or "nc" in license_name.lower().split("-") or " nd" in license_name.lower():
            skipped.append({"title": title, "reason": "license:" + license_name})
            continue
        if info.get("mime") not in ("image/jpeg", "image/png", "image/webp") or min(info.get("width", 0), info.get("height", 0)) < 500:
            skipped.append({"title": title, "reason": "format_or_small"})
            continue
        url = info.get("thumburl") or info["url"]
        data = fetch(url)
        name = re.sub(r"[^A-Za-z0-9._-]", "_", title.split(":", 1)[1])
        (out / "images" / name).write_bytes(data)
        kept.append({
            "file": name,
            "title": title,
            "page_url": info.get("descriptionurl"),
            "license": license_name,
            "license_url": strip(meta.get("LicenseUrl", {}).get("value", "")),
            "share_alike": "sa" in license_name.lower(),
            "artist": strip(meta.get("Artist", {}).get("value", ""))[:300],
            "description": strip(meta.get("ImageDescription", {}).get("value", ""))[:800],
            "original_size": [info.get("width"), info.get("height")],
            "sha256": hashlib.sha256(data).hexdigest(),
        })
        time.sleep(10)
        (out / "manifest.json").write_text(json.dumps({"kept": kept, "skipped": skipped}, ensure_ascii=False, indent=1))
    (out / "manifest.json").write_text(json.dumps({"kept": kept, "skipped": skipped}, ensure_ascii=False, indent=1))
    print("kept", len(kept), "skipped", len(skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
