# AI-assisted (Claude, 2026-11-17): written by Claude (Flask order page and operator page, plan §6).
# Verified: tests/test_app.py; Øivind ran it against Spoolman 0.27.0 and read it through before committing.
"""The web pages (plan §6). Start from the python/ folder with Spoolman running:

    python -m pendulum.app          then open http://localhost:5000

/        order page: the customer fills in the pendulum and picks a filament for each part
/orders  operator page: register the makerspace filaments, process orders, see the results
"""
import logging
import secrets
from collections import defaultdict
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, url_for

from pendulum.processing import (DONE, ORDERS_DIR, OUTPUT_DIR, PARTS, POSTPONED, REJECTED, Order,
                                 OrderProcessor, check_input, load_orders, new_order_id)
from pendulum.simulate import simulate
from pendulum.stock import SpoolmanClient, StockUnavailable

log = logging.getLogger(__name__)


def design_functions():
    """Thomas's design(), all_masses(), export_3mf() and inertia() when they exist, else the dummies.

    Returns the four functions and True if they are the dummies (the pages then show a warning).
    """
    try:
        from pendulum.cad import export_3mf
        from pendulum.physics import all_masses, design, inertia
        return (design, all_masses, export_3mf, inertia), False
    except ImportError:
        from pendulum import dummies
        log.warning("pendulum.physics / pendulum.cad not ready: using the DUMMY design functions")
        return (dummies.design, dummies.all_masses, dummies.export_3mf, dummies.inertia), True


def stock_overview(stock):
    """Filaments with their spools and grams left, for the dropdowns and the stock table.

    Raises StockUnavailable when Spoolman doesn't answer.
    """
    filaments = stock.get_filaments()
    left, count = defaultdict(float), defaultdict(int)
    for s in stock.get_spools():
        fid = s["filament"]["id"]
        count[fid] += 1
        left[fid] += s.get("remaining_weight") or 0
    rows = []
    for f in filaments:
        vendor = (f.get("vendor") or {}).get("name", "")
        rows.append({"id": f["id"], "name": f"{vendor} {f.get('name', '')}".strip(),
                     "material": f.get("material", ""), "density": f.get("density"),
                     "color": f.get("color_hex") or "cccccc", "spools": count[f["id"]],
                     "grams_left": round(left[f["id"]])})
    return sorted(rows, key=lambda r: r["name"])


def _number(text, scale=1.0):
    """A form field as a float, or None if it isn't a number (check_input() then reports it)."""
    try:
        return float(text.replace(",", ".")) * scale
    except (AttributeError, ValueError):
        return None


def _filament_id(text):
    """Spoolman ids are whole numbers; anything else is kept as it is for check_input() to report."""
    return int(text) if text.strip().isdigit() else text


def order_from_form(form, orders_dir):
    return Order(
        id=new_order_id(orders_dir),
        customer_ref=form.get("customer_ref", "").strip(),
        target_period_s=_number(form.get("target_period_s")),
        amplitude_deg=_number(form.get("amplitude_deg")),
        base_width_mm=_number(form.get("base_width_mm")),
        base_depth_mm=_number(form.get("base_depth_mm")),
        base_height_mm=_number(form.get("base_height_mm")),
        infill=_number(form.get("infill_percent"), scale=0.01),
        filament_per_part={part: _filament_id(form.get(f"filament_{part}", "")) for part in PARTS},
    )


def create_app(stock=None, functions=None, simulate_fn=simulate,
               orders_dir=ORDERS_DIR, output_dir=OUTPUT_DIR, seed_file=None):
    """The Flask app. Tests pass a fake stock and the dummy functions; normal use passes nothing."""
    orders_dir, output_dir = Path(orders_dir), Path(output_dir)
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(16)          # only for the short messages after a button
    stock = stock or SpoolmanClient()
    if functions is None:
        functions, dummy = design_functions()
    else:
        dummy = functions[0].__module__ == "pendulum.dummies"
    processor = OrderProcessor(stock, *functions, simulate_fn, orders_dir=orders_dir, output_dir=output_dir)

    @app.context_processor
    def common():
        return {"dummy": dummy, "parts": PARTS}

    @app.route("/", methods=["GET", "POST"])
    def order_page():
        errors, form = [], request.form if request.method == "POST" else {}
        if request.method == "POST":
            order = order_from_form(request.form, orders_dir)
            errors = check_input(order)
            if not errors:
                order.save(orders_dir)
                flash(f"Order {order.id} received. Click \"Process orders\" to make it.")
                return redirect(url_for("orders_page"))
        try:
            filaments, offline = stock_overview(stock), False
        except StockUnavailable:
            filaments, offline = [], True
        return render_template("order.html", filaments=filaments, offline=offline, errors=errors, form=form)

    @app.route("/orders")
    def orders_page():
        try:
            filaments, offline = stock_overview(stock), False
        except StockUnavailable:
            filaments, offline = [], True
        orders = list(reversed(load_orders(orders_dir)))              # newest first
        return render_template("orders.html", orders=orders, filaments=filaments, offline=offline,
                               DONE=DONE, REJECTED=REJECTED, POSTPONED=POSTPONED)

    @app.post("/process")
    def process_orders():
        processed = processor.process_all()
        if not processed:
            flash("No received or postponed orders to process.")
        for o in processed:
            flash(f"{o.id}: {o.status}. {o.reason}")
        return redirect(url_for("orders_page"))

    @app.post("/register-filaments")
    def register_filaments():
        from scripts.seed_stock import SEED_FILE, load_seed, seed, validate
        filaments = load_seed(seed_file or SEED_FILE)
        problems = validate(filaments)
        if problems:
            flash("The seed file has problems, nothing was registered: " + " ".join(problems))
            return redirect(url_for("orders_page"))
        try:
            added, skipped = seed(stock, filaments, log=lambda line: None)
            flash(f"Filaments registered: {len(added)} added, {len(skipped)} already in Spoolman.")
        except StockUnavailable as e:
            flash(f"{e}. Start it with: docker compose up -d")
        return redirect(url_for("orders_page"))

    @app.route("/output/<order_id>/<path:filename>")
    def output_file(order_id, filename):
        if order_id not in {o.id for o in load_orders(orders_dir)}:
            abort(404)
        return send_from_directory(output_dir / order_id, filename)   # refuses paths outside the folder

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(port=5000)
