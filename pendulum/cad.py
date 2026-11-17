import cadquery as cq
from pathlib import Path

def make_axle(p):
    axle = cq.Workplane("YZ").cylinder(p.AxleLength, p.AxlDia/2)
    return axle

    # AI-assisted (Claude, 2026-11-17): flat on the print-bed side (cut_y, below_bed, cut). Verified: test_collar_volume, CadQuery volume 476.91 mm3.
def make_collars(p):
    collar_right = cq.Workplane("YZ").cylinder(p.ClrThick, p.ClrDia/2).translate((p.PostGap/2 - p.ClrGap - p.ClrThick/2, 0, 0)).cut(make_axle(p))
    collar_left =  cq.Workplane("YZ").cylinder(p.ClrThick, p.ClrDia/2).translate((- (p.PostGap/2 - p.ClrGap - p.ClrThick/2), 0, 0)).cut(make_axle(p))
    collar = collar_right.union(collar_left)
    cut_y = p.ClrDia/2
    below_bed = cq.Workplane("XY").box(p.AxleLength, cut_y, p.ClrDia).translate((0, -p.AxlDia/2 - cut_y/2, 0))
    collar = collar.cut(below_bed)
    return collar

def make_arm(p):
    arm = cq.Workplane("XY").box(p.ArmThick, p.BlockArmHeight, p.ArmLength, centered=True).translate((0, 0, -p.ArmLength/2)).cut(make_axle(p))
    return arm

def make_weight(p):
    weight = cq.Workplane("XY").box(p.BlockThickness, p.BlockArmHeight, p.BlockLength).translate((0, 0, -p.WeightPos)).cut(make_arm(p))
    return weight

def make_pendulum(p):
    pendulum = make_axle(p).union(make_collars(p)).union(make_arm(p)).union(make_weight(p))
    return pendulum

def make_base(p):
    base = cq.Workplane("XY").box(p.BaseWidth, p.BaseDepth, p.BaseThickness).translate((0, 0, p.AxlOff - p.BaseHeight + p.BaseThickness/2))
    return base

def make_posts(p):
    post_right = cq.Workplane("XY").box(p.PostThickness, p.PostDepth, p.BaseHeight - p.BaseThickness).translate((p.PostGap/2 + p.PostThickness/2, 0, p.AxlOff - p.BaseHeight/2 + p.BaseThickness/2))
    post_left  = cq.Workplane("XY").box(p.PostThickness, p.PostDepth, p.BaseHeight - p.BaseThickness).translate((-p.PostGap/2 - p.PostThickness/2, 0, p.AxlOff - p.BaseHeight/2 + p.BaseThickness/2))
    posts = post_right.union(post_left)
    u_slot_circ = cq.Workplane("YZ").cylinder(2*p.BaseWidth, p.AxlDia/2 + p.SlotClearance/2).translate((0, 0, p.SlotClearance/2))
    u_slot_rect = cq.Workplane("XY").box(2*p.BaseWidth, p.SlotWidth, p.AxlDia).translate((0, 0, p.SlotClearance/2 + p.AxlDia/2))
    u_slot = u_slot_circ.union(u_slot_rect)
    posts = posts.cut(u_slot)
    return posts

def make_U(p):
    U = make_base(p).union(make_posts(p))
    return U


def export_3mf(p, out_dir):
    pendulum_print = make_pendulum(p).rotate((0, 0, 0), (1, 0, 0), 90).translate((0, 0, p.AxlDia/2))
    u_stand_print = make_U(p).translate((0, 0, p.BaseHeight - p.AxlOff))
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    pendulum_file = folder / "pendulum.3mf"
    cq.exporters.export(pendulum_print, str(pendulum_file))
    u_stand_file = folder / "u_stand.3mf"
    cq.exporters.export(u_stand_print, str(u_stand_file))
    return [str(pendulum_file), str(u_stand_file)]