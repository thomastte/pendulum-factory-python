# AI-assisted (Claude, 2026-11-17): tests for part_mass. Verified: values worked out by hand from the plan §3.1 model.
import cadquery as cq
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from pendulum.cad import make_U, make_pendulum
from pendulum.params import PendulumParams, PrintSettings
from pendulum.physics import all_masses, bisect, design, inertia, part_mass, period
from pendulum.processing import InfeasibleDesign


def test_part_mass_cube():
    cube = cq.Workplane("XY").box(20, 20, 20)            # V = 8000 mm3, A = 2400 mm2
    settings = PrintSettings(infill=0.2, walls=2, line_width=0.42)
    # walls: 2400 * 2 * 0.42 = 2016 mm3; infill: 0.2 * (8000 - 2016) = 1196.8 mm3; total 3212.8 mm3
    assert part_mass(cube, 1.24, settings) == pytest.approx(1.24 * 3212.8 / 1000)   # 3.98 g


def test_part_mass_full_infill_is_solid():
    cube = cq.Workplane("XY").box(20, 20, 20)
    settings = PrintSettings(infill=1.0, walls=2, line_width=0.42)
    assert part_mass(cube, 1.24, settings) == pytest.approx(1.24 * 8000 / 1000)     # 9.92 g, walls don't matter


def test_part_mass_thin_part_is_all_wall():
    plate = cq.Workplane("XY").box(20, 20, 1)            # V = 400 mm3, A = 880 mm2, walls 739 mm3 > V
    settings = PrintSettings(infill=0.2, walls=2, line_width=0.42)
    assert part_mass(plate, 1.24, settings) == pytest.approx(1.24 * 400 / 1000)      # min() caps the walls at V

# AI-assisted (Claude, 2026-11-17): tests for all_masses, same pattern as above. Verified: pytest.
def test_all_masses_weighs_each_printed_piece():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 120
    m = all_masses(p, {"u_stand": 1.24, "pendulum": 1.27})
    assert set(m) == {"u_stand", "pendulum"}             # exactly the keys processing.py uses
    assert m["u_stand"] == pytest.approx(part_mass(make_U(p), 1.24, p.print_settings))
    assert m["pendulum"] == pytest.approx(part_mass(make_pendulum(p), 1.27, p.print_settings))


def test_all_masses_uses_each_pieces_own_density():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 120
    m1 = all_masses(p, {"u_stand": 1.0, "pendulum": 1.0})
    m2 = all_masses(p, {"u_stand": 2.0, "pendulum": 1.0})   # only the stand's filament changes
    assert m2["u_stand"] == pytest.approx(2 * m1["u_stand"])
    assert m2["pendulum"] == pytest.approx(m1["pendulum"])


# AI-assisted (Claude, 2026-11-17): tests for inertia. Verified: pytest; the values match the
# step-by-step hand calculation (rho = m/V, I_G = rho*J[0][0], I = I_G + m*d^2) for the same geometry.
def test_inertia_known_values():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 120
    I, M, d = inertia(p, all_masses(p, {"u_stand": 1.24, "pendulum": 1.24}))
    assert M == pytest.approx(0.023530, rel=1e-3)      # kg  (23.53 g)
    assert d == pytest.approx(0.10295, rel=1e-3)       # m   (G is 102.95 mm below the axle)
    assert I == pytest.approx(2.983e-4, rel=1e-3)      # kg·m²


def test_inertia_parallel_axis():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 120
    I, M, d = inertia(p, all_masses(p, {"u_stand": 1.24, "pendulum": 1.24}))
    assert I > M * d**2                                # I_G about the centre of mass is never negative
    assert p.ArmLength / 2 / 1000 < d < p.WeightPos / 1000   # G between the arm's own centre and the block centre


def test_inertia_grows_when_the_weight_moves_down():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 120
    I1, M1, d1 = inertia(p, all_masses(p, {"u_stand": 1.24, "pendulum": 1.24}))
    p.WeightPos = 140
    I2, M2, d2 = inertia(p, all_masses(p, {"u_stand": 1.24, "pendulum": 1.24}))
    assert d2 > d1
    assert I2 > I1
    assert M2 == pytest.approx(M1)                     # same parts, only moved: the mass doesn't change


# AI-assisted (Claude, 2026-11-17): tests for period. Verified: pytest, run against a copy of period() with the
# k/K name fixed; expected values from the small-angle formula and K(sin²22.5°)/(π/2) = 1.0400 (scipy.special.ellipk).
def test_period_known_value():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 120
    I, M, d = inertia(p, all_masses(p, {"u_stand": 1.24, "pendulum": 1.24}))
    assert period(p, I, M, d) == pytest.approx(0.7321, rel=1e-3)     # s, released from 45°


