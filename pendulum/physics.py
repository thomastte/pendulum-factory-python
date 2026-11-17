from pendulum.cad import make_U, make_pendulum

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
