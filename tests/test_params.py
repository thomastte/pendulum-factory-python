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
    p.WeightPos = 100
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
    assert "Base width must be positive." in problems 

def test_validate_dimension_negative():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.AxlDia =-8
    problems = p.validate(printer)
    assert "Axle diameter must be positive." in problems

def test_validate_arm_length():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=10)
    problems = p.validate(printer)
    assert "Arm length must be positive." in problems
    assert "Base height must be positive." not in problems

def test_validate_base_width():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=300, BaseDepth=200, BaseHeight=200)
    problems = p.validate(printer)
    assert "Base too wide for printer." in problems


# AI-assisted (Claude, 2026-11-11): tests for S2, O1 and O3-O6 below, same pattern as the S1/S3 tests. Verified: pytest.
def test_validate_block_top():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 20    # block top at 20 - 65.1/2 = -12.55 mm, above the collar edge at 7 mm
    problems = p.validate(printer)
    assert "Block intersects collars." in problems

def test_validate_block_bottom():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 170   # block bottom at 170 + 65.1/2 = 202.55 mm, past the arm tip at 186 mm
    problems = p.validate(printer)
    assert "Block extends past end of arm." in problems

def test_validate_post_depth():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=20, BaseHeight=200)
    p.WeightPos = 100
    problems = p.validate(printer)
    assert "Posts are deeper than the base." in problems

def test_validate_block_thickness():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=20, BaseDepth=80, BaseHeight=200)   # BlockThickness = 20 - 12 - 4 = 4
    p.WeightPos = 100
    problems = p.validate(printer)
    assert "Block is not thicker than the arm." in problems

def test_validate_post_gap():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=22, BaseDepth=80, BaseHeight=200)   # PostGap = 10, needs 12
    p.WeightPos = 100
    problems = p.validate(printer)
    assert "Collars and arm do not fit between the posts." in problems
    assert "Block is not thicker than the arm." not in problems

def test_validate_collar_diameter():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 100
    p.ClrDia = 6
    problems = p.validate(printer)
    assert "Collar diameter must be larger than the axle diameter." in problems

def test_validate_collar_gap():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 100
    p.ClrGap = 2    # equal to SideClearance, must be smaller
    problems = p.validate(printer)
    assert "Collar gap must be smaller than the side clearance." in problems

def test_validate_slot_width():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 100
    p.PostDepth = 8     # SlotWidth = 8.4
    problems = p.validate(printer)
    assert "Slot leaves no wall in the post." in problems


# AI-assisted (Claude, 2026-11-11): tests for S4a, S4b, O2, O7 and O8 below, same pattern as the tests above. Verified: pytest.
def test_validate_base_height():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=250)    # usable is 246
    p.WeightPos = 100
    problems = p.validate(printer)
    assert "Base too tall for printer." in problems

def test_validate_base_width_at_limit():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=246, BaseDepth=80, BaseHeight=200)   # exactly usable: the U fits
    p.WeightPos = 100
    problems = p.validate(printer)
    assert "Base too wide for printer." not in problems

def test_validate_reads_printer():
    small = {"build_volume_mm": [200, 200, 200], "margin_mm": 5}     # usable 190
    real = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}      # usable 246
    p = PendulumParams(BaseWidth=195, BaseDepth=80, BaseHeight=150)
    p.WeightPos = 70
    assert "Base too wide for printer." in p.validate(small)
    assert "Base too wide for printer." not in p.validate(real)

def test_validate_axle_length():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=244, BaseDepth=80, BaseHeight=200)   # AxleLength = 248, the U still fits
    p.WeightPos = 100
    problems = p.validate(printer)
    assert "Axle length or total length is too long for printer." in problems
    assert "Base too wide for printer." not in problems

def test_validate_block_length_frac():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 100
    p.BlockLengthFrac = 1    # boundary: must be less than 1
    problems = p.validate(printer)
    assert "Block length fraction must be between 0 and 1." in problems

def test_validate_start_angle_zero():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 100
    p.StartAng = 0    # boundary: must be greater than 0
    problems = p.validate(printer)
    assert "Start angle must be between 0 and 90." in problems

def test_validate_start_angle_90_ok():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 100
    p.StartAng = 90   # boundary: 90 is allowed
    problems = p.validate(printer)
    assert "Start angle must be between 0 and 90." not in problems

def test_validate_infill_zero():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 100
    p.print_settings.infill = 0
    problems = p.validate(printer)
    assert "Infill must be between 0 and 1." in problems

def test_validate_infill_one_ok():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 100
    p.print_settings.infill = 1    # solid part is allowed
    problems = p.validate(printer)
    assert "Infill must be between 0 and 1." not in problems

def test_validate_walls():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 100
    p.print_settings.walls = 0
    problems = p.validate(printer)
    assert "Walls must be at least 1." in problems

def test_validate_line_width():
    printer = {"build_volume_mm": [256, 256, 256], "margin_mm": 5}
    p = PendulumParams(BaseWidth=80, BaseDepth=80, BaseHeight=200)
    p.WeightPos = 100
    p.print_settings.line_width = 0
    problems = p.validate(printer)
    assert "Line width must be positive." in problems
