# AI-assisted (Claude, 2026-11-17): written by Claude (Order, OrderProcessor, the plan §4 flow).
# Adapted by Øivind to design-decisions.md 18–20 (two printed pieces, 45° start from params.StartAng,
# no amplitude or infill in the order).
# Verified: tests/test_processing.py; Øivind read it through before committing.
"""Order processing: one order from "received" to "done", following the activity diagram in plan §4.

Thomas's design functions (plan §8) are passed in, so this module runs and is tested before
they exist: until the integration, pendulum/dummies.py stands in for them.
Units: mm and g in orders and results; SI only for inertia, period and simulation.
"""
import json
import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from scipy.special import ellipk

from pendulum.stock import InsufficientMaterial, StockUnavailable, need_per_filament, pick_spools

log = logging.getLogger(__name__)

PY_ROOT = Path(__file__).resolve().parent.parent
ORDERS_DIR = PY_ROOT / "orders"                    # one JSON file per order (gitignored)
OUTPUT_DIR = PY_ROOT / "output"                    # design.json, 3MF, sim.csv, plot.png per order (gitignored)
PRINTER_FILE = PY_ROOT / "config" / "printer.json"

# The printed parts. Must match the keys of Thomas's all_masses(): change them here if his change.
PARTS = ("u_stand", "pendulum")

RECEIVED, POSTPONED, REJECTED, DONE = "received", "postponed", "rejected", "done"
G = 9.81


class InfeasibleDesign(Exception):
    """design() raises this when no weight position gives the ordered period (plan §8)."""


@dataclass
class Order:
    id: str
    customer_ref: str
    target_period_s: float

    base_width_mm: float
    base_depth_mm: float
    base_height_mm: float
                  # 0..1
    filament_per_part: dict             # {part: Spoolman filament id}
    status: str = RECEIVED
    reason: str = ""
    created: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    result: dict = field(default_factory=dict)

    def save(self, folder=ORDERS_DIR):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{self.id}.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path):
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


def new_order_id(folder=ORDERS_DIR, now=None):
    """order-YYYYMMDD-HHMMSS, with -2, -3 ... if that name is taken."""
    base = (now or datetime.now()).strftime("order-%Y%m%d-%H%M%S")
    order_id, n = base, 2
    while (Path(folder) / f"{order_id}.json").exists():
        order_id, n = f"{base}-{n}", n + 1
    return order_id


def load_orders(folder=ORDERS_DIR):
    """All saved orders, oldest first."""
    orders = [Order.load(p) for p in Path(folder).glob("*.json")]
    return sorted(orders, key=lambda o: o.created)


def _number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def check_input(order):
    """Problems with the order's own fields (plan §4, first step). An empty list means OK."""
    problems = []
    if not (_number(order.target_period_s) and order.target_period_s > 0):
        problems.append("The period must be a number above 0 s.")
    
    for name, label in (("base_width_mm", "width"), ("base_depth_mm", "depth"), ("base_height_mm", "height")):
        value = getattr(order, name)
        if not (_number(value) and value > 0):
            problems.append(f"The base {label} must be a number above 0 mm.")
   
    missing = [part for part in PARTS if not order.filament_per_part.get(part)]
    if missing:
        problems.append("No filament chosen for: " + ", ".join(missing) + ".")
    bad = [part for part in PARTS if part not in missing and not str(order.filament_per_part[part]).isdigit()]
    if bad:
        problems.append("The filament id must be a whole number for: " + ", ".join(bad) + ".")
    return problems


def exact_period(I, M, d, theta0_deg, g=G):
    """T = 4·√(I/(M·g·d))·K(sin(θ0/2)), plan §3.2. SI units, θ0 in degrees."""
    k = math.sin(math.radians(theta0_deg) / 2)
    return 4 * math.sqrt(I / (M * g * d)) * float(ellipk(k * k))   # ellipk takes k², not k


def _plot_swing(csv_path, png_path, title):
    """θ(t) from the simulator's CSV as a PNG. Returns the file name, or None if it fails."""
    try:
        import matplotlib
        matplotlib.use("Agg")                     # no window: runs inside the web server
        import matplotlib.pyplot as plt
        import numpy as np

        data = np.genfromtxt(csv_path, delimiter=",", names=True)
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.plot(data["t"], np.degrees(data["theta"]))
        ax.set(xlabel="t [s]", ylabel="θ [°]", title=title)
        ax.grid(True)
        fig.tight_layout()
        fig.savefig(png_path, dpi=120)
        plt.close(fig)
        return Path(png_path).name
    except Exception:
        log.warning("could not plot %s", csv_path, exc_info=True)
        return None


