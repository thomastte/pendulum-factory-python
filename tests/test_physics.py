# AI-assisted (Claude, 2026-11-17): tests for part_mass. Verified: values worked out by hand from the plan §3.1 model.
import cadquery as cq
import pytest

from pendulum.cad import make_U, make_pendulum
from pendulum.params import PendulumParams, PrintSettings
from pendulum.physics import all_masses, part_mass


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
    m = all_masses(p, {"stand": 1.24, "pendulum": 1.27})
    assert set(m) == {"stand", "pendulum"}             # exactly the keys processing.py uses
    assert m["stand"] == pytest.approx(part_mass(make_U(p), 1.24, p.print_settings))
    assert m["pendulum"] == pytest.approx(part_mass(make_pendulum(p), 1.27, p.print_settings))


def test_all_masses_uses_each_pieces_own_density():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 120
    m1 = all_masses(p, {"stand": 1.0, "pendulum": 1.0})
    m2 = all_masses(p, {"stand": 2.0, "pendulum": 1.0})   # only the stand's filament changes
    assert m2["stand"] == pytest.approx(2 * m1["stand"])
    assert m2["pendulum"] == pytest.approx(m1["pendulum"])
