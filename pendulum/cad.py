import cadquery as cq

def make_axle(p):
    axle = cq.Workplane("YZ").cylinder(p.AxleLength, p.AxlDia/2)
    return axle

