from pendulum.params import PendulumParams
from pendulum.cad import make_axle
import math 
import pytest

def test_axle_volume():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    axle = make_axle(p)
    volume = axle.val().Volume()
    assert volume == pytest.approx(p.AxleLength*math.pi*(p.AxlDia/2)**2)