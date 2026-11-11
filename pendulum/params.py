from dataclasses import dataclass, field, asdict
import json


@dataclass 
class PrintSettings: 
    infill: float = 0.2
    walls: int = 2
    line_width: float = 0.42


@dataclass
class PendulumParams:
    BaseWidth: int
    BaseDepth: int
    BaseHeight: int
    AxlDia: int = 8
    ArmThick: int = 4
    AxlOvr: int = 2
    ClrGap: int = 1
    ClrDia: int = 14
    ClrThick: float = 3
    PostThickness: int = 6
    PostDepth: int = 30
    BaseThickness: int = 5
    PendClearance: int = 5
    SlotClearance: float = 0.4
    SideClearance: int = 2
    BlockLengthFrac: float = 0.35
    StartAng: int = 45
    WeightPos: float = 6 
    print_settings: PrintSettings = field(default_factory=PrintSettings)


    @property
    def AxlOff(self):
        return self.AxlDia / 2
    @property
    def ArmLength(self):
        return self.BaseHeight - self.BaseThickness - self.PendClearance - self.AxlOff
    @property
    def PostGap(self):
        return self.BaseWidth - 2*(self.PostThickness)
    @property
    def BlockThickness(self): 
        return self.PostGap - 2*(self.SideClearance)
    @property
    def BlockLength(self): 
        return self.BlockLengthFrac * self.ArmLength
    @property
    def BlockArmHeight(self):
        return self.AxlDia
    @property
    def SlotWidth(self): 
        return self.AxlDia + self.SlotClearance
    @property
    def AxleLength(self): 
        return self.BaseWidth + 2*(self.AxlOvr) 


    def validate(self, printer):
        problems = []
        usable = printer["build_volume_mm"][0] - 2*printer["margin_mm"]
        if self.BaseWidth <=0:
            problems.append("Base width must be positive.")
        if self.BaseDepth <=0:
            problems.append("Base depth must be positive.")
        if self.BaseHeight <=0:
            problems.append("Base height must be positive.")
        if self.AxlDia <=0:
            problems.append("Axle diameter must be positive.")
        if self.ArmThick <=0:
            problems.append("Arm thickness must be positive.")
        if self.ArmLength <= 0:
            problems.append("Arm length must be positive.")
        if self.AxlOvr <=0:
            problems.append("Axle overhang must be positive.")
        if self.ClrGap <=0:
            problems.append("Collar gap must be positive.")
        if self.ClrDia <=0:
            problems.append("Collar diameter must be positive.")
        if self.ClrThick <=0:
            problems.append("Collar thickness must be positive.")
        if self.PostThickness <=0:
            problems.append("Post thickness must be positive.")
        if self.PostDepth <=0:
            problems.append("Post depth must be positive.")
        if self.BaseThickness <=0:
            problems.append("Base thickness must be positive.")
        if self.PendClearance < 5:
            problems.append("Arm clearance is too small, must be at least 5 mm.")
        if self.SlotClearance <=0:
            problems.append("Slot clearance must be positive.")
        if self.SideClearance <=0:
            problems.append("Side clearance must be positive.")

        if self.WeightPos - self.BlockLength/2 < self.ClrDia/2:
            problems.append("Block intersects collars.")
        if self.WeightPos + self.BlockLength/2 > self.ArmLength:
            problems.append("Block extends past end of arm.")

        if self.BaseWidth > usable: 
            problems.append("Base too wide for printer.")
        if self.BaseDepth > usable:
            problems.append("Base too deep for printer.")
        if self.BaseHeight > usable:
            problems.append("Base too tall for printer.")

        if self.BlockLengthFrac >= 1 or self.BlockLengthFrac <= 0:
            problems.append("Block length fraction must be between 0 and 1.")
        if self.StartAng > 90 or self.StartAng <= 0:
            problems.append("Start angle must be between 0 and 90.")
        if self.AxleLength > usable or self.ArmLength + self.ClrDia/2 > usable:
            problems.append("Axle length or total length is too long for printer.")
        if self.print_settings.infill <= 0 or self.print_settings.infill > 1:
            problems.append("Infill must be between 0 and 1.")
        if self.print_settings.walls < 1:
            problems.append("Walls must be at least 1.")
        if self.print_settings.line_width <= 0:
            problems.append("Line width must be positive.")

        # AI-assisted (Claude, 2026-11-11): rules O1, O3-O6 below, same pattern as S1-S3. Verified: one test per rule, pytest.
        if self.PostDepth > self.BaseDepth:
            problems.append("Posts are deeper than the base.")
        if self.BlockThickness <= self.ArmThick:
            problems.append("Block is not thicker than the arm.")
        if self.PostGap < 2*(self.ClrGap + self.ClrThick) + self.ArmThick:
            problems.append("Collars and arm do not fit between the posts.")
        if self.ClrDia <= self.AxlDia:
            problems.append("Collar diameter must be larger than the axle diameter.")
        if self.ClrGap >= self.SideClearance:
            problems.append("Collar gap must be smaller than the side clearance.")
        if self.SlotWidth >= self.PostDepth:
            problems.append("Slot leaves no wall in the post.")
        return problems

    

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        d["print_settings"] = PrintSettings(**d["print_settings"])
        return cls(**d)
