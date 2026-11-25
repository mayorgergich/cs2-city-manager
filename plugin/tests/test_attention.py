"""Tests for city.py attention (and its section in report.py) on the made-up map (made_up_map.py), with the parts a
grown city's snapshot has added by hand: a budget running out, power and sewage short, a full school, homeless people,
unemployment, unhappy citizens, a slow Main Street, a crowded bus line, low office demand, warning icons."""
import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "skills/city-manager/scripts"))
import made_up_map as mm  # noqa: E402
import city  # noqa: E402


def grown():
    s = mm.snapshot()
    s["city"].update(population=1200, money=50000)
    s["budget"] = {"income": {"TaxResidential": 2000}, "expenses": {"ServiceUpkeep": 8000, "LoanInterest": 2000},
                   "totalIncome": 2000, "totalExpenses": 12000, "balance": -10000}
    s["loan"] = {"amount": 100000, "interestPercent": 2.5, "monthlyCost": 2000, "limit": 500000}
    s["utilities"] = {"electricity": {"production": 8000, "consumption": 10000, "fulfilled": 9000, "import": 0},
                      "water": {"freshCapacity": 1000, "freshConsumption": 950, "sewageCapacity": 1000, "sewageConsumption": 1200}}
    s["buildings"] += [
        {"id": 60, "prefab": 4, "kind": "service", "name": "Elementary School", "x": 20.0, "z": 0.0, "use": {"what": "pupils", "now": 98, "max": 100}},
        {"id": 61, "prefab": 4, "kind": "service", "name": "Medical Clinic", "x": 20.0, "z": 100.0, "use": {"what": "patients", "now": 88, "max": 100}},
        {"id": 62, "prefab": 4, "kind": "service", "name": "Landfill", "x": 400.0, "z": 500.0, "efficiency": 40},
        {"id": 63, "prefab": 4, "kind": "residential", "name": "House", "x": 30.0, "z": -50.0, "abandoned": True},
        {"id": 64, "prefab": 4, "kind": "residential", "name": "House", "x": 30.0, "z": -60.0, "abandoned": True}]
    s["people"] = {"households": 400, "residents": 1200, "workable": 700, "workers": 616, "unemploymentPercent": 12.0,
                   "homelessHouseholds": 10, "homeless": 30}
    s["jobs"] = {"total": 1000, "free": 300, "filled": 700, "totalByEducation": [400, 300, 200, 100, 0], "freeByEducation": [0, 50, 200, 50, 0]}
    s["happiness"] = {"average": 45, "factors": [{"factor": "TrafficPenalty", "points": -6}, {"factor": "Tax", "points": -3},
                                                 {"factor": "Healthcare", "points": 4}]}
    for e in s["edges"]:
        if e.get("street") == 2:
            e.update(flow=35, volume=500)
        elif e.get("street") == 3:
            e.update(flow=55, volume=90)
        elif e.get("kind") in ("road", "highway"):
            e.update(flow=100, volume=200)
    s["transit"] = [{"kind": "Bus", "name": "Bus 1", "vehicles": 4, "usagePercent": 95, "active": True,
                     "stops": [{"x": 0, "z": 0, "name": "Market", "waiting": 60}, {"x": 0, "z": 100, "waiting": 3}]},
                    {"kind": "Tram", "name": "Tram 2", "vehicles": 0, "usagePercent": 0, "active": True, "stops": []}]
    s["demand"] = {"residentialLow": 80, "residentialMedium": 30, "residentialHigh": 20, "commercial": 40, "industrial": 30,
                   "office": 5, "storage": 0,
                   "factors": {"office": {"Taxes": -40, "EducatedWorkforce": -20, "BuildingDemand": 100},
                               "storage": {"Warehouses": -5}}}
    s["problems"] = {"kinds": [{"id": "NoCustomers", "title": "Not enough customers", "count": 25}],
                     "items": [{"kind": 0, "x": 0, "z": 0, "on": "road", "street": 2}] * 3}
    return s


class Attention(unittest.TestCase):
    def test_a_city_in_trouble(self):
        items = city.attention(grown())
        fix = [(a, t) for lv, a, t in items if lv == "fix"]
        watch = [(a, t) for lv, a, t in items if lv == "watch"]
        self.assertEqual([a for a, _ in fix], ["Money", "Power", "Sewage", "Services", "Homeless", "Jobs", "Happiness", "Traffic", "Warning icons"],
                         "fix first, in a fixed order")
        text = dict(fix)
        self.assertIn("losing $10,000 a month: $50,000 lasts about 5 months", text["Money"])
        self.assertIn("service upkeep $8,000", text["Money"])
        self.assertIn("short: the city needs 1.0 MW and gets 900 kW", text["Power"])
        s = grown()
        s["utilities"]["electricity"].update(fulfilled=10000, production=0, consumption=10000, **{"import": 10000})
        s["budget"]["expenses"]["ImportElectricity"] = 4700
        self.assertIn(("watch", "Power", "all 1.0 MW comes from outside, at $4,700 a month"), city.attention(s))
        self.assertIn("full (pupils): Elementary School near Main Street (98%)", text["Services"])
        self.assertIn("30 people (10 households)", text["Homeless"])
        self.assertEqual(text["Jobs"], "unemployment 12.0% (84 of 700 who could work), yet 300 jobs are empty, most of them for "
                                       "educated workers (200): more jobs that fit the people here, or schools, as much as more jobs")
        self.assertEqual(text["Happiness"], "45: pulled down by traffic (-6), taxes (-3)")
        self.assertEqual(text["Traffic"], "1 street below 40% of free-flow speed: Main Street (35%, 300 m)")
        self.assertEqual(text["Warning icons"], "Not enough customers ×25 (near Main Street)")
        w = "\n".join(f"{a}: {t}" for a, t in watch)
        for line in ("Money: a loan of $100,000", "Water: 950 of 1,000 m³ used", "Services: nearly full (patients): Medical Clinic",
                     "Services: running below 60%: Landfill", "Traffic: 1 more below 60%: Old Lane (55%,", "Transit: Bus 1 is 95% full: add vehicles",
                     "Transit: Bus 1: 60 waiting at Market", "Transit: Tram 2 isn't running", "Demand: high for low-density homes: room to zone more",
                     "Demand: low for offices (5): held back by taxes, too few educated workers", "Demand: low for warehouses (0): held back by warehouses",
                     "Buildings: 2 abandoned"):
            self.assertIn(line, w)
        self.assertNotIn("jobs are empty", w, "empty jobs only count as a worker shortage when unemployment is low")

    def test_a_quiet_city_and_unlimited_money(self):
        md = city.attention_markdown(mm.snapshot())
        self.assertIn("Nothing stands out", md)
        s = grown()
        s["city"]["unlimitedMoney"] = True
        self.assertNotIn("losing", "\n".join(t for _, _, t in city.attention(s)))
        s = grown()
        s["city"]["money"] = 5_000_000
        self.assertNotIn("losing", "\n".join(t for _, _, t in city.attention(s)), "years of money in the bank: no warning")

    def test_empty_jobs_when_unemployment_is_low(self):
        s = grown()
        s["people"]["unemploymentPercent"] = 2.0
        text = {a: t for _, a, t in city.attention(s) if a == "Jobs"}
        self.assertEqual(text["Jobs"], "300 of 1,000 jobs are empty: not enough workers, mostly for educated people (200)")

    def test_in_the_report_and_the_prep(self):
        import report
        base = Path(tempfile.mkdtemp(prefix="cm-attention-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        before = mm.snapshot()
        now = grown()
        now["taken"] = "2026-11-25T22:00:00Z"
        (base / "city-start.json").write_text(json.dumps(before), encoding="utf-8")
        (base / "city.json").write_text(json.dumps(now), encoding="utf-8")
        for extra in ([], ["--prep"]):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = report.main(["report.py", str(base / "city.json"), *extra])
            self.assertEqual(code, 0, out.getvalue())
            self.assertIn("**Fix first**", out.getvalue())
            self.assertIn("- Power: short", out.getvalue())


if __name__ == "__main__":
    unittest.main()
