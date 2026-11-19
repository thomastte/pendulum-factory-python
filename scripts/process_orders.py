# AI-assisted (Claude, 2026-11-19): written by Claude at Øivind's request (plan §4 without the web pages).
# Reviewed and checked by Øivind. Verified: tests/test_process_orders.py; Øivind ran it on the six example
# orders against Spoolman.
"""Process orders from the command line, without the web pages.

Run from the python/ folder, with Spoolman running (docker compose up -d):
    python scripts/process_orders.py examples/orders    queue the example orders and process them
    python scripts/process_orders.py                    process what is already waiting in orders/

Each JSON file in the folder is copied into orders/ as a received order, then every received or
postponed order is processed, exactly like the "Process orders" button. An order that is already in
orders/ is not copied again, so running it twice does not make (or subtract) anything twice.
Results: orders/<id>.json (status, reason and "result") and output/<id>/ (design.json, 3MF, plot).
"""
import argparse
import logging
import sys
from pathlib import Path

PY_ROOT = Path(__file__).resolve().parent.parent       # the python/ folder
sys.path.insert(0, str(PY_ROOT))                        # so "pendulum" imports when run as a script

from pendulum.app import design_functions  # noqa: E402
from pendulum.processing import (ORDERS_DIR, OUTPUT_DIR, RECEIVED, Order,  # noqa: E402
                                 OrderProcessor)
from pendulum.simulate import simulate  # noqa: E402
from pendulum.stock import SpoolmanClient  # noqa: E402


def queue(folder, orders_dir):
    """Copy each order file in folder into orders_dir as received. Returns (queued ids, problems)."""
    queued, problems = [], []
    for path in sorted(Path(folder).glob("*.json")):
        try:
            order = Order.load(path)
        except Exception as e:                       # bad JSON or unknown fields: report and go on
            problems.append(f"{path.name}: not a valid order ({e})")
            continue
        if (Path(orders_dir) / f"{order.id}.json").exists():
            print(f"  {order.id}: already in orders/, not queued again")
            continue
        order.status, order.reason, order.result = RECEIVED, "", {}
        order.save(orders_dir)
        queued.append(order.id)
    return queued, problems


def summary_line(order):
    """One line per order for the terminal."""
    r = order.result
    line = f"  {order.id:<24} {order.status:<10} {order.reason}"
    if "period_sim_s" in r:
        line += f"\n  {'':<24} {'':<10} target {order.target_period_s:.3f} s, simulated {r['period_sim_s']:.4f} s ({r.get('simulator', '')})"
    if "masses_g" in r:
        line += ", " + ", ".join(f"{part} {g} g" for part, g in r["masses_g"].items())
    return line


def main(argv=None, stock=None, functions=None, simulate_fn=simulate,
         orders_dir=ORDERS_DIR, output_dir=OUTPUT_DIR):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", nargs="?", help="folder with order JSON files to queue first")
    args = parser.parse_args(argv)

    if args.folder:
        if not Path(args.folder).is_dir():
            print(f"No such folder: {args.folder}")
            return 1
        print(f"Queueing the orders in {args.folder}:")
        queued, problems = queue(args.folder, orders_dir)
        for p in problems:
            print(f"  {p}")
        print(f"  {len(queued)} queued")

    if functions is None:
        functions, dummy = design_functions()
        if dummy:
            print("WARNING: pendulum.physics is not available, so the DUMMY design functions are used.")
    processor = OrderProcessor(stock or SpoolmanClient(), *functions, simulate_fn,
                               orders_dir=orders_dir, output_dir=output_dir)
    processed = processor.process_all()

    print(f"\nProcessed {len(processed)} order(s):")
    for order in sorted(processed, key=lambda o: o.id):
        print(summary_line(order))
    counts = {s: sum(o.status == s for o in processed) for s in ("done", "rejected", "postponed")}
    print(f"\n{counts['done']} done, {counts['rejected']} rejected, {counts['postponed']} postponed.")
    print(f"Results: {Path(orders_dir)}/<id>.json and {Path(output_dir)}/<id>/")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.exit(main())
