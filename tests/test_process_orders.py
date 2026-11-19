# AI-assisted (Claude, 2026-11-19): tests written by Claude for scripts/process_orders.py.
# Reviewed, run and checked by Øivind.
"""Tests for scripts/process_orders.py, with the fake stock and simulator from test_app.py."""
import json
import sys
from pathlib import Path

from pendulum import dummies
from pendulum.processing import DONE, REJECTED, load_orders
from test_app import FakeStock, fake_simulate

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import process_orders  # noqa: E402

FUNCTIONS = (dummies.design, dummies.all_masses, dummies.export_3mf, dummies.inertia)


def write_order(folder, order_id, period):
    folder.mkdir(parents=True, exist_ok=True)
    order = {"id": order_id, "customer_ref": "Example", "target_period_s": period,
             "base_width_mm": 80, "base_depth_mm": 80, "base_height_mm": 200,
             "filament_per_part": {"u_stand": 1, "pendulum": 1},
             "status": "received", "reason": "", "created": "2026-11-19T12:00:00", "result": {}}
    (folder / f"{order_id}.json").write_text(json.dumps(order), encoding="utf-8")


def run(tmp_path, stock, folder):
    return process_orders.main([str(folder)], stock, FUNCTIONS, fake_simulate,
                               tmp_path / "orders", tmp_path / "output")


def test_queues_the_example_orders_and_processes_them(tmp_path, capsys):
    examples = tmp_path / "examples"
    write_order(examples, "example-ok", 0.65)
    write_order(examples, "example-bad", 0)                       # a period of 0 is rejected
    assert run(tmp_path, FakeStock(), examples) == 0
    status = {o.id: o.status for o in load_orders(tmp_path / "orders")}
    assert status == {"example-ok": DONE, "example-bad": REJECTED}
    out = capsys.readouterr().out
    assert "1 done, 1 rejected, 0 postponed" in out


def test_running_twice_makes_nothing_twice(tmp_path, capsys):
    examples, stock = tmp_path / "examples", FakeStock()
    write_order(examples, "example-ok", 0.65)
    run(tmp_path, stock, examples)
    left = sum(s["remaining_weight"] for s in stock.spools)
    run(tmp_path, stock, examples)
    assert sum(s["remaining_weight"] for s in stock.spools) == left      # nothing subtracted again
    assert "already in orders/" in capsys.readouterr().out


def test_a_bad_file_is_reported_and_the_rest_still_run(tmp_path, capsys):
    examples = tmp_path / "examples"
    write_order(examples, "example-ok", 0.65)
    (examples / "broken.json").write_text("{ not json", encoding="utf-8")
    run(tmp_path, FakeStock(), examples)
    assert [o.id for o in load_orders(tmp_path / "orders")] == ["example-ok"]
    assert "broken.json: not a valid order" in capsys.readouterr().out


def test_a_missing_folder_is_an_error(tmp_path):
    assert run(tmp_path, FakeStock(), tmp_path / "nowhere") == 1
