# AI-assisted (Claude, 2026-11-17): tests written by Claude; updated by Claude for design-decisions.md 18–20.
# Verified: all pass; Øivind read them through and ran them before committing.
"""Tests for pendulum/app.py with Flask's test client. A fake stock stands in for Spoolman."""
import json
import math

import pytest

from pendulum import dummies
from pendulum.app import create_app
from pendulum.processing import DONE, RECEIVED, exact_period, load_orders
from pendulum.stock import StockUnavailable


class FakeStock:
    """Enough of SpoolmanClient for the pages and the seed button."""

    def __init__(self, offline=False):
        self.offline = offline
        self.vendors = [{"id": 1, "name": "eSUN"}]
        self.filaments = [{"id": 1, "name": "PLA+ Black", "vendor": self.vendors[0], "material": "PLA+",
                           "density": 1.23, "color_hex": "000000"}]
        self.spools = [{"id": 10, "filament": {"id": 1}, "remaining_weight": 1000.0},
                       {"id": 11, "filament": {"id": 1}, "remaining_weight": 150.0}]

    def _check(self):
        if self.offline:
            raise StockUnavailable("Spoolman is not answering")

    def get_vendors(self):
        self._check(); return self.vendors

    def get_filaments(self):
        self._check(); return self.filaments

    def get_spools(self):
        self._check(); return self.spools

    def use(self, spool_id, grams):
        self._check()
        for s in self.spools:
            if s["id"] == spool_id:
                s["remaining_weight"] -= grams
        return {}

    def create_vendor(self, name):
        v = {"id": len(self.vendors) + 1, "name": name}; self.vendors.append(v); return v

    def create_filament(self, name, vendor_id, material, density, diameter, color_hex, weight=None):
        vendor = next(v for v in self.vendors if v["id"] == vendor_id)
        f = {"id": len(self.filaments) + 1, "name": name, "vendor": vendor, "material": material,
             "density": density, "color_hex": color_hex}
        self.filaments.append(f); return f

    def create_spool(self, filament_id, initial_weight):
        s = {"id": 100 + len(self.spools), "filament": {"id": filament_id}, "remaining_weight": initial_weight}
        self.spools.append(s); return s


def fake_simulate(I, M, d, theta0, csv_path):
    csv_path.write_text("t,theta\n0,0.1\n0.1,0\n", encoding="utf-8")
    return exact_period(I, M, d, math.degrees(theta0)), "fake"


FORM = {"customer_ref": "Test", "target_period_s": "0.65",
        "base_width_mm": "80", "base_depth_mm": "80", "base_height_mm": "200",
        "filament_u_stand": "1", "filament_pendulum": "1"}


@pytest.fixture
def setup(tmp_path):
    stock = FakeStock()
    functions = (dummies.design, dummies.all_masses, dummies.export_3mf, dummies.inertia)
    app = create_app(stock, functions, fake_simulate, tmp_path / "orders", tmp_path / "output")
    return app.test_client(), stock, tmp_path


def test_order_page_lists_the_filaments_with_grams_left(setup):
    client, _, _ = setup
    page = client.get("/").get_data(as_text=True)
    assert "eSUN PLA+ Black" in page and "1150 g left" in page
    assert "Stock is offline" not in page


def test_order_page_when_spoolman_is_offline(setup):
    client, stock, _ = setup
    stock.offline = True
    page = client.get("/").get_data(as_text=True)
    assert "Stock is offline" in page
    assert '<button type="submit" disabled' in page


def test_placing_an_order_saves_it_as_received(setup):
    client, _, tmp_path = setup
    response = client.post("/", data=FORM)
    assert response.status_code == 302                         # on to the orders page
    [order] = load_orders(tmp_path / "orders")
    assert order.status == RECEIVED
    assert order.filament_per_part == {"u_stand": 1, "pendulum": 1}


def test_a_bad_order_is_shown_again_and_not_saved(setup):
    client, _, tmp_path = setup
    page = client.post("/", data={**FORM, "target_period_s": "abc"}).get_data(as_text=True)
    assert "The period must be a number" in page
    assert load_orders(tmp_path / "orders") == []


def test_process_orders_button_makes_the_order(setup):
    client, stock, tmp_path = setup
    client.post("/", data=FORM)
    client.post("/process")
    [order] = load_orders(tmp_path / "orders")
    assert order.status == DONE
    assert sum(s["remaining_weight"] for s in stock.spools) < 1150     # filament was subtracted
    page = client.get("/orders").get_data(as_text=True)
    assert order.id in page and "done" in page


def test_result_files_are_served_but_nothing_outside(setup):
    client, _, tmp_path = setup
    client.post("/", data=FORM)
    client.post("/process")
    [order] = load_orders(tmp_path / "orders")
    assert client.get(f"/output/{order.id}/design.json").status_code == 200
    assert client.get(f"/output/{order.id}/../../orders/{order.id}.json").status_code == 404
    assert client.get("/output/not-an-order/design.json").status_code == 404


def test_register_filaments_button_adds_whats_missing(setup):
    client, stock, tmp_path = setup
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"filaments": [
        {"vendor": "eSUN", "name": "PLA+ Black", "material": "PLA+", "density": 1.23, "diameter": 1.75,
         "color_hex": "000000", "net_weight": 1000},
        {"vendor": "eSUN", "name": "PLA+ Red", "material": "PLA+", "density": 1.23, "diameter": 1.75,
         "color_hex": "C62828", "net_weight": 1000}]}), encoding="utf-8")
    functions = (dummies.design, dummies.all_masses, dummies.export_3mf, dummies.inertia)
    client = create_app(stock, functions, fake_simulate, tmp_path / "orders", tmp_path / "output",
                        seed_file=seed).test_client()
    page = client.post("/register-filaments", follow_redirects=True).get_data(as_text=True)
    assert "1 added, 1 already in Spoolman" in page
    assert [f["name"] for f in stock.filaments] == ["PLA+ Black", "PLA+ Red"]


def test_orders_page_when_spoolman_is_offline(setup):
    client, stock, _ = setup
    stock.offline = True
    assert "Stock is offline" in client.get("/orders").get_data(as_text=True)
