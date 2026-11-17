from pendulum.cad import make_U, make_pendulum
import cadquery as cq
import math
from scipy.special import ellipk

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
    stand_mass = part_mass(U, densities["stand"], p.print_settings)
    pendulum = make_pendulum(p)
    pendulum_mass = part_mass(pendulum, densities["pendulum"], p.print_settings)
    masses = {"stand": stand_mass, "pendulum": pendulum_mass }
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