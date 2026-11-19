# AI-assisted (Claude, 2026-11-17): written by Claude; markdown_table() rewritten by Øivind from Claude's
# version, and 90° added to the amplitude comparison by Øivind with Claude's help. Updated by Claude for
# design-decisions.md 18–20. Reviewed and checked by Øivind. Verified: tests/test_variants.py.
"""Simulate the swing and compare two variants (the spec's "compare 2 variants", plan §3.4).

1. Infill: the same order printed with 20 % and with 100 % infill. Same period, different mass
   (design-decisions.md: infill can't tune the period).
2. Amplitude: the same pendulum started at 5° and at 45°. The period grows with the amplitude.

Run from the python/ folder:   python -m pendulum.variants
Writes to output/variants/: variants-infill.png, variants-amplitude.png, variants.csv and variants.md.
"""
import csv
import logging
import math
from dataclasses import dataclass, replace
from pathlib import Path

from pendulum.processing import G, OUTPUT_DIR, PARTS, Order, exact_period
from pendulum.simulate import simulate

log = logging.getLogger(__name__)

DENSITY = 1.23      # g/cm³, eSUN PLA+ (the makerspace filament, config/stock_seed.json)

BASE_ORDER = Order(id="variants", customer_ref="variant study", target_period_s=0.65,
                   base_width_mm=80, base_depth_mm=80, base_height_mm=200,
                   filament_per_part={part: 1 for part in PARTS})


def design_functions():
    """Thomas's design(), all_masses(), export_3mf() and inertia() when they exist, else the dummies.
    Returns the four functions and True if they are the dummies."""
    try:
        from pendulum.cad import export_3mf
        from pendulum.physics import all_masses, design, inertia
        return (design, all_masses, export_3mf, inertia), False
    except ImportError:
        from pendulum import dummies
        log.warning("pendulum.physics / pendulum.cad not ready: the variants use the DUMMY design functions")
        return (dummies.design, dummies.all_masses, dummies.export_3mf, dummies.inertia), True


@dataclass
class Variant:
    label: str
    infill: float              # 0..1
    amplitude_deg: float
    weight_pos_mm: float
    mass_g: float              # all printed parts
    I: float                   # kg·m², about the axle
    M: float                   # kg, the swinging part
    d: float                   # m, axle to centre of mass


def make_variant(label, order, functions, density=DENSITY, infill=None):
    """Design the order and return it as a Variant (the swinging part in SI, as the simulator wants).

    infill (0..1) overrides the print setting; the start angle is the design's (params.StartAng, 45°).
    """
    design, all_masses, _, inertia = functions
    densities = {part: density for part in PARTS}
    params = design(order, densities)
    if infill is not None:
        params.print_settings.infill = infill
    masses = all_masses(params, densities)
    I, M, d = inertia(params, masses)
    return Variant(label, params.print_settings.infill, params.StartAng, params.WeightPos,
                   sum(masses.values()), I, M, d)


def run(variants, out_dir, name, simulate_fn=simulate, normalise=False, title=""):
    """Simulate every variant, plot θ(t) for all of them in one figure and return one result row each.

    normalise=True plots θ/θ0, so variants with different amplitudes can be compared on one axis.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, curves = [], []
    for i, v in enumerate(variants, start=1):
        sim_csv = out_dir / f"variants-{name}-{i}.csv"
        t_sim, backend = simulate_fn(v.I, v.M, v.d, math.radians(v.amplitude_deg), sim_csv)
        t_calc = exact_period(v.I, v.M, v.d, v.amplitude_deg)
        t_small = 2 * math.pi * math.sqrt(v.I / (v.M * G * v.d))
        rows.append({"comparison": name, "variant": v.label, "infill_percent": round(100 * v.infill),
                     "amplitude_deg": v.amplitude_deg, "weight_pos_mm": round(v.weight_pos_mm, 1),
                     "mass_g": round(v.mass_g, 1), "period_small_angle_s": round(t_small, 4),
                     "period_formula_s": round(t_calc, 4), "period_sim_s": round(t_sim, 4),
                     "sim_minus_formula_ms": round(1000 * (t_sim - t_calc), 3), "simulator": backend})
        curves.append((v, sim_csv))
    _plot(curves, out_dir / f"variants-{name}.png", normalise, title)
    return rows


def _plot(curves, png_path, normalise, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=(7, 3.6))
    for v, sim_csv in curves:
        data = np.genfromtxt(sim_csv, delimiter=",", names=True)
        keep = data["t"] <= 3.0                                  # the first few swings are enough to see
        theta = np.degrees(data["theta"][keep])
        ax.plot(data["t"][keep], theta / v.amplitude_deg if normalise else theta, label=v.label)
    ax.set(xlabel="t [s]", ylabel="θ / θ₀" if normalise else "θ [°]", title=title)
    ax.grid(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=len(curves), frameon=False)
    fig.tight_layout()
    fig.savefig(png_path, dpi=150)
    plt.close(fig)


COLUMNS = [("variant", "Variant"), ("infill_percent", "Infill [%]"), ("amplitude_deg", "θ₀ [°]"),
           ("weight_pos_mm", "Weight pos. [mm]"), ("mass_g", "Mass [g]"),
           ("period_small_angle_s", "T small-angle [s]"), ("period_formula_s", "T exact [s]"),
           ("period_sim_s", "T simulated [s]"), ("sim_minus_formula_ms", "Sim − exact [ms]")]


def markdown_table(rows):
    lines = ["| " + " | ".join(h for _, h in COLUMNS) + " |",   "|" + "---|" * len(COLUMNS)]
    for row in rows:
        lines.append("| " + " | ".join(str(row[k]) for k, _ in COLUMNS) + " |")
    return "\n".join(lines)



def main(out_dir=OUTPUT_DIR / "variants", functions=None, simulate_fn=simulate):
    if functions is None:
        functions, dummy = design_functions()
    else:
        dummy = functions[0].__module__ == "pendulum.dummies"
    note = " (DUMMY design)" if dummy else ""

    low = make_variant("20 % infill", BASE_ORDER, functions, infill=0.2)
    full = make_variant("100 % infill", BASE_ORDER, functions, infill=1.0)
    rows = run([low, full], out_dir, "infill", simulate_fn,
               title=f"Same order, 20 % vs 100 % infill{note}")


    wide = replace(low, label="θ₀ = 45°", amplitude_deg=45)
    widest = replace(low, label="θ₀ = 90°", amplitude_deg=90)
    rows+= run([replace(low, label="θ₀ = 5°", amplitude_deg=5), wide, widest],
                out_dir, "amplitude", simulate_fn, normalise=True, title=f"Same order, 5°, 45° and 90° amplitude{note}")

    out_dir = Path(out_dir)
    with open(out_dir / "variants.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    table = markdown_table(rows)
    (out_dir / "variants.md").write_text(table + "\n", encoding="utf-8")
    print(table)
    if dummy:
        print("\nNOTE: dummy design functions. Run again once physics.py and cad.py exist, "
              "before the numbers go in the report.")
    print(f"\nWritten to {out_dir}")
    return rows


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()
