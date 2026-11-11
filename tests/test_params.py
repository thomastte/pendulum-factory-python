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

def test_validate_ok():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    assert p.validate(printer) == []

def test_validate_pendClearance():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.PendClearance = 3
    assert "Arm clearance is too small, must be at least 5 mm." in p.validate(printer)

def test_validate_dimension_zero():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=0, BaseDepth=80, BaseHeight=200)
    problems = p.validate(printer)
    assert "Base width must be positive ." in problems 

def test_validate_dimension_negative():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.AxlDia =-8
    problems = p.validate(printer)
    assert "Axle diameter must be positive ." in problems

def test_validate_arm_length():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=10)
    problems = p.validate(printer)
    assert "Arm length must be positive ." in problems
    assert "Base height must be positive ." not in problems