def test_period_small_angle_matches_the_simple_formula():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.StartAng = 1e-6                                                 # almost no swing: K -> π/2
    I, M, d = 2.983e-4, 0.02353, 0.10295
    assert period(p, I, M, d) == pytest.approx(2 * math.pi * math.sqrt(I / (M * 9.81 * d)), rel=1e-9)


def test_period_point_mass():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.StartAng = 1e-6
    M, d = 0.1, 0.25
    I = M * d**2                                                      # all mass at distance d: simple pendulum
    assert period(p, I, M, d) == pytest.approx(2 * math.pi * math.sqrt(d / 9.81), rel=1e-9)   # 1.003 s


def test_period_45_degrees_is_4_percent_longer():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)    # StartAng = 45 by default
    I, M, d = 2.983e-4, 0.02353, 0.10295
    small = 2 * math.pi * math.sqrt(I / (M * 9.81 * d))
    assert period(p, I, M, d) / small == pytest.approx(1.03997, rel=1e-5)   # ellipk(k) instead of ellipk(k**2) gives 1.124


# AI-assisted (Claude, 2026-11-18): tests for bisect, written without running them first (Thomas's request).
# Verified: Thomas ran pytest.
def test_bisect_finds_pi_half_from_cosine():
    assert bisect(math.cos, 0, 3) == pytest.approx(math.pi / 2, abs=0.01)     # cos changes sign at π/2


def test_bisect_root_exactly_at_hi():
    assert bisect(lambda x: x - 3, 1, 3) == pytest.approx(3, abs=0.01)        # f(hi) = 0: still a valid bracket


def test_bisect_stops_after_max_iter():
    x = bisect(lambda x: x**2 - 2, 0, 2, tol=0, max_iter=3)                   # tol=0: only max_iter can stop it
    assert abs(x - math.sqrt(2)) <= 2 / 2**3 / 2                               # bracket 2 wide -> 0.25 after 3 halvings


def test_bisect_reuses_f_lo():
    calls = []
    def f(x):
        calls.append(x)                                                        # remember every call
        return x**2 - 2
    bisect(f, 0, 2)                                                            # 2 / 2**8 < 0.01: 8 halvings
    assert len(calls) <= 2 + 8                                                 # f(lo), f(hi), then one call per step

# AI-assisted (Claude, 2026-11-18): tests for design. Verified: pytest -m slow, run against a copy of Thomas's design().
# Each design() builds the CAD about 15 times (~4 s), so these are marked slow: run them with  pytest -m slow
def order_for(period_s, width=80, depth=80, height=200):
    """A stand-in with only the four Order fields design() reads (works with the old and new Order class)."""
    return SimpleNamespace(target_period_s=period_s, base_width_mm=width, base_depth_mm=depth, base_height_mm=height)


DENSITIES = {"u_stand": 1.24, "pendulum": 1.24}


@pytest.mark.slow
def test_design_hits_the_ordered_period():
    p = design(order_for(0.70), DENSITIES)
    I, M, d = inertia(p, all_masses(p, DENSITIES))
    assert period(p, I, M, d) == pytest.approx(0.70, abs=1e-4)


@pytest.mark.slow
def test_design_result_passes_validate():
    printer = json.loads((Path(__file__).parent.parent / "config" / "printer.json").read_text(encoding="utf-8"))
    p = design(order_for(0.70), DENSITIES)
    assert p.validate(printer) == []


@pytest.mark.slow
def test_design_rejects_too_long_a_period_with_the_range():
    with pytest.raises(InfeasibleDesign, match=r"0\.900 s.*can reach 0\.5\d\d to 0\.8\d\d s"):
        design(order_for(0.90), DENSITIES)                   # this kit reaches about 0.560-0.815 s


@pytest.mark.slow
def test_design_rejects_too_short_a_period():
    with pytest.raises(InfeasibleDesign):
        design(order_for(0.50), DENSITIES)


@pytest.mark.slow
def test_design_uses_the_order_sizes_rounded():
    p = design(order_for(0.70, width=80.4, depth=79.6, height=200.2), DENSITIES)
    assert (p.BaseWidth, p.BaseDepth, p.BaseHeight) == (80, 80, 200)


@pytest.mark.slow
def test_design_longer_period_moves_the_weight_down():
    p1 = design(order_for(0.65), DENSITIES)
    p2 = design(order_for(0.75), DENSITIES)
    assert p2.WeightPos > p1.WeightPos
