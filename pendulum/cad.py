import cadquery as cq

def make_axle(p):
    axle = cq.Workplane("YZ").cylinder(p.AxleLength, p.AxlDia/2)
    return axle

def make_collars(p):
    collar_right = cq.Workplane("YZ").cylinder(p.ClrThick, p.ClrDia/2).translate((p.PostGap/2 - p.ClrGap - p.ClrThick/2, 0, 0)).cut(make_axle(p))
    collar_left =  cq.Workplane("YZ").cylinder(p.ClrThick, p.ClrDia/2).translate((- (p.PostGap/2 - p.ClrGap - p.ClrThick/2), 0, 0)).cut(make_axle(p))
    collar = collar_right.union(collar_left)
    return collar