class OrderProcessor:
    """Runs plan §4 for each order.

    stock:   a SpoolmanClient (pendulum.stock)
    design, all_masses, export_3mf, inertia: Thomas's functions (plan §8), or pendulum.dummies
    simulate: pendulum.simulate.simulate (the C++ program, SciPy if it isn't built)
    """

    def __init__(self, stock, design, all_masses, export_3mf, inertia, simulate,
                 printer=None, orders_dir=ORDERS_DIR, output_dir=OUTPUT_DIR):
        self.stock = stock
        self.design, self.all_masses, self.export_3mf, self.inertia = design, all_masses, export_3mf, inertia
        self.simulate = simulate
        self.printer = printer or json.loads(PRINTER_FILE.read_text(encoding="utf-8"))
        self.orders_dir, self.output_dir = Path(orders_dir), Path(output_dir)

    def process_all(self):
        """Process every received or postponed order (the "Process orders" button). Returns them."""
        todo = [o for o in load_orders(self.orders_dir) if o.status in (RECEIVED, POSTPONED)]
        for order in todo:
            self.process(order)
        return todo

    def process(self, order):
        """One order through plan §4. Sets status and reason, saves the order and returns it."""
        try:
            return self._run(order)
        except Exception as e:      # a bug in one order must not stop the others; it is retried next time
            log.exception("order %s failed", order.id)
            return self._finish(order, POSTPONED, f"Error while processing: {e}")

    def _finish(self, order, status, reason=""):
        order.status, order.reason = status, reason
        order.save(self.orders_dir)
        log.info("order %s: %s %s", order.id, status, reason)
        return order

    def _run(self, order):
        problems = check_input(order)
        if problems:
            return self._finish(order, REJECTED, " ".join(problems))

        try:
            filaments = {f["id"]: f for f in self.stock.get_filaments()}
            spools = self.stock.get_spools()
        except StockUnavailable as e:
            return self._finish(order, POSTPONED, f"Stock is offline: {e}")

        chosen = {part: int(order.filament_per_part[part]) for part in PARTS}
        unknown = sorted({fid for fid in chosen.values() if fid not in filaments})
        if unknown:
            return self._finish(order, REJECTED, f"Filament id {unknown} is not in Spoolman.")
        densities = {part: filaments[fid]["density"] for part, fid in chosen.items()}

        try:
            params = self.design(order, densities)
        except InfeasibleDesign as e:
            return self._finish(order, REJECTED, str(e))

        problems = params.validate(self.printer)
        if problems:
            return self._finish(order, REJECTED, " ".join(problems))

        masses = self.all_masses(params, densities)
        need = need_per_filament(masses, chosen)
        # A retry after Spoolman dropped out while registering: filaments already subtracted are skipped.
        registered = order.result.setdefault("registered", {})
        todo = {fid: grams for fid, grams in need.items() if str(fid) not in registered}
        try:
            picked = pick_spools(todo, spools)
        except InsufficientMaterial as e:
            return self._finish(order, POSTPONED, f"Not enough filament. {e}.")

        out = self.output_dir / order.id
        out.mkdir(parents=True, exist_ok=True)
        params.save(out / "design.json")
        files = self.export_3mf(params, out)
        I, M, d = self.inertia(params, masses)
        calc = exact_period(I, M, d, params.StartAng)
        sim, backend = self.simulate(I, M, d, math.radians(params.StartAng), out / "sim.csv")
        plot = _plot_swing(out / "sim.csv", out / "plot.png", f"{order.id}: T = {sim:.3f} s")

        # Filament is subtracted last, so an order that fails earlier uses none.
        try:
            for fid, spool_id in picked.items():
                self.stock.use(spool_id, todo[fid])
                registered[str(fid)] = {"spool": spool_id, "grams": round(todo[fid], 1)}
        except StockUnavailable as e:
            return self._finish(order, POSTPONED, f"Stock went offline while subtracting filament: {e}")

        order.result.update({
            "files": [Path(f).name for f in files],
            "masses_g": {part: round(g, 1) for part, g in masses.items()},
            "period_target_s": order.target_period_s,
            "period_calc_s": round(calc, 4),
            "period_sim_s": round(sim, 4),
            "period_diff_s": round(sim - order.target_period_s, 4),
            "simulator": backend,
            "plot": plot,
        })
        diff_ms = 1000 * (sim - order.target_period_s)
        return self._finish(order, DONE, f"Simulated period is {diff_ms:+.1f} ms from the ordered one.")
