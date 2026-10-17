#!/usr/bin/env python3
"""Scan Crosby VW's used inventory and build the description review page.

Reads every used vehicle from the website's used inventory page
(crosbyvw.com/used/search.html, which includes demos), opens each vehicle's
page for its details and description, flags the ones with no description (or
only the generic dealer blurb), and writes:

  data/inventory.json  - every used vehicle with its description status
  review.html          - the review page, with the prompts and vehicles embedded
  site/index.html      - the same page as a standalone file for GitHub Pages

Usage: python3 scan.py

Packaged as CrosbyDescriptions.exe, it instead writes "Crosby Descriptions.html"
next to the .exe and opens it in the browser.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
# Bundled prompts and template live in PyInstaller's unpack folder when frozen.
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
SITE = "https://www.crosbyvw.com"
LISTING_URL = SITE + "/used/search.html"
# Each vehicle page embeds its full record as `window.__vdpJSON = {...}`.
VDP_MARKER = "window.__vdpJSON = "
HEADERS = {"User-Agent": "Mozilla/5.0"}

# The stock blurb some units carry instead of a real description.
GENERIC_MARKER = "family-owned business for over 50 years"
# The site auto-fills units with a one-line placeholder ("Pure White, Grigio, Cloth
# Seating Surfaces 4 years / 80,000 km"); real descriptions run 190+ words.
MIN_REAL_WORDS = 60
# The site title-cases trims ("Execline 2.0 Tsi"); restore the usual spellings.
TRIM_WORDS = {w.lower(): w for w in (
    "TSI TDI GTI GLI GLS GL GT SE SEL SXT SLE SLT SL SV SR LX EX EX-L LT LTZ RS XLE XSE "
    "AWD FWD RWD 4WD 4X4 4MOTION 4MATIC xDrive DSG CVT R-Line EV PHEV HEV").split()}
# Prices under this default to AS-IS in the dropdown.
AS_IS_PRICE_LIMIT = 5000

PAGE_SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<style>body{margin:0}[hidden]{display:none!important}</style>
</head>
<body>
<!--PAGE-->
</body>
</html>
"""


class LayoutChanged(RuntimeError):
    """The website no longer has the data where the scanner expects it."""


def fetch(url, attempts=5):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            # The site rate-limits bursts (429); back off and try again.
            if e.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
            wait = e.headers.get("Retry-After")
            time.sleep(int(wait) if wait and wait.isdigit() else 5 * 2 ** attempt)
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            # Dropped connections ("connection reset by peer") and timeouts.
            if attempt == attempts - 1:
                raise
            time.sleep(5 * 2 ** attempt)


