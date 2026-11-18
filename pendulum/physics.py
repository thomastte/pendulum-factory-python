from pendulum.cad import make_U, make_pendulum
import cadquery as cq
import math
from scipy.special import ellipk
from pendulum.params import PendulumParams
from pendulum.processing import InfeasibleDesign

def part_mass(solid, density, settings):
    V = solid.val().Volume()
    A = solid.val().Area()
    infill = settings.infill
    walls = settings.walls
    line_width = settings.line_width
    V_walls = min(V, A * walls * line_width)
    V_eff = V_walls + infill * (V - V_walls)
    mass = density * V_eff / 1000
    return  mass

def all_masses(p, densities):
    U = make_U(p)
    stand_mass = part_mass(U, densities["u_stand"], p.print_settings)
    pendulum = make_pendulum(p)
    pendulum_mass = part_mass(pendulum, densities["pendulum"], p.print_settings)
    masses = {"u_stand": stand_mass, "pendulum": pendulum_mass }
    return masses

def inertia(p, masses):
    solid = make_pendulum(p).val()
    c = solid.Center()
    V = solid.Volume()
    J = cq.Shape.matrixOfInertia(solid)
    m = masses["pendulum"]
    I = m * (J[0][0] / V + c.y**2 + c.z**2) * 1e-9
    M = m/1000
    d = math.sqrt(c.y**2 + c.z**2)/1000
    return I, M, d

def period(p, I, M, d):
    g = 9.81
    rad = math.radians(p.StartAng/2)
    K = math.sin(rad)
    T = 4 * math.sqrt(I / (M*g*d)) * ellipk(K**2)
    return T

def bisect(f, lo, hi, tol = 0.01, max_iter = 60):
    flo = f(lo)
    fhi = f(hi)
    if flo * fhi > 0: raise ValueError("f(lo) and f(hi) have the same sign: no root between lo and hi")
    for i in range(max_iter):
        mid = (hi + lo)/2
        fmid = f(mid)

        if flo*fmid <= 0:
            hi = mid
        else: 
            lo = mid
            flo = fmid

        if hi - lo < tol:
            break
    return (lo + hi)/2


def design(order, densities):
    p = PendulumParams(BaseWidth = round(order.base_width_mm), BaseDepth = round(order.base_depth_mm), BaseHeight = round(order.base_height_mm))

    def f(w):
        p.WeightPos = w
        m = all_masses(p, densities)
        I, M, d = inertia(p, m)
        T = period(p, I, M, d)
        return T - order.target_period_s
    lo = p.ClrDia/2 + p.BlockLength/2 + 0.1
    hi = p.ArmLength - p.BlockLength/2

    try:
        p.WeightPos = bisect(f, lo, hi)
    except ValueError:
        T_lo = f(lo) + order.target_period_s 
        T_hi = f(hi) + order.target_period_s
        raise InfeasibleDesign(f"A period of {order.target_period_s:.3f} s can't be made with this kit size; it can reach {T_lo:.3f} to {T_hi:.3f} s.")
    return p