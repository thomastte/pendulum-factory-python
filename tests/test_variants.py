# AI-assisted (Claude, 2026-11-17): tests written by Claude; updated by Claude for design-decisions.md 18–20.
# Verified: all pass; Øivind read them through and ran them before committing.
"""Tests for pendulum/variants.py, with the dummy design functions and the real simulator (C++ or SciPy)."""
import math
from dataclasses import replace

import pytest
from scipy.special import ellipk

from pendulum import dummies
from pendulum.variants import BASE_ORDER, main, make_variant, markdown_table, run

FUNCTIONS = (dummies.design, dummies.all_masses, dummies.export_3mf, dummies.inertia)


def exact_ratio(deg):
    """T(θ0) / T_small-angle = 2·K(sin²(θ0/2)) / π."""
    return 2 * ellipk(math.sin(math.radians(deg) / 2) ** 2) / math.pi


def test_more_infill_is_heavier():
    low = make_variant("20 %", BASE_ORDER, FUNCTIONS, infill=0.2)
    full = make_variant("100 %", BASE_ORDER, FUNCTIONS, infill=1.0)
    assert full.mass_g > low.mass_g


def test_45_degrees_swings_slower_by_the_exact_amount(tmp_path):
    v = make_variant("45°", BASE_ORDER, FUNCTIONS)              # designed for a 45° start
    rows = run([replace(v, label="5°", amplitude_deg=5), v], tmp_path, "amplitude")
    t5, t45 = rows[0]["period_sim_s"], rows[1]["period_sim_s"]
    assert t45 / t5 == pytest.approx(exact_ratio(45) / exact_ratio(5), rel=1e-3)   # about 3.9 % longer


def test_simulation_matches_the_exact_formula(tmp_path):
    rows = run([make_variant("a", BASE_ORDER, FUNCTIONS)], tmp_path, "check")
    assert abs(rows[0]["sim_minus_formula_ms"]) < 1.0


def test_markdown_table_has_one_line_per_variant():
    rows = [{"variant": "a", "infill_percent": 20, "amplitude_deg": 5, "weight_pos_mm": 105.0, "mass_g": 80.0,
             "period_small_angle_s": 0.65, "period_formula_s": 0.6503, "period_sim_s": 0.6503,
             "sim_minus_formula_ms": 0.0}]
    lines = markdown_table(rows).splitlines()
    assert len(lines) == 3 and lines[2].startswith("| a | 20 | 5 |")


def test_main_writes_both_plots_and_the_table(tmp_path):
    rows = main(tmp_path, FUNCTIONS)
    assert len(rows) == 5
    for name in ("variants-infill.png", "variants-amplitude.png", "variants.csv", "variants.md"):
        assert (tmp_path / name).exists()
