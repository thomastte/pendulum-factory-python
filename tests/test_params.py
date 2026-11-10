from pendulum.params import PendulumParams

def test_arm_length():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    assert p.ArmLength == 186   #200 - 5 - 5 - 4

def test_arm_length_follows_height():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    assert p.ArmLength == 186
    p.BaseHeight = 250
    assert p.ArmLength == 250 - 5 - 5 - 4
    p.BaseHeight = 100
    assert p.ArmLength == 100 - 5 - 5 - 4

def test_block_thickness():
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    assert p.BlockThickness == 80 - 2*6 - 2*2
    p.BaseWidth = 150
    assert p.BlockThickness == 150 - 2*6 - 2*2

def test_save_load(tmp_path):
    path = tmp_path/ "design.json"
    p = PendulumParams(BaseWidth=150, BaseDepth= 50, BaseHeight= 200)
    p.save(path)
    q = PendulumParams.load(path)
    assert q == p
    