from pendulum.params import PendulumParams
from pendulum.cad import make_axle 
from pendulum.cad import make_collars
from pendulum.cad import make_arm
from pendulum.cad import make_weight
from pendulum.cad import make_pendulum, make_base, make_posts, make_U
import math 
import pytest

def test_axle_volume():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    axle = make_axle(p)
    volume = axle.val().Volume()
    assert volume == pytest.approx(p.AxleLength*math.pi*(p.AxlDia/2)**2)

def test_collar_volume():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    collar = make_collars(p)
    volume = collar.val().Volume()
    # AI-assisted (Claude, 2026-11-17): the flat on the print-bed side cuts a circular segment off each ring. Verified: matches CadQuery 2.8 (476.91 mm3).
    R = p.ClrDia/2      # collar radius
    h = p.AxlDia/2      # distance from the axle centre to the bed line
    segment = R**2 * math.acos(h/R) - h * math.sqrt(R**2 - h**2)   # area below the bed line
    ring = math.pi * (R**2 - (p.AxlDia/2)**2)                      # area of one ring before the flat
    assert volume == pytest.approx(2 * (ring - segment) * p.ClrThick)
    assert collar.val().BoundingBox().ymin == pytest.approx(-p.AxlDia/2)   # nothing below the bed line

# AI-assisted (Claude, 2026-11-17): arm test, same pattern as the axle and collar tests. Verified: pytest, and run against a corrected arm in CadQuery 2.8.
def test_arm_volume():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    arm = make_arm(p)
    volume = arm.val().Volume()
    half_disc = 0.5 * math.pi * (p.AxlDia/2)**2   # the part of the bar inside the axle, cut away
    assert volume == pytest.approx(p.ArmThick * (p.BlockArmHeight * p.ArmLength - half_disc))
    assert arm.val().BoundingBox().zmin == pytest.approx(-p.ArmLength)   # hangs down from the pivot

# AI-assisted (Claude, 2026-11-17): weight test, same pattern as the arm test. Verified: pytest, and the same geometry checked in CadQuery 2.8.
def test_weight_volume():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 120   # the default (6) would put the block up at the axle
    weight = make_weight(p)
    volume = weight.val().Volume()
    assert volume == pytest.approx((p.BlockThickness - p.ArmThick) * p.BlockArmHeight * p.BlockLength)   # block minus the arm through it
    assert len(weight.val().Solids()) == 2   # the arm splits the block into two halves
    bb = weight.val().BoundingBox()
    assert (bb.zmin + bb.zmax) / 2 == pytest.approx(-p.WeightPos)   # block centre at WeightPos below the pivot

# AI-assisted (Claude, 2026-11-17): tests for make_pendulum, make_base, make_posts and make_U, same pattern as above. Verified: pytest, run against Thomas's cad.py in CadQuery 2.8.
def test_pendulum_is_one_body():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 120
    parts = [make_axle(p), make_collars(p), make_arm(p), make_weight(p)]
    pendulum = make_pendulum(p)
    assert len(pendulum.val().Solids()) == 1   # everything is joined
    total = sum(part.val().Volume() for part in parts)
    assert pendulum.val().Volume() == pytest.approx(total)   # the cuts left no overlaps (decision 21)

def test_base_volume_and_position():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    base = make_base(p)
    assert base.val().Volume() == pytest.approx(p.BaseWidth * p.BaseDepth * p.BaseThickness)
    assert base.val().BoundingBox().zmin == pytest.approx(p.AxlOff - p.BaseHeight)   # on the table

def test_posts_volume_and_position():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    posts = make_posts(p)
    # AI-assisted (Claude, 2026-11-17): slot subtracted from each post. Verified: hand calculation, 69484.4 mm3 at BaseHeight 200.
    r = p.SlotWidth/2                                   # radius of the round slot bottom
    centre = p.SlotClearance/2                          # slot bottom circle sits this far above the pivot
    slot_area = math.pi * r**2 / 2 + p.SlotWidth * (p.AxlOff - centre)   # half circle + straight part up to the top
    full = p.PostThickness * p.PostDepth * (p.BaseHeight - p.BaseThickness)
    assert posts.val().Volume() == pytest.approx(2 * (full - slot_area * p.PostThickness))
    assert make_axle(p).intersect(posts).val().Volume() == pytest.approx(0, abs=1e-6)   # the axle does not cut into the posts
    bb = posts.val().BoundingBox()
    assert bb.zmax == pytest.approx(p.AxlOff)             # top of the posts level with the top of the axle
    assert bb.xmax == pytest.approx(p.BaseWidth/2)        # outer faces flush with the base edges
    assert bb.xmin == pytest.approx(-p.BaseWidth/2)

def test_U_is_one_body():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    u = make_U(p)
    assert len(u.val().Solids()) == 1   # posts stand on the base
    assert u.val().Volume() == pytest.approx(make_base(p).val().Volume() + make_posts(p).val().Volume())
    bb = u.val().BoundingBox()
    assert bb.zmax - bb.zmin == pytest.approx(p.BaseHeight)   # BaseHeight from the table to the top of the posts