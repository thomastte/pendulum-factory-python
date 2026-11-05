# AI-assisted (Claude, 2026-11-03): written by Claude (SpoolmanClient, need_per_filament, pick_spools).
# Verified: tests/test_stock.py; Øivind read it through before committing.
"""Material stock: talk to Spoolman over its REST API.

Paths and field names are checked against Spoolman v0.27.0 (spoolman/api/v1/ in its source).
All weights are in grams. Spoolman answers on http://localhost:7912/api/v1 (docker-compose.yml).
What the user sees when something goes wrong: plan §5.4.
"""
import requests

DEFAULT_URL = "http://localhost:7912/api/v1"
WASTE_FACTOR = 1.1  # extra for purge and skirt (plan §5.2)


class StockUnavailable(Exception):
    """Spoolman did not answer: not running, wrong URL, or slower than the timeout."""


class InsufficientMaterial(Exception):
    """No spool of a filament has enough left for the order.

    The numbers are kept as attributes so the order can be postponed with them (plan §5.4).
    """

    def __init__(self, filament_id, needed_g, available_g):
        self.filament_id = filament_id
        self.needed_g = needed_g
        self.available_g = available_g
        super().__init__(f"Filament {filament_id}: needs {needed_g:.1f} g, "
                         f"the fullest spool has {available_g:.1f} g")


class SpoolmanClient:
    """Thin wrapper around Spoolman's REST API: one method per call we use."""

    def __init__(self, base_url=DEFAULT_URL, timeout=3.0):
        self.base = base_url.rstrip("/")
        self.timeout = timeout  # seconds, for connecting and for each read

    def _call(self, method, path, **kwargs):
        """Send one request to self.base + path and return the JSON answer.

        No answer (refused, unknown host, timeout) -> StockUnavailable.
        An answer with 4xx/5xx -> requests.HTTPError, left as it is: Spoolman is up, so it is
        not "stock offline" but a bug or bad data, and it should be seen, not postponed.
        """
        url = self.base + path
        try:
            r = requests.request(method, url, timeout=self.timeout, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as e:
            raise StockUnavailable(f"Spoolman is not answering at {self.base}") from e
        r.raise_for_status()
        return r.json()

    # --- reading -----------------------------------------------------------------

    def get_vendors(self):
        """GET /vendor -> list of vendors, each {id, name, ...}."""
        return self._call("GET", "/vendor")

    def get_filaments(self):
        """GET /filament -> list of filaments, each {id, name, material, density, diameter,
        color_hex, weight, vendor, ...}."""
        return self._call("GET", "/filament")

    def get_spools(self):
        """GET /spool -> list of spools, each with a nested "filament".

        Archived spools are left out by default. "remaining_weight" is only in the answer
        when the spool has initial_weight or its filament has weight.
        """
        return self._call("GET", "/spool")

    # --- writing ---------------------------------------------------------------------

    def create_vendor(self, name):
        """POST /vendor with {name} -> the new vendor (used by the seed script)."""
        return self._call("POST", "/vendor", json={"name": name})

    def create_filament(self, name, vendor_id, material, density, diameter, color_hex, weight=None):
        """POST /filament -> the new filament (used by the seed script).

        density [g/cm3] and diameter [mm] are required by Spoolman. color_hex without "#",
        e.g. "000000". weight = net grams on a full spool. Fields that are None are left out.
        """
        body = {"name": name, "vendor_id": vendor_id, "material": material, "density": density,
                "diameter": diameter, "color_hex": color_hex, "weight": weight}
        return self._call("POST", "/filament", json={k: v for k, v in body.items() if v is not None})

    def create_spool(self, filament_id, initial_weight):
        """POST /spool with {filament_id, initial_weight} -> the new spool (used by the seed script).

        initial_weight = net grams on the label. Always set it, or remaining_weight is missing.
        """
        return self._call("POST", "/spool",
                          json={"filament_id": filament_id, "initial_weight": initial_weight})

    def use(self, spool_id, grams):
        """PUT /spool/{spool_id}/use with {"use_weight": grams rounded to 0.1} -> the updated spool.

        Sends use_weight only; with use_length as well, Spoolman answers 400.
        A negative amount would put filament back on the spool, so it is refused.
        """
        if grams < 0:
            raise ValueError(f"grams must be 0 or more, got {grams}")
        return self._call("PUT", f"/spool/{spool_id}/use", json={"use_weight": round(grams, 1)})


def need_per_filament(masses_g, filament_per_part, waste=WASTE_FACTOR):
    """Grams of each filament one order needs.

    masses_g:          {part: grams}, from Thomas's all_masses()
    filament_per_part: {part: filament_id}, from the order
    Returns {filament_id: grams}: the parts on the same filament added up, times waste.
    Filament ids are made int, because Spoolman's ids are ints and a form sends strings:
    "3" would never match 3 in pick_spools.
    """
    need = {}
    for part, grams in masses_g.items():
        if part not in filament_per_part:
            raise ValueError(f"No filament chosen for part {part!r}")
        fid = int(filament_per_part[part])
        need[fid] = need.get(fid, 0.0) + grams
    return {fid: grams * waste for fid, grams in need.items()}


def pick_spools(need_g, spools):
    """Choose one spool for each filament.

    need_g: {filament_id: grams}. spools: the list from get_spools().
    Returns {filament_id: spool_id}. Among the spools of that filament with enough left,
    take the one with the least left, so spools get used up (plan §5.2).
    One spool per filament: two half-full spools that only together would be enough
    count as not enough, since the printer takes one spool per filament.
    Spools without "remaining_weight" are skipped (Spoolman leaves it out when it can't
    compute it). No spool has enough -> InsufficientMaterial.
    """
    chosen = {}
    for fid, grams in need_g.items():
        known = [s for s in spools
                 if s["filament"]["id"] == fid and s.get("remaining_weight") is not None]
        enough = [s for s in known if s["remaining_weight"] >= grams]
        if not enough:
            most = max((s["remaining_weight"] for s in known), default=0.0)
            raise InsufficientMaterial(fid, grams, most)
        chosen[fid] = min(enough, key=lambda s: s["remaining_weight"])["id"]
    return chosen
