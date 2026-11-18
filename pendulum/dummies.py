# AI-assisted (Claude, 2026-11-17): stand-ins written by Claude so processing.py can run before
# the real design functions exist. Adapted by Øivind to two printed pieces and the 45° start.
# Verified: tests/test_processing.py; Øivind read it through.
"""DUMMY versions of Thomas's design functions (plan §8). The numbers are rough, and no 3MF is written.

Used only until the integration: then app.py takes design(), all_masses(), export_3mf() and
inertia() from Thomas's modules instead, and nothing from this file is in the hand-in results.
"""
import math
from scipy.special import ellipk
from pendulum.params import PendulumParams
from pendulum.processing import G, InfeasibleDesign


def design(order, densities):
    """The order's U-stand with the block where a point mass would give the ordered period."""
    p = PendulumParams(BaseWidth=round(order.base_width_mm), BaseDepth=round(order.base_depth_mm),
                       BaseHeight=round(order.base_height_mm))
    vinkel = math.radians(p.StartAng)
    faktor = 2 / math.pi * ellipk(math.sin(vinkel / 2) ** 2)      # ≈ 1,04 ved 45°
    pos = 1000 * G * (order.target_period_s / faktor / (2 * math.pi)) ** 2
    lo, hi = p.ClrDia / 2 + p.BlockLength / 2, p.ArmLength - p.BlockLength / 2
    if not lo <= pos <= hi:
        raise InfeasibleDesign(f"A period of {order.target_period_s} s needs the weight {pos:.0f} mm "
                               f"below the axle; this stand allows {lo:.0f}-{hi:.0f} mm.")
    p.WeightPos = pos
    return p


def all_masses(params, densities):
    """Grams per part from box and cylinder volumes (mm³), with a rough allowance for infill."""
    p = params
    arm = p.ArmLength * p.ArmThick * p.BlockArmHeight + p.BlockLength * p.BlockThickness * p.BlockArmHeight
    axle = math.pi * (p.AxlDia / 2) ** 2 * p.AxleLength
    collars = 2 * math.pi * ((p.ClrDia / 2) ** 2 - (p.AxlDia / 2) ** 2) * p.ClrThick
    volume = {
        "u_stand": p.BaseWidth * p.BaseDepth * p.BaseThickness + 2 * p.PostThickness * p.PostDepth * p.BaseHeight,
        "pendulum": arm + axle + collars,

    }
    fill = 0.3 + 0.7 * p.print_settings.infill          # walls are solid, the rest is infill
    return {part: densities[part] * v * fill / 1000 for part, v in volume.items()}


def export_3mf(params, out_dir):
    """Writes nothing: the real export_3mf() comes from Thomas's cad.py."""
    return []


def inertia(params, masses):
    """I, M, d in SI for the arm as a point mass at the block (consistent with design() above)."""
    M = masses["pendulum"] / 1000
    d = params.WeightPos / 1000
    return M * d * d, M, d
