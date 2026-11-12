from pendulum.params import PendulumParams
from pendulum.cad import make_axle 
from pendulum.cad import make_collars
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
    assert volume == pytest.approx(2 * math.pi * ((p.ClrDia/2)**2 - (p.AxlDia/2)**2) * p.ClrThick)