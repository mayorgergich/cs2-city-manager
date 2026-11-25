using System;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Threading;
using CityManager;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Xunit;

namespace CityManager.Tests
{
    /// <summary>city.json as format/README.md describes it, without the game: CityReader fills the same object in game.</summary>
    public class CitySnapshotTests
    {
        private static JObject Parse(string json)
        {
            using var reader = new JsonTextReader(new StringReader(json)) { DateParseHandling = DateParseHandling.None };
            return JObject.Load(reader);
        }

        private static CitySnapshot Sample()
        {
            var s = new CitySnapshot { Mod = "0.6.0", Taken = "2026-11-24T21:05:00Z", Why = "save", Save = "Riverton", Name = "Riverton",
                Population = 12345, Happiness = 62, Money = -2500, Xp = 900, Milestone = 5, Year = 2026, Month = 6, Hour = 14, DateText = "June 2026, 14:00" };
            s.Income.Add(new System.Collections.Generic.KeyValuePair<string, int>("TaxResidential", 41000));
            s.Expenses.Add(new System.Collections.Generic.KeyValuePair<string, int>("ServiceUpkeep", 38000));
            s.TotalIncome = 41000; s.TotalExpenses = 38000; s.Balance = 3000;
            var small = s.Prefabs.Of("Small Road");
            var street = s.Streets.Of("Rue de l'Église 🏙");
            s.AddNode(new CitySnapshot.Node { Id = 812, X = 120.54f, Z = -400.26f, Y = 31f, Lights = true });
            s.AddNode(new CitySnapshot.Node { Id = 815, X = 150f, Z = -385.3f, Y = 31f });
            s.AddEdge(new CitySnapshot.Edge { Id = 901, Prefab = small, Kind = "road", A = 812, B = 815, Street = street, Length = 84.23f,
                Pts = new[] { 120.54f, -400.26f, 31f, 130.1f, -395f, 31f, 140.2f, -390.1f, 31f, 150f, -385.3f, 31f },
                HasLanes = true, LanesForward = 1, LanesBackward = 1, Flow = 92 });
            s.AddEdge(new CitySnapshot.Edge { Id = 902, Prefab = s.Prefabs.Of("Highway Oneway - 2 lanes"), Kind = "highway", A = 815, B = 812,
                Length = 40f, HasLanes = true, LanesForward = 2, BusForward = 1, ElevationA = -12.04f, ElevationB = -8f, Tunnel = true, Owned = true });
            s.AddBuilding(new CitySnapshot.Building { Prefab = s.Prefabs.Of("EU_ResidentialLow01"), Kind = "residential", Level = 2, LotWidth = 2, LotDepth = 3,
                X = 140f, Z = -420f, Y = 31f, Angle = 89.6f });
            s.AddBuilding(new CitySnapshot.Building { Prefab = s.Prefabs.Of("Hospital01"), Kind = "service", Service = "Healthcare", Name = "Hospital",
                LotWidth = 10, LotDepth = 8, Abandoned = true });
            var d = new CitySnapshot.District { Name = "Mill Row" };
            d.Outline.Add(new[] { 100f, -500f });
            d.Outline.Add(new[] { 300f, -500f });
            d.Outline.Add(new[] { 300f, -300f });
            s.AddDistrict(d);
            s.Tiles.Add(new[] { -937f, -313f, -937f, -313f });
            s.OwnedTiles = 1;
            s.TerrainSize = 2; s.TerrainCell = 56f; s.TerrainOrigin = -7168f;
            s.Heights = new ushort[] { 0, 1, 256, 65535 };
            s.Water = new ushort[] { 0, 0, 12, 0 };
            return s;
        }

        [Fact]
        public void WritesTheDocumentedFormat()
        {
            var j = Parse(Sample().ToJson());
            Assert.Equal(1, (int)j["format"]);
            Assert.Equal("save", (string)j["why"]);
            Assert.Equal("Riverton", (string)j["save"]);
            Assert.Equal("Riverton", (string)j["city"]["name"]);
            Assert.Equal(-2500, (int)j["city"]["money"]);
            Assert.Equal(6, (int)j["city"]["date"]["month"]);
            Assert.Equal("June 2026, 14:00", (string)j["city"]["date"]["text"]);
            Assert.Equal(41000, (int)j["budget"]["income"]["TaxResidential"]);
            Assert.Equal(38000, (int)j["budget"]["expenses"]["ServiceUpkeep"]);
            Assert.Equal(3000, (int)j["budget"]["balance"]);
            Assert.Equal(new[] { "Small Road", "Highway Oneway - 2 lanes", "EU_ResidentialLow01", "Hospital01" }, j["prefabs"].Select(t => (string)t).ToArray());
            Assert.Equal("Rue de l'Église 🏙", (string)j["streets"][0]);
            Assert.Equal(2, (int)j["counts"]["edges"]);
            Assert.Equal(1, (int)j["counts"]["residential"]);
            Assert.Equal(1, (int)j["counts"]["service"]);

            var road = (JObject)j["edges"][0];
            Assert.Equal(0, (int)road["street"]);
            Assert.Equal("Small Road", (string)j["prefabs"][(int)road["prefab"]]);
            Assert.Equal(new[] { 1, 1 }, road["lanes"].Select(t => (int)t).ToArray());
            Assert.Equal(92, (int)road["flow"]);
            Assert.Equal(84.2, (double)road["length"]);
            Assert.Equal(new[] { 120.5, -400.3, 31.0 }, road["pts"][0].Select(t => (double)t).ToArray());
            Assert.Equal(new[] { 150.0, -385.3, 31.0 }, road["pts"][3].Select(t => (double)t).ToArray());
            foreach (var absent in new[] { "elevation", "tunnel", "bridge", "owned", "bus" }) Assert.Null(road[absent]);   // only when true or not zero

            var tunnel = (JObject)j["edges"][1];
            Assert.Null(tunnel["street"]);
            Assert.Null(tunnel["flow"]);
            Assert.True((bool)tunnel["tunnel"]);
            Assert.True((bool)tunnel["owned"]);
            Assert.Equal(new[] { -12.0, -8.0 }, tunnel["elevation"].Select(t => (double)t).ToArray());
            Assert.Equal(new[] { 2, 0 }, tunnel["lanes"].Select(t => (int)t).ToArray());
            Assert.Equal(new[] { 1, 0 }, tunnel["bus"].Select(t => (int)t).ToArray());

            Assert.True((bool)j["nodes"][0]["lights"]);
            Assert.Null(j["nodes"][1]["lights"]);
            Assert.Equal(90, (int)j["buildings"][0]["angle"]);
            Assert.Null(j["buildings"][0]["name"]);
            Assert.Equal("Healthcare", (string)j["buildings"][1]["service"]);
            Assert.True((bool)j["buildings"][1]["abandoned"]);
            Assert.Equal(new[] { 10, 8 }, j["buildings"][1]["lot"].Select(t => (int)t).ToArray());
            Assert.Equal("Mill Row", (string)j["districts"][0]["name"]);
            Assert.Equal(3, j["districts"][0]["outline"].Count());
            Assert.Equal(new[] { -937.0, -313.0, -937.0, -313.0 }, j["tiles"][0].Select(t => (double)t).ToArray());
            Assert.Empty(j["truncated"]);
        }

        [Fact]
        public void TerrainIsLittleEndianDecimetres()
        {
            var t = Parse(Sample().ToJson())["terrain"];
            Assert.Equal(2, (int)t["size"]);
            Assert.Equal(56.0, (double)t["cell"]);
            Assert.Equal(-7168.0, (double)t["origin"]);
            var bytes = Convert.FromBase64String((string)t["heights"]);
            Assert.Equal(new byte[] { 0, 0, 1, 0, 0, 1, 255, 255 }, bytes);
            Assert.Equal(new byte[] { 0, 0, 0, 0, 12, 0, 0, 0 }, Convert.FromBase64String((string)t["water"]));

            Assert.Equal(0, CitySnapshot.Decimetres(-3f));
            Assert.Equal(0, CitySnapshot.Decimetres(float.NaN));
            Assert.Equal(1234, CitySnapshot.Decimetres(123.44f));
            Assert.Equal(ushort.MaxValue, CitySnapshot.Decimetres(9000f));
        }

        [Fact]
        public void NumbersDontFollowTheMachinesLanguage()
        {
            var before = Thread.CurrentThread.CurrentCulture;
            try
            {
                Thread.CurrentThread.CurrentCulture = new CultureInfo("de-DE");   // decimal comma
                var json = Sample().ToJson();
                Assert.Contains("\"length\":84.2", json);
                Assert.DoesNotContain("84,2", json);
                Parse(json);
            }
            finally
            {
                Thread.CurrentThread.CurrentCulture = before;
            }
        }

        [Fact]
        public void BrokenNumbersBecomeZero()
        {
            var s = new CitySnapshot();
            s.AddNode(new CitySnapshot.Node { Id = 1, X = float.NaN, Z = float.PositiveInfinity, Y = float.NegativeInfinity });
            s.AddEdge(new CitySnapshot.Edge { Id = 2, Kind = "road", Length = float.NaN, Pts = Enumerable.Repeat(float.NaN, 12).ToArray() });
            s.AddBuilding(new CitySnapshot.Building { Kind = "other", Angle = float.NaN });
            var j = Parse(s.ToJson());   // valid JSON: NaN and Infinity aren't JSON numbers
            Assert.Equal(0.0, (double)j["nodes"][0]["x"]);
            Assert.Equal(0.0, (double)j["edges"][0]["pts"][2][1]);
            Assert.Equal(0, (int)j["buildings"][0]["angle"]);
            Assert.Null(j["terrain"]);   // no terrain read: no terrain section
        }

        [Fact]
        public void ListsStopAtTheirLimitAndSaySo()
        {
            var s = new CitySnapshot();
            for (var i = 0; i < CitySnapshot.MaxBuildings + 5; i++) s.AddBuilding(new CitySnapshot.Building { Kind = "residential" });
            Assert.Equal(CitySnapshot.MaxBuildings, s.Buildings.Count);
            Assert.False(s.AddBuilding(new CitySnapshot.Building()));
            var j = Parse(s.ToJson());
            Assert.Equal(new[] { "buildings" }, j["truncated"].Select(t => (string)t).ToArray());
            Assert.Equal(CitySnapshot.MaxBuildings, (int)j["counts"]["buildings"]);
        }

        [Fact]
        public void ATooLargeFileDropsBuildingsThenEdges()
        {
            var s = Sample();
            for (var i = 0; i < 2000; i++) s.AddBuilding(new CitySnapshot.Building { Kind = "residential", Prefab = 2, X = i });
            s.MaxBytes = Sample().ToJson().Length + 2000;   // room for the sample, not for 2,000 more buildings
            var j = Parse(s.ToJson());
            Assert.Empty(j["buildings"]);
            Assert.Equal(2, j["edges"].Count());
            Assert.Equal(new[] { "buildings (file too large)" }, j["truncated"].Select(t => (string)t).ToArray());
            Assert.Equal(2002, (int)j["counts"]["buildings"]);   // the counts stay

            var tiny = Sample();
            tiny.MaxBytes = 100;
            var k = Parse(tiny.ToJson());
            Assert.Empty(k["edges"]);
            Assert.Empty(k["nodes"]);
            Assert.Equal(12345, (int)k["city"]["population"]);   // the numbers and budget are always there
            Assert.Equal(2, k["truncated"].Count());
        }

        private static CitySnapshot Session(string session, int population, int money, params (int id, string kind, float length, bool owned)[] edges)
        {
            var s = new CitySnapshot { Session = session, Taken = "2026-11-24T20:00:00Z", DateText = "March 2026, 08:00", Population = population, Money = money };
            foreach (var e in edges) s.AddEdge(new CitySnapshot.Edge { Id = e.id, Kind = e.kind, Length = e.length, Owned = e.owned });
            return s;
        }

        [Fact]
        public void ChangesSinceTheStartOfTheSession()
        {
            var start = Session("S1", 1000, 50000, (1, "road", 400f, false), (2, "highway", 600f, false), (3, "train", 1000f, false), (4, "road", 50f, true));
            start.AddBuilding(new CitySnapshot.Building { Id = 10, Kind = "residential" });
            start.AddBuilding(new CitySnapshot.Building { Id = 11, Kind = "service" });
            start.OwnedTiles = 9;
            var now = Session("S1", 1312, 8000, (1, "road", 400f, false), (5, "road", 2300f, false), (6, "tram", 500f, false), (7, "road", 80f, true), (8, "path", 90f, false));
            now.AddBuilding(new CitySnapshot.Building { Id = 10, Kind = "residential" });
            for (var i = 0; i < 41; i++) now.AddBuilding(new CitySnapshot.Building { Id = 100 + i, Kind = i % 2 == 0 ? "residential" : "office" });
            now.AddBuilding(new CitySnapshot.Building { Id = 200, Kind = "signature" });
            now.AddBuilding(new CitySnapshot.Building { Id = 201, Kind = "service" });
            now.OwnedTiles = 10;

            var c = CitySnapshot.Compare(start, now);
            Assert.Equal(2.3, c.RoadsAddedKm, 3);       // edge 5; owned roads (a building's) and paths don't count
            Assert.Equal(0.6, c.RoadsRemovedKm, 3);     // the highway piece 2
            Assert.Equal(0.5, c.RailAddedKm, 3);
            Assert.Equal(1.0, c.RailRemovedKm, 3);
            Assert.Equal(41, c.Grew);
            Assert.Equal(2, c.Placed);
            Assert.Equal(1, c.Removed);                 // building 11
            Assert.Equal(312, c.Population);
            Assert.Equal(-42000, c.Money);
            Assert.Equal(1, c.Tiles);

            now.SessionChanges = c;
            var j = Parse(now.ToJson());
            Assert.Equal("S1", (string)j["session"]["start"]);
            Assert.Equal(2.3, (double)j["session"]["changes"]["roadsAddedKm"]);
            Assert.Equal(-42000, (int)j["session"]["changes"]["money"]);
            Assert.Equal(100, (int)j["buildings"][1]["id"]);

            Assert.Null(CitySnapshot.Compare(start, Session("S2", 1, 1)));   // another session: entity numbers don't match
            Assert.Null(CitySnapshot.Compare(Session("", 1, 1), Session("", 1, 1)));
        }

