# AI-assisted (Claude, 2026-11-17): tests written by Claude; updated by Claude for design-decisions.md 18–20
# (two printed pieces, 45° start, no amplitude or infill in the order).
# Verified: all pass; Øivind read them through and ran them before committing.
"""Tests for pendulum/processing.py: every branch of the activity diagram in plan §4.

FakeStock stands in for Spoolman; the design functions are the dummies. One test runs the
real simulator (C++, or SciPy if it isn't built) to check the whole chain.
"""
import math
from datetime import datetime

import pytest

from pendulum import dummies
from pendulum.processing import (DONE, PARTS, POSTPONED, RECEIVED, REJECTED, Order, OrderProcessor,
                                 check_input, exact_period, load_orders, new_order_id)
from pendulum.simulate import simulate
from pendulum.stock import StockUnavailable

PRINTER = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}


class FakeStock:
    """Same methods as SpoolmanClient. filament 1 and 2, one spool each; offline=True raises."""

    def __init__(self, grams=(1000, 1000), offline=False, offline_on_use=None):
        self.filaments = [{"id": 1, "density": 1.23}, {"id": 2, "density": 1.23}]
        self.spools = [{"id": 10 + i, "filament": {"id": i + 1}, "remaining_weight": g} for i, g in enumerate(grams)]
        self.offline, self.offline_on_use, self.used = offline, offline_on_use, []

    def get_filaments(self):
        if self.offline:
            raise StockUnavailable("not answering")
        return self.filaments

    def get_spools(self):
        if self.offline:
            raise StockUnavailable("not answering")
        return self.spools

    def use(self, spool_id, grams):
        if spool_id == self.offline_on_use:
            raise StockUnavailable("not answering")
        self.used.append((spool_id, round(grams, 1)))
        for s in self.spools:
            if s["id"] == spool_id:
                s["remaining_weight"] -= grams
        return {}


def fake_simulate(I, M, d, theta0, csv_path):
    csv_path.write_text("t,theta\n0,0.1\n0.1,0\n", encoding="utf-8")
    return exact_period(I, M, d, math.degrees(theta0)), "fake"


def make_order(**changes):
    o = Order(id="order-1", customer_ref="Test", target_period_s=0.65,
              base_width_mm=80, base_depth_mm=80, base_height_mm=200,
              filament_per_part={"u_stand": 1, "pendulum": 2})
    for key, value in changes.items():
        setattr(o, key, value)
    return o


def processor(tmp_path, stock=None, simulator=fake_simulate):
    return OrderProcessor(stock or FakeStock(), dummies.design, dummies.all_masses, dummies.export_3mf,
                          dummies.inertia, simulator, printer=PRINTER,
                          orders_dir=tmp_path / "orders", output_dir=tmp_path / "output")


# --- the order itself ------------------------------------------------------------------

def test_valid_order_has_no_input_problems():
    assert check_input(make_order()) == []


@pytest.mark.parametrize("changes", [
    {"target_period_s": 0}, {"target_period_s": "0.65"}, {"base_height_mm": -1},
    {"filament_per_part": {"u_stand": 1}},
    {"filament_per_part": {"u_stand": "abc", "pendulum": 1}},
])
def test_bad_input_is_a_problem(changes):
    assert check_input(make_order(**changes))


def test_order_save_and_load(tmp_path):
    o = make_order(result={"x": 1})
    o.save(tmp_path)
    assert load_orders(tmp_path) == [o]


def test_new_order_id_does_not_reuse_a_name(tmp_path):
    now = datetime(2026, 11, 17, 13, 0, 0)
    assert new_order_id(tmp_path, now) == "order-20261117-130000"
    make_order(id="order-20261117-130000").save(tmp_path)
    assert new_order_id(tmp_path, now) == "order-20261117-130000-2"      # same second, name taken


def test_exact_period_small_angle():
    I, M, d = 0.05 * 0.2**2, 0.05, 0.2           # point mass 50 g on 0.2 m
    assert exact_period(I, M, d, 1e-6) == pytest.approx(2 * math.pi * math.sqrt(0.2 / 9.81), rel=1e-9)


