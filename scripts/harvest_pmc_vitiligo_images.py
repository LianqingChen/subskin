"""Harvest clinical vitiligo photographs from the PMC Open Access subset (CC BY / CC0 only).

Uses only NCBI-sanctioned automated channels: E-utilities (search) and the
PMC Cloud Service bucket (``pmc-oa-opendata``, anonymous HTTPS). Every image
keeps attribution (citation, DOI, license, figure caption) so CC BY terms can
be honoured. Figures are filtered by caption: clinical photos in, histology /
dermoscopy / charts / animal work out. Output is untrusted data — open it
with ``python -I`` and never execute anything from it.

Usage:
    python -I scripts/harvest_pmc_vitiligo_images.py --out data/external/pmc_vitiligo [--limit 900]
"""

import argparse
import hashlib
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
BUCKET = "https://pmc-oa-opendata.s3.amazonaws.com"
TERM = 'vitiligo[title] AND open_access[filter] AND ("cc by license"[filter] OR "cc0 license"[filter])'
ALLOWED_LICENSES = {"CC BY", "CC0"}
UA = "SubSkin-research-harvester/1.0 (vitiligo segmentation dataset; contact via subskin.cn)"

INCLUDE = re.compile(
    r"vitiligo|depigment|hypopigment|patch|macule|lesion|repigment|before|after|baseline|"
    r"clinical (photo|image|picture|appearance)|photograph|white (patch|spot)|leukoderma|halo",
    re.I,
)
EXCLUDE = re.compile(
    r"histolog|histopath|immunohisto|immunofluoresc|h&e|hematoxylin|haematoxylin|stain|biopsy section|"
    r"microscop|dermoscop|dermatoscop|trichoscop|confocal|western blot|blot|pcr|flow cytometr|"
    r"mouse|mice|murine|rat |zebrafish|cell line|melanocytes? culture|in vitro|"
    r"flow ?chart|flowchart|schematic|diagram|pathway|mechanism|graph|plot|bar chart|forest plot|"
    r"kaplan|prisma|network|heat ?map|venn|chart|algorithm|questionnaire|survey|table|"
    r"funnel|roc curve|ultrasound|mri|ct scan|retina|fundus|oct\b|eeg",
    re.I,
)


def get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def search_ids(limit: int) -> list:
    ids, start = [], 0
    while len(ids) < limit:
        query = urllib.parse.urlencode(
            {"db": "pmc", "term": TERM, "retmax": 500, "retstart": start, "retmode": "json"}
        )
        page = json.loads(get(EUTILS + "?" + query))["esearchresult"]
        batch = page.get("idlist", [])
        if not batch:
            break
        ids.extend(batch)
        start += len(batch)
        time.sleep(0.4)  # stay under 3 requests/s without an API key
    return ["PMC" + i for i in ids[:limit]]


def latest_version(pmcid: str):
    listing = get("%s/?list-type=2&prefix=%s.&max-keys=200" % (BUCKET, pmcid)).decode()
    versions = sorted({int(v) for v in re.findall(r"<Key>%s\.(\d+)/" % pmcid, listing)})
    return "%s.%d" % (pmcid, versions[-1]) if versions else None


def figures(xml: str):
    for match in re.finditer(r"<fig\b.*?</fig>", xml, re.S):
        block = match.group(0)
        href = re.search(r'<graphic[^>]*xlink:href="([^"]+)"', block)
        if not href:
            continue
        label = re.search(r"<label>(.*?)</label>", block, re.S)
        caption = re.search(r"<caption>(.*?)</caption>", block, re.S)
        text = " ".join(re.sub(r"<[^>]+>", " ", caption.group(1) if caption else "").split())
        yield {
            "href": href.group(1),
            "label": re.sub(r"<[^>]+>", "", label.group(1)).strip() if label else "",
            "caption": text,
        }


def clinical(caption: str) -> bool:
    return bool(INCLUDE.search(caption)) and not EXCLUDE.search(caption)


def main() -> int:
    from PIL import Image

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=900)
    parser.add_argument("--min-side", type=int, default=600)
    args = parser.parse_args()
    out = Path(args.out)
    images_dir = out / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.jsonl"
    done = set()
    if manifest_path.exists():
        done = {json.loads(line)["file"] for line in manifest_path.read_text().splitlines() if line.strip()}
    stats = {"articles": 0, "licensed": 0, "figures": 0, "kept": 0, "small": 0, "filtered": 0, "errors": 0}
    ids = search_ids(args.limit)
    print("candidate articles:", len(ids), flush=True)
    with manifest_path.open("a") as manifest:
        for pmcid in ids:
            stats["articles"] += 1
            try:
                version = latest_version(pmcid)
                if not version:
                    continue
                meta = json.loads(get("%s/%s/%s.json" % (BUCKET, version, version)))
                if meta.get("license_code") not in ALLOWED_LICENSES or meta.get("is_retracted"):
                    continue
                stats["licensed"] += 1
                media = {}
                for url in meta.get("media_urls") or []:
                    key, _, query = url.replace("s3://pmc-oa-opendata/", "").partition("?md5=")
                    media[key.split("/", 1)[1]] = (key, query)
                xml = get("%s/%s/%s.xml" % (BUCKET, version, version)).decode("utf-8", "replace")
            except Exception as exc:  # network/parse problems skip one article, never abort the run
                stats["errors"] += 1
                print("skip", pmcid, type(exc).__name__, flush=True)
                continue
            for fig in figures(xml):
                stats["figures"] += 1
                if not clinical(fig["caption"]):
                    stats["filtered"] += 1
                    continue
                candidates = [k for k in media if k.rsplit(".", 1)[0] == fig["href"].rsplit(".", 1)[0]]
                if not candidates:
                    continue
                name = sorted(candidates, key=lambda k: k.endswith((".gif", ".tif")))[0]
                key, md5 = media[name]
                file_name = "%s_%s" % (pmcid, re.sub(r"[^A-Za-z0-9._-]", "_", name))
                if file_name in done:
                    continue
                try:
                    data = get("%s/%s" % (BUCKET, key))
                    if md5 and hashlib.md5(data).hexdigest() != md5:
                        raise ValueError("md5 mismatch")
                    with Image.open(io.BytesIO(data)) as image:
                        width, height = image.size
                        fmt = image.format
                except Exception as exc:
                    stats["errors"] += 1
                    print("bad image", pmcid, name, type(exc).__name__, flush=True)
                    continue
                if min(width, height) < args.min_side or fmt not in ("JPEG", "PNG", "WEBP"):
                    stats["small"] += 1
                    continue
                (images_dir / file_name).write_bytes(data)
                record = {
                    "file": file_name,
                    "pmcid": pmcid,
                    "version": version,
                    "doi": meta.get("doi"),
                    "title": meta.get("title"),
                    "citation": meta.get("citation"),
                    "license": meta.get("license_code"),
                    "figure_label": fig["label"],
                    "caption": fig["caption"][:1500],
                    "width": width,
                    "height": height,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "source_url": "%s/%s" % (BUCKET, key),
                }
                manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
                manifest.flush()
                done.add(file_name)
                stats["kept"] += 1
            time.sleep(0.1)
            if stats["articles"] % 50 == 0:
                print(stats, flush=True)
    print("final", stats, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