def list_used():
    """Every vehicle on the used inventory page, from its schema.org Vehicle data."""
    html = fetch(LISTING_URL)
    vehicles, seen = [], set()
    for m in re.finditer(r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', html, re.S):
        try:
            item = json.loads(m.group(1))
        except ValueError:
            continue
        url = (item.get("offers") or {}).get("url")
        if item.get("@type") != "Vehicle" or not url or url in seen:
            continue
        seen.add(url)
        vehicles.append({"url": url, "vin": item.get("vehicleIdentificationNumber", ""),
                         "name": " ".join(item.get("name", "").split())})
    if not vehicles:
        raise LayoutChanged(f"No vehicles found on {LISTING_URL}; the website layout may have changed.")
    return vehicles


def vehicle_detail(url):
    html = fetch(url)
    i = html.find(VDP_MARKER)
    if i < 0:
        raise LayoutChanged(f"No vehicle data on {url}; the website layout may have changed.")
    return json.JSONDecoder().raw_decode(html, i + len(VDP_MARKER))[0]


def plain_text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def description_status(text):
    if not text:
        return "missing"
    if GENERIC_MARKER in text or len(text.split()) < MIN_REAL_WORDS:
        return "generic"
    return "ok"


def trim_name(trim):
    words = []
    for w in trim.split():
        if w.lower() in TRIM_WORDS:
            w = TRIM_WORDS[w.lower()]
        elif re.fullmatch(r"\d+(\.\d+)?[a-z]", w):
            w = w.upper()  # 2.0t -> 2.0T
        words.append(w)
    return " ".join(words)


def number(value):
    digits = re.sub(r"[^0-9.]", "", str(value or ""))
    try:
        return int(float(digits))
    except ValueError:
        return None


def field(value, key="basic"):
    """The site's text fields are either plain strings or {"basic": ...} objects; "N.A." means unknown."""
    if isinstance(value, dict):
        value = value.get(key, "")
    value = str(value or "").strip()
    return "" if value.upper() in ("N.A.", "N/A", "NA") else value


def suggested_type(v, price):
    if v.get("isCertified"):
        return "cpo"
    if v.get("asIs") or (price and price < AS_IS_PRICE_LIMIT):
        return "as-is"
    return "safety"


def specs(sections):
    """The spec table on the vehicle page, as {"specsDriveTrain": "Front-wheel drive", ...}."""
    table = {}
    for group in (sections.get("specifications") or {}).get("listing") or []:
        for key, pair in group.items():
            if isinstance(pair, list) and pair:
                table[key] = field(pair[0])
    return table


def summarize(v, url):
    sections = v.get("sections") or {}
    spec = specs(sections)
    parts = (sections.get("description") or {}).get("text") or []
    text = plain_text(" ".join(p.get("text", "") for p in parts if isinstance(p, dict)))
    status = description_status(text)
    price = number((v.get("prices") or {}).get("priceInteger"))
    color = v.get("color") or {}
    delivery = str(v.get("deliveryStatus") or "").lower()
    stock = field(v.get("sn"))
    return {
        "stock": re.sub(r"-demo$", "", stock, flags=re.I),
        "demo": bool(v.get("isDemo")) or stock.lower().endswith("-demo"),
        "vin": field(v.get("niv")),
        "year": number(v.get("year")),
        "make": field(v.get("make")),
        "model": field(v.get("model")),
        "trim": trim_name(field(v.get("version"))),
        "km": number(v.get("km")),
        "price": price,
        "certified": bool(v.get("isCertified")),
        "exterior": field(color.get("exterior")) or spec.get("specsExtColor", ""),
        "interior": field(color.get("interior")) or spec.get("specsIntColor", ""),
        "drivetrain": spec.get("specsDriveTrain") or field(v.get("drivetrain")),
        "engine": spec.get("specsEngine") or field(v.get("engine")),
        "transmission": spec.get("specsTransmission") or field(v.get("transmission")),
        "body": field(v.get("bodytype")) or spec.get("specsBodyType", ""),
        "fuel": spec.get("specsFuel") or field(v.get("fueltype")),
        "in_transit": "transit" in delivery,
        "on_order": "order" in delivery,
        "url": url,
        "status": status,
        "current_description": text if status == "generic" else "",
        "suggested": suggested_type(v, price),
    }


def main():
    print("Scanning crosbyvw.com used inventory...")
    listing = list_used()
    vehicles = []
    for i, item in enumerate(listing, 1):
        print(f"  {i}/{len(listing)}  {item['name']}", flush=True)
        vehicles.append(summarize(vehicle_detail(item["url"]), item["url"]))
        time.sleep(0.5)
    vehicles.sort(key=lambda v: (v["status"] == "ok", v["status"] != "missing", v["stock"]))

    scanned = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data = {"scanned_at": scanned, "total_used": len(vehicles), "vehicles": vehicles}

    prompts = {
        "safety": (ROOT / "prompts" / "safety-certified.md").read_text("utf-8").strip(),
        "cpo": (ROOT / "prompts" / "cpo.md").read_text("utf-8").strip(),
        "as-is": (ROOT / "prompts" / "as-is.md").read_text("utf-8").strip(),
    }
    page_data = dict(data, vehicles=[v for v in vehicles if v["status"] != "ok"], prompts=prompts)
    template = (ROOT / "review_template.html").read_text("utf-8")
    payload = json.dumps(page_data).replace("</", "<\\/")
    sdk = (ROOT / "vendor" / "anthropic-sdk.min.js").read_text("utf-8")
    page = template.replace("/*__SDK__*/", sdk).replace("/*__DATA__*/null", payload)
    standalone = PAGE_SHELL.replace("<!--PAGE-->", page)

    if FROZEN:
        out = Path(sys.executable).parent / "Crosby Descriptions.html"
        out.write_text(standalone, "utf-8")
        webbrowser.open(out.as_uri())
    else:
        (ROOT / "data").mkdir(exist_ok=True)
        (ROOT / "data" / "inventory.json").write_text(json.dumps(data, indent=2), "utf-8")
        (ROOT / "review.html").write_text(page, "utf-8")
        # Standalone copy for GitHub Pages (the Claude artifact host adds this wrapper itself).
        (ROOT / "site").mkdir(exist_ok=True)
        (ROOT / "site" / "index.html").write_text(standalone, "utf-8")

    need = page_data["vehicles"]
    print(f"{len(vehicles)} used vehicles scanned; {len(need)} need a description "
          f"({sum(v['status'] == 'missing' for v in need)} missing, "
          f"{sum(v['status'] == 'generic' for v in need)} placeholder text only).")


if __name__ == "__main__":
    if not FROZEN:
        main()
    else:
        # Keep the console window open so the result or error can be read.
        try:
            main()
            print("\nDone. The page is open in your browser.")
            time.sleep(4)
        except Exception as e:
            print(f"\nThe scan didn't finish: {e}")
            print("Check your internet connection and try again. If it keeps failing, send this message to whoever maintains the tool.")
            input("\nPress Enter to close.")