# --- plan §4, branch by branch ------------------------------------------------------------

def test_good_order_is_done(tmp_path):
    stock = FakeStock()
    o = processor(tmp_path, stock).process(make_order())
    assert o.status == DONE
    assert o.result["period_diff_s"] == pytest.approx(0, abs=1e-3)
    assert {spool for spool, _ in stock.used} == {10, 11}          # one spool per filament
    assert (tmp_path / "output" / "order-1" / "design.json").exists()
    assert load_orders(tmp_path / "orders")[0].status == DONE       # saved


def test_used_grams_are_the_parts_on_each_filament_plus_waste(tmp_path):
    stock = FakeStock()
    o = processor(tmp_path, stock).process(make_order())
    m = o.result["masses_g"]
    used = dict(stock.used)
    assert used[11] == pytest.approx(round(m["pendulum"] * 1.1, 1), abs=0.2)
    assert used[10] == pytest.approx(round(m["u_stand"] * 1.1, 1), abs=0.2)


def test_bad_input_is_rejected_without_asking_spoolman(tmp_path):
    stock = FakeStock(offline=True)                 # would postpone if it were asked
    o = processor(tmp_path, stock).process(make_order(target_period_s=0))
    assert o.status == REJECTED and "period" in o.reason


def test_spoolman_offline_postpones(tmp_path):
    o = processor(tmp_path, FakeStock(offline=True)).process(make_order())
    assert o.status == POSTPONED and "offline" in o.reason


def test_unknown_filament_is_rejected(tmp_path):
    o = processor(tmp_path).process(make_order(filament_per_part={"u_stand": 9, "pendulum": 1}))
    assert o.status == REJECTED and "9" in o.reason


def test_impossible_period_is_rejected(tmp_path):
    o = processor(tmp_path).process(make_order(target_period_s=2.0))
    assert o.status == REJECTED and "allows" in o.reason


def test_broken_geometry_rule_is_rejected(tmp_path):
    o = processor(tmp_path).process(make_order(base_width_mm=300))
    assert o.status == REJECTED and "Base too wide" in o.reason


def test_not_enough_filament_postpones_and_uses_nothing(tmp_path):
    stock = FakeStock(grams=(1000, 5))
    o = processor(tmp_path, stock).process(make_order())
    assert o.status == POSTPONED and "Not enough filament" in o.reason
    assert stock.used == []


def test_offline_while_subtracting_postpones_and_retry_does_not_count_twice(tmp_path):
    stock = FakeStock(offline_on_use=11)            # filament 1 goes through, filament 2 fails
    proc = processor(tmp_path, stock)
    o = proc.process(make_order())
    assert o.status == POSTPONED and stock.used[0][0] == 10
    stock.offline_on_use = None                     # Spoolman is back
    o = proc.process(o)
    assert o.status == DONE
    assert [spool for spool, _ in stock.used] == [10, 11]          # spool 10 only once


def test_an_error_postpones_instead_of_crashing(tmp_path):
    def broken_masses(params, densities):
        raise RuntimeError("boom")
    proc = processor(tmp_path)
    proc.all_masses = broken_masses
    o = proc.process(make_order())
    assert o.status == POSTPONED and "boom" in o.reason


def test_process_all_takes_received_and_postponed_only(tmp_path):
    proc = processor(tmp_path)
    for i, status in enumerate([RECEIVED, POSTPONED, DONE, REJECTED]):
        make_order(id=f"order-{i}", status=status, created=f"2026-11-17T13:00:0{i}").save(tmp_path / "orders")
    processed = proc.process_all()
    assert [o.id for o in processed] == ["order-0", "order-1"]
    assert all(o.status == DONE for o in processed)


def test_whole_chain_with_the_real_simulator(tmp_path):
    """Dummy design + C++ (or SciPy) simulation: the simulated period matches the order."""
    o = processor(tmp_path, simulator=simulate).process(make_order())
    assert o.status == DONE
    assert o.result["period_sim_s"] == pytest.approx(0.65, rel=0.01)
    assert o.result["plot"] == "plot.png"
    assert (tmp_path / "output" / "order-1" / "plot.png").exists()
