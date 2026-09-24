#!/usr/bin/env python3
"""Scan Crosby VW's used inventory and build the description review page.

Pulls every used vehicle (in stock, in transit, on order) through the
website's own inventory endpoint, flags the ones with no description (or only
the generic dealer blurb), and writes:

  data/inventory.json  - every used vehicle with its description status
  review.html          - the review page, with the prompts and vehicles embedded
  site/index.html      - the same page as a standalone file for GitHub Pages

Usage: python3 scan.py
"""
import concurrent.futures
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
SITE = "https://www.crosbyvw.com"
PROXY = SITE + "/wp-content/plugins/convertus-vms/include/php/ajax-vehicles.php"
VMS = "https://vms.prod.convertus.rocks/api/"
INVENTORY_ID = "4211"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# The stock blurb some units carry instead of a real description.
GENERIC_MARKER = "family-owned business for over 50 years"
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


def vms_get(endpoint):
    url = PROXY + "?endpoint=" + urllib.parse.quote(endpoint, safe="") + "&action=vms_data"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def list_used():
    vehicles, page = [], 1
    while True:
        data = vms_get(
            f"{VMS}filtering/?cp={INVENTORY_ID}&ln=en&pg={page}&pc=100"
            "&sc=used&in_transit=true&in_stock=true&on_order=true"
        )
        vehicles += data["results"]
        if not data["results"] or len(vehicles) >= int(data["summary"]["total_vehicles"]):
            return vehicles
        page += 1


def vehicle_detail(vin):
    data = vms_get(f"{VMS}inventory/{INVENTORY_ID}/?&ln=en&vn={vin}&ba=true")
    return data[0] if isinstance(data, list) else data


def plain_text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def description_status(text):
    if not text:
        return "missing"
    if GENERIC_MARKER in text:
        return "generic"
    return "ok"


def suggested_type(v):
    if str(v.get("certified")) == "1":
        return "cpo"
    try:
        if float(v.get("final_price") or 0) and float(v["final_price"]) < AS_IS_PRICE_LIMIT:
            return "as-is"
    except ValueError:
        pass
    return "safety"


def number(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def summarize(v):
    text = plain_text(v.get("description"))
    status = description_status(text)
    return {
        "stock": v.get("stock_number", ""),
        "vin": v.get("vin", ""),
        "year": v.get("year"),
        "make": v.get("make", ""),
        "model": v.get("model", ""),
        "trim": v.get("trim", ""),
        "km": number(v.get("odometer")),
        "price": number(v.get("final_price")),
        "certified": str(v.get("certified")) == "1",
        "exterior": v.get("exterior_color", ""),
        "interior": v.get("interior_color", ""),
        "drivetrain": v.get("drive_train", ""),
        "engine": v.get("engine", ""),
        "transmission": v.get("transmission", ""),
        "body": v.get("body_style", ""),
        "fuel": v.get("fuel_type", ""),
        "in_transit": str(v.get("in_transit")) == "1",
        "on_order": str(v.get("on_order")) == "1",
        "url": v.get("vdp_url", ""),
        "status": status,
        "current_description": text if status == "generic" else "",
        "suggested": suggested_type(v),
    }


def main():
    listing = list_used()
    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        details = list(pool.map(lambda v: vehicle_detail(v["vin"]), listing))
    vehicles = [summarize(v) for v in details]
    vehicles.sort(key=lambda v: (v["status"] == "ok", v["status"] != "missing", v["stock"]))

    scanned = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data = {"scanned_at": scanned, "total_used": len(vehicles), "vehicles": vehicles}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "inventory.json").write_text(json.dumps(data, indent=2))

    prompts = {
        "safety": (ROOT / "prompts" / "safety-certified.md").read_text().strip(),
        "cpo": (ROOT / "prompts" / "cpo.md").read_text().strip(),
        "as-is": (ROOT / "prompts" / "as-is.md").read_text().strip(),
    }
    page_data = dict(data, vehicles=[v for v in vehicles if v["status"] != "ok"], prompts=prompts)
    template = (ROOT / "review_template.html").read_text()
    payload = json.dumps(page_data).replace("</", "<\\/")
    page = template.replace("/*__DATA__*/null", payload)
    (ROOT / "review.html").write_text(page)
    # Standalone copy for GitHub Pages (the Claude artifact host adds this wrapper itself).
    (ROOT / "site").mkdir(exist_ok=True)
    (ROOT / "site" / "index.html").write_text(PAGE_SHELL.replace("<!--PAGE-->", page))

    need = page_data["vehicles"]
    print(f"{len(vehicles)} used vehicles scanned; {len(need)} need a description "
          f"({sum(v['status'] == 'missing' for v in need)} missing, "
          f"{sum(v['status'] == 'generic' for v in need)} generic blurb only).")


if __name__ == "__main__":
    main()
