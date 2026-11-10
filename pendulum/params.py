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
        if self.PendClearance < 5:
            problems.append("Arm clearance is too small, must be at least 5 mm.")
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
