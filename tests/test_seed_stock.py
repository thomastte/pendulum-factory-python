# AI-assisted (Claude, 2026-11-03): tests written by Claude.
# Verified: all pass; Øivind read them through and ran them before committing.
"""Tests for scripts/seed_stock.py. None of them need Spoolman: FakeSpoolman stands in for it."""
import json

import pytest
import requests

from scripts.seed_stock import main, seed, validate


class FakeSpoolman:
    """Same methods as SpoolmanClient, but keeps vendors, filaments and spools in lists."""

    def __init__(self, vendors=(), filaments=()):
        self.vendors = list(vendors)
        self.filaments = list(filaments)
        self.spools = []

    def get_vendors(self):
        return self.vendors

    def get_filaments(self):
        return self.filaments

    def create_vendor(self, name):
        vendor = {"id": len(self.vendors) + 1, "name": name}
        self.vendors.append(vendor)
        return vendor

    def create_filament(self, name, vendor_id, material, density, diameter, color_hex, weight=None):
        vendor = next(v for v in self.vendors if v["id"] == vendor_id)
        filament = {"id": len(self.filaments) + 1, "name": name, "vendor": vendor, "material": material,
                    "density": density, "diameter": diameter, "color_hex": color_hex, "weight": weight}
        self.filaments.append(filament)
        return filament

    def create_spool(self, filament_id, initial_weight):
        spool = {"id": len(self.spools) + 1, "filament_id": filament_id, "initial_weight": initial_weight}
        self.spools.append(spool)
        return spool


def entry(**changes):
    """One valid filament from the seed file, with some fields changed."""
    f = {"vendor": "Bambu Lab", "name": "PLA Basic Black", "material": "PLA", "density": 1.24,
         "diameter": 1.75, "color_hex": "000000", "net_weight": 1000}
    f.update(changes)
    return f


def quiet(*args):
    pass


# --- validate -------------------------------------------------------------------------

def test_valid_entry_has_no_problems():
    assert validate([entry(), entry(name="PLA Basic White", color_hex="#ffffff", spools_g=[1000, 350])]) == []


def test_density_zero_is_a_problem():
    """The placeholder in stock_seed.json has density 0.0 until the datasheet value is filled in."""
    problems = validate([entry(density=0.0)])
    assert len(problems) == 1 and "density" in problems[0]


def test_missing_field_is_a_problem():
    f = entry()
    del f["material"]
    assert "missing material" in validate([f])[0]


@pytest.mark.parametrize("color", ["black", "00000", "#12345G"])
def test_bad_color_is_a_problem(color):
    assert "color_hex" in validate([entry(color_hex=color)])[0]


@pytest.mark.parametrize("spools", [[0], [1200], ["full"]])
def test_impossible_spool_is_a_problem(spools):
    assert "spools_g" in validate([entry(spools_g=spools)])[0]


def test_same_filament_twice_is_a_problem():
    assert "twice" in validate([entry(), entry()])[0]


# --- seed ---------------------------------------------------------------------------------

def test_seed_adds_vendor_filament_and_one_full_spool():
    sp = FakeSpoolman()
    added, skipped = seed(sp, [entry()], log=quiet)
    assert (added, skipped) == (["Bambu Lab PLA Basic Black"], [])
    assert [v["name"] for v in sp.vendors] == ["Bambu Lab"]
    assert sp.filaments[0]["weight"] == 1000            # so Spoolman can compute remaining_weight
    assert [s["initial_weight"] for s in sp.spools] == [1000]


def test_seed_spools_g_gives_one_spool_each():
    sp = FakeSpoolman()
    seed(sp, [entry(spools_g=[1000, 350])], log=quiet)
    assert [s["initial_weight"] for s in sp.spools] == [1000, 350]


def test_seed_adds_vendor_once_for_two_filaments():
    sp = FakeSpoolman()
    seed(sp, [entry(), entry(name="PLA Basic White")], log=quiet)
    assert len(sp.vendors) == 1 and len(sp.filaments) == 2


def test_seed_reuses_vendor_already_in_spoolman():
    sp = FakeSpoolman(vendors=[{"id": 7, "name": "Bambu Lab"}])
    seed(sp, [entry()], log=quiet)
    assert len(sp.vendors) == 1
    assert sp.filaments[0]["vendor"]["id"] == 7


def test_seed_skips_filament_already_in_spoolman():
    sp = FakeSpoolman()
    seed(sp, [entry()], log=quiet)
    added, skipped = seed(sp, [entry(), entry(name="PLA Basic White")], log=quiet)
    assert added == ["Bambu Lab PLA Basic White"]
    assert skipped == ["Bambu Lab PLA Basic Black"]
    assert len(sp.spools) == 2                           # no extra spool for the skipped one


def test_seed_sends_color_without_hash():
    sp = FakeSpoolman()
    seed(sp, [entry(color_hex="#ff8800")], log=quiet)
    assert sp.filaments[0]["color_hex"] == "FF8800"


def test_dry_run_adds_nothing():
    sp = FakeSpoolman()
    added, _ = seed(sp, [entry()], dry_run=True, log=quiet)
    assert added == ["Bambu Lab PLA Basic Black"]
    assert sp.vendors == [] and sp.filaments == [] and sp.spools == []


# --- main (the command line) ----------------------------------------------------------------

def write_seed(tmp_path, filaments):
    path = tmp_path / "stock_seed.json"
    path.write_text(json.dumps({"filaments": filaments}), encoding="utf-8")
    return path


def test_main_refuses_a_file_with_problems(tmp_path, monkeypatch, capsys):
    def must_not_be_called(*args, **kwargs):
        raise AssertionError("Spoolman was contacted although the file has problems")

    monkeypatch.setattr(requests, "request", must_not_be_called)
    assert main(["--file", str(write_seed(tmp_path, [entry(density=0.0)]))]) == 1
    assert "nothing was registered" in capsys.readouterr().out


def test_main_says_how_to_start_spoolman_when_offline(tmp_path, monkeypatch, capsys):
    def refused(*args, **kwargs):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(requests, "request", refused)
    assert main(["--file", str(write_seed(tmp_path, [entry()]))]) == 1
    assert "docker compose up -d" in capsys.readouterr().out
