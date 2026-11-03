# AI-assisted (Claude, 2026-11-03): tests written by Claude.
# Verified: all pass; Øivind read them through and ran them before committing.
"""Tests for pendulum/stock.py.

None of them need Spoolman, except the integration test at the bottom:
docker compose up -d, then  pytest -m integration
"""
import pytest
import requests

from pendulum.stock import (InsufficientMaterial, SpoolmanClient, StockUnavailable,
                            need_per_filament, pick_spools)


def spool(spool_id, filament_id, remaining=None):
    """A spool the way GET /spool returns it, with only the fields we use.
    remaining=None leaves "remaining_weight" out, as Spoolman does when it can't compute it."""
    s = {"id": spool_id, "filament": {"id": filament_id}}
    if remaining is not None:
        s["remaining_weight"] = remaining
    return s


class FakeResponse:
    """Stands in for requests.Response: status 200 and a fixed JSON body."""

    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


@pytest.fixture
def sent(monkeypatch):
    """Replace requests.request with a fake that records each call and answers {}."""
    calls = []

    def fake(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse({})

    monkeypatch.setattr(requests, "request", fake)
    return calls


# --- Spoolman not answering ---------------------------------------------------------

def test_timeout_gives_stock_unavailable(monkeypatch):
    """Spoolman slower than the timeout -> StockUnavailable, not requests.Timeout."""
    def too_slow(*args, **kwargs):
        raise requests.Timeout("too slow")

    monkeypatch.setattr(requests, "request", too_slow)
    with pytest.raises(StockUnavailable):
        SpoolmanClient().get_spools()


def test_nothing_listening_gives_stock_unavailable():
    """Nothing on that port -> StockUnavailable, within about the timeout."""
    with pytest.raises(StockUnavailable):
        SpoolmanClient("http://127.0.0.1:9/api/v1", timeout=0.5).get_spools()


def test_timeout_is_sent_with_every_call(sent):
    """Without timeout=..., requests waits forever if Spoolman hangs."""
    SpoolmanClient(timeout=1.5).get_filaments()
    assert sent[0]["timeout"] == 1.5


# --- What is sent to Spoolman ---------------------------------------------------------

def test_use_sends_rounded_weight(sent):
    SpoolmanClient("http://x/api/v1").use(7, 12.345)
    assert sent[0]["method"] == "PUT"
    assert sent[0]["url"] == "http://x/api/v1/spool/7/use"
    assert sent[0]["json"] == {"use_weight": 12.3}


def test_use_refuses_negative_grams(sent):
    with pytest.raises(ValueError):
        SpoolmanClient().use(7, -5)
    assert sent == []  # nothing was sent


def test_create_filament_leaves_out_none(sent):
    SpoolmanClient().create_filament("PLA Basic Black", 1, "PLA", 1.26, 1.75, "000000")
    assert "weight" not in sent[0]["json"]
    assert sent[0]["json"]["density"] == 1.26


# --- need_per_filament ----------------------------------------------------------------

def test_need_adds_parts_on_same_filament_and_waste():
    masses = {"base": 10.0, "arm": 20.0, "weight": 5.0}
    filament = {"base": 1, "arm": 1, "weight": 2}
    assert need_per_filament(masses, filament, waste=1.1) == pytest.approx({1: 33.0, 2: 5.5})


def test_need_turns_filament_ids_into_int():
    """A form sends "1"; Spoolman's ids are ints."""
    assert need_per_filament({"base": 10.0}, {"base": "1"}, waste=1.0) == {1: 10.0}


def test_need_raises_when_a_part_has_no_filament():
    with pytest.raises(ValueError):
        need_per_filament({"base": 10.0, "arm": 5.0}, {"base": 1})


# --- pick_spools --------------------------------------------------------------------------

def test_pick_takes_the_smallest_spool_that_is_enough():
    spools = [spool(11, 1, 50), spool(12, 1, 150), spool(13, 1, 900), spool(21, 2, 1000)]
    assert pick_spools({1: 100}, spools) == {1: 12}


def test_pick_one_spool_per_filament():
    spools = [spool(11, 1, 500), spool(21, 2, 300)]
    assert pick_spools({1: 100, 2: 100}, spools) == {1: 11, 2: 21}


def test_pick_raises_when_no_spool_is_enough():
    spools = [spool(11, 1, 300), spool(12, 1, 250)]
    with pytest.raises(InsufficientMaterial) as err:
        pick_spools({1: 500}, spools)
    assert (err.value.needed_g, err.value.available_g) == (500, 300)
    assert "500.0 g" in str(err.value) and "300.0 g" in str(err.value)


def test_pick_raises_when_filament_has_no_spools():
    with pytest.raises(InsufficientMaterial) as err:
        pick_spools({3: 10}, [spool(11, 1, 900)])
    assert err.value.available_g == 0.0


def test_pick_skips_spool_without_remaining_weight():
    spools = [spool(11, 1, None), spool(12, 1, 200)]
    assert pick_spools({1: 100}, spools) == {1: 12}


# --- Against the real Spoolman: pytest -m integration ---------------------------------------

@pytest.mark.integration
def test_spoolman_answers():
    """Read-only, so it doesn't change the stock. Needs: docker compose up -d."""
    client = SpoolmanClient()
    assert isinstance(client.get_filaments(), list)
    assert isinstance(client.get_spools(), list)
