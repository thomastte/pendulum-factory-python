# AI-assisted (Claude, 2026-10-29): test drafted by Claude.
import numpy as np
import pytest
from scipy.special import ellipk

from pendulum.simulate import find_simulator, simulate_cpp, simulate_scipy

G = 9.81
M, L = 0.05, 0.2            # point mass 50 g on 0.2 m: I = M L^2, d = L


def exact_period(theta0):
    return 4 * np.sqrt(L / G) * ellipk(np.sin(theta0 / 2) ** 2)


@pytest.mark.parametrize("deg", [5, 45])
def test_scipy_matches_exact(deg):
    th0 = np.radians(deg)
    _, _, T = simulate_scipy(M * L**2, M, L, th0)
    assert T == pytest.approx(exact_period(th0), rel=1e-8)


@pytest.mark.skipif(find_simulator() is None, reason="C++ simulator not built")
@pytest.mark.parametrize("deg", [5, 45])
def test_cpp_matches_exact(deg, tmp_path):
    th0 = np.radians(deg)
    T = simulate_cpp(M * L**2, M, L, th0, tmp_path / "sim.csv")
    assert T == pytest.approx(exact_period(th0), rel=1e-9)
