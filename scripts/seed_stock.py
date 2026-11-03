# AI-assisted (Claude, 2026-11-03): written by Claude.
# Verified: tests/test_seed_stock.py; run twice against Spoolman 0.27.0 (first adds, then skips all);
# Øivind read it through before committing.
"""Load the filament stock into Spoolman from config/stock_seed.json.

Run from the python/ folder, with Spoolman running (docker compose up -d):
    python scripts/seed_stock.py              register what is missing
    python scripts/seed_stock.py --dry-run    only show what it would do

Safe to run again: a filament that is already in Spoolman (same vendor and name) is skipped,
together with its spools. Nothing is registered until every entry in the file is valid.
"""
import argparse
import json
import re
import sys
from pathlib import Path

PY_ROOT = Path(__file__).resolve().parent.parent       # the python/ folder
sys.path.insert(0, str(PY_ROOT))                        # so "pendulum" imports when run as a script

from pendulum.stock import DEFAULT_URL, SpoolmanClient, StockUnavailable  # noqa: E402

SEED_FILE = PY_ROOT / "config" / "stock_seed.json"
REQUIRED = ("vendor", "name", "material", "density", "diameter", "color_hex", "net_weight")


def load_seed(path):
    """The list of filaments in the seed file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)["filaments"]


def _positive(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0


def validate(filaments):
    """Every problem in the seed file, as text. An empty list means it is all good."""
    problems = []
    seen = set()
    for i, f in enumerate(filaments, start=1):
        label = f"entry {i} ({f.get('vendor', '?')} {f.get('name', '?')})"
        missing = [key for key in REQUIRED if key not in f]
        if missing:
            problems.append(f"{label}: missing {', '.join(missing)}")
            continue
        for key, unit in (("density", "g/cm3"), ("diameter", "mm"), ("net_weight", "g")):
            if not _positive(f[key]):
                problems.append(f"{label}: {key} must be a number above 0 {unit}, got {f[key]!r}")
        if not re.fullmatch(r"[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?", str(f["color_hex"]).lstrip("#")):
            problems.append(f"{label}: color_hex must be like 000000, got {f['color_hex']!r}")
        for grams in f.get("spools_g", []):
            if not _positive(grams) or (_positive(f["net_weight"]) and grams > f["net_weight"]):
                problems.append(f"{label}: each spool in spools_g must be above 0 g and at most "
                                f"net_weight, got {grams!r}")
        if (f["vendor"], f["name"]) in seen:
            problems.append(f"{label}: listed twice")
        seen.add((f["vendor"], f["name"]))
    return problems


def seed(client, filaments, dry_run=False, log=print):
    """Register the filaments (and their vendors and spools) that Spoolman doesn't have yet.

    client: a SpoolmanClient. filaments: a validated list from the seed file.
    spools_g gives the grams left on each spool; without it, one full spool of net_weight.
    Returns (added, skipped), each a list of "vendor name".
    """
    vendors = {v["name"]: v["id"] for v in client.get_vendors()}
    existing = {((f.get("vendor") or {}).get("name"), f.get("name")) for f in client.get_filaments()}
    added, skipped = [], []
    for f in filaments:
        label = f"{f['vendor']} {f['name']}"
        if (f["vendor"], f["name"]) in existing:
            log(f"skip       {label} (already in Spoolman)")
            skipped.append(label)
            continue
        spools = f.get("spools_g", [f["net_weight"]])
        log(f"{'would add' if dry_run else 'add':<10} {label}: {len(spools)} spool(s), {spools} g")
        added.append(label)
        if dry_run:
            continue
        if f["vendor"] not in vendors:
            vendors[f["vendor"]] = client.create_vendor(f["vendor"])["id"]
        filament = client.create_filament(
            f["name"], vendors[f["vendor"]], f["material"], f["density"], f["diameter"],
            str(f["color_hex"]).lstrip("#").upper(), weight=f["net_weight"])
        for grams in spools:
            client.create_spool(filament["id"], grams)
    return added, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description="Load the filament stock into Spoolman.")
    parser.add_argument("--file", type=Path, default=SEED_FILE, help="seed file (default: config/stock_seed.json)")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Spoolman API (default: {DEFAULT_URL})")
    parser.add_argument("--dry-run", action="store_true", help="only show what would be added")
    args = parser.parse_args(argv)

    filaments = load_seed(args.file)
    problems = validate(filaments)
    if problems:
        print(f"{args.file} has problems, so nothing was registered:")
        for problem in problems:
            print("  -", problem)
        return 1
    try:
        added, skipped = seed(SpoolmanClient(args.url), filaments, dry_run=args.dry_run)
    except StockUnavailable as e:
        print(f"{e}. Start it with: docker compose up -d")
        return 1
    print(f"Done: {len(added)} {'to add' if args.dry_run else 'added'}, {len(skipped)} already there.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