        [Fact]
        public void CutListsAreNotCompared()
        {
            var start = Session("S1", 1, 1, (1, "road", 400f, false));
            var now = Session("S1", 2, 2);
            now.Truncated.Add("edges");
            var c = CitySnapshot.Compare(start, now);
            Assert.False(c.RoadsKnown);
            Assert.Equal(0, c.RoadsRemovedKm);
            now.SessionChanges = c;
            Assert.Null(Parse(now.ToJson())["session"]["changes"]["roadsAddedKm"]);
        }

        [Fact]
        public void WritesTheCityWideSectionsAndTheNewFields()
        {
            var s = Sample();
            s.PrefabTitles[0] = "Two-Lane Road";
            s.Edges[0].SpeedKmh = 40;
            s.Edges[0].Volume = 120;
            s.Edges[0].Upgrades = new System.Collections.Generic.List<string> { "trees", "lighting" };
            s.Edges[0].ZoneCells = 24;
            s.Edges[0].ZoneBuilt = 18;
            var school = s.Buildings[1];
            school.District = 0;
            school.Efficiency = 87;
            school.UseWhat = "patients";
            school.UseNow = 120;
            school.UseMax = 300;
            var house = s.Buildings[0];
            house.Households = 3;
            house.HomesMax = 4;
            s.Districts[0].Policies = new JArray(new JObject { ["policy"] = "HeavyTrafficBan", ["title"] = "Heavy Traffic Ban" });
            s.Section("demand", new JObject { ["residentialLow"] = 40, ["factors"] = new JObject { ["residentialLow"] = new JObject { ["Taxes"] = -12 } } });
            s.Section("utilities", new JObject { ["electricity"] = new JObject { ["production"] = 5000, ["ratio"] = double.NaN, ["odd"] = double.PositiveInfinity } });
            s.Section("happiness", new JObject { ["factors"] = new JArray(new JObject { ["factor"] = "Telecom", ["points"] = -3, ["exact"] = 1.23456 }) });
            s.Section("ignored", null);

            var j = Parse(s.ToJson());
            Assert.Equal(new[] { "Two-Lane Road", "", "", "" }, j["prefabTitles"].Select(t => (string)t).ToArray());   // one per prefab, "" where the game had none
            var road = j["edges"][0];
            Assert.Equal(40, (int)road["speed"]);
            Assert.Equal(120, (int)road["volume"]);
            Assert.Equal(new[] { "trees", "lighting" }, road["upgrades"].Select(t => (string)t).ToArray());
            Assert.Equal(new[] { 24, 18 }, road["zoned"].Select(t => (int)t).ToArray());
            foreach (var absent in new[] { "speed", "volume", "upgrades", "zoned" }) Assert.Null(j["edges"][1][absent]);
            Assert.Equal(87, (int)j["buildings"][1]["efficiency"]);
            Assert.Equal(0, (int)j["buildings"][1]["district"]);
            Assert.Equal("patients", (string)j["buildings"][1]["use"]["what"]);
            Assert.Equal(300, (int)j["buildings"][1]["use"]["max"]);
            Assert.Equal(new[] { 3, 4 }, j["buildings"][0]["homes"].Select(t => (int)t).ToArray());
            Assert.Null(j["buildings"][0]["jobs"]);
            Assert.Null(j["buildings"][0]["district"]);
            Assert.Equal("Heavy Traffic Ban", (string)j["districts"][0]["policies"][0]["title"]);
            Assert.Equal(-12, (int)j["demand"]["factors"]["residentialLow"]["Taxes"]);
            Assert.Equal(0, (double)j["utilities"]["electricity"]["ratio"]);   // NaN and infinity become 0: still valid JSON
            Assert.Equal(0, (double)j["utilities"]["electricity"]["odd"]);
            Assert.Equal(1.235, (double)j["happiness"]["factors"][0]["exact"]);
            Assert.Null(j["ignored"]);
            var keys = j.Properties().Select(p => p.Name).ToList();
            Assert.True(keys.IndexOf("budget") < keys.IndexOf("demand") && keys.IndexOf("demand") < keys.IndexOf("counts"));   // after the budget
        }

        [Fact]
        public void TablesHoldEachNameOnce()
        {
            var t = new CitySnapshot.Table();
            Assert.Equal(0, t.Of("Main Street"));
            Assert.Equal(1, t.Of("main street"));   // names are kept exactly as the game shows them
            Assert.Equal(0, t.Of("Main Street"));
            Assert.Equal(2, t.Of(null));
            Assert.Equal(new[] { "Main Street", "main street", "" }, t.Names);
        }
    }
}
