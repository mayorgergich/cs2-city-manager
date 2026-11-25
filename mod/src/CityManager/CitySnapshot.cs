// The city snapshot (city.json; its format is in format/README.md): plain data that CityReader fills in from the game,
// written out as JSON here. Nothing in this file touches the game, so the offline tests can check the format, the
// rounding, the limits and the terrain encoding.

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace CityManager
{
    public sealed class CitySnapshot
    {
        public const int Format = 1;
        public const int MaxEdges = 100000, MaxBuildings = 100000, MaxNodes = 200000, MaxDistricts = 2000, MaxOutline = 2000;
        public long MaxBytes = DefaultMaxBytes;
        public const long DefaultMaxBytes = 32L * 1024 * 1024;
        public const string FileName = "city.json", StartFileName = "city-start.json";

        public string Mod = "", Taken = "", Why = "", Save = "";
        public string Session = "";      // when the city was loaded: a session's city-start.json and city.json share it
        public Changes SessionChanges;   // what changed since the session's start snapshot, when there is one

        public string Name = "";
        public int Population, Happiness, Money, Xp, Milestone, OwnedTiles;
        public bool UnlimitedMoney;
        public int Year, Month, Hour, Minute;
        public string DateText = "";

        public readonly List<KeyValuePair<string, int>> Income = new List<KeyValuePair<string, int>>();
        public readonly List<KeyValuePair<string, int>> Expenses = new List<KeyValuePair<string, int>>();
        public int TotalIncome, TotalExpenses, Balance;

        public readonly Table Prefabs = new Table(), Streets = new Table();
        public readonly Dictionary<int, string> PrefabTitles = new Dictionary<int, string>();   // the name in the game's menus, by prefab index
        public readonly List<Node> Nodes = new List<Node>();
        public readonly List<Edge> Edges = new List<Edge>();
        public readonly List<Building> Buildings = new List<Building>();
        public readonly List<District> Districts = new List<District>();
        public readonly List<float[]> Tiles = new List<float[]>();   // owned tiles: minX, maxX, minZ, maxZ

        public int TerrainSize;
        public float TerrainCell, TerrainOrigin;
        public ushort[] Heights, Water;   // decimetres, row by row (row = z, column = x)

        public readonly List<string> Truncated = new List<string>();

        /// <summary>The city-wide parts (people, jobs, demand, services, problems, transit…), in the order they are
        /// written, after the budget. Numbers that aren't finite are written as 0.</summary>
        public readonly List<KeyValuePair<string, JToken>> Sections = new List<KeyValuePair<string, JToken>>();

        public void Section(string name, JToken value)
        {
            if (value != null) Sections.Add(new KeyValuePair<string, JToken>(name, value));
        }

        /// <summary>Each name once; the lists refer to it by position.</summary>
        public sealed class Table
        {
            private readonly Dictionary<string, int> _index = new Dictionary<string, int>(StringComparer.Ordinal);
            public readonly List<string> Names = new List<string>();

            public int Of(string name)
            {
                name = name ?? "";
                if (_index.TryGetValue(name, out var i)) return i;
                i = Names.Count;
                Names.Add(name);
                _index[name] = i;
                return i;
            }
        }

        public struct Node
        {
            public int Id;
            public float X, Z, Y;
            public bool Lights, Roundabout, Outside;
        }

        public sealed class Edge
        {
            public int Id, Prefab, A, B, Street = -1, Flow = -1;
            public string Kind = "";
            public float Length;
            public float[] Pts = new float[12];   // four control points, x z y each
            public int LanesForward, LanesBackward, BusForward, BusBackward;
            public float ElevationA, ElevationB;
            public bool Tunnel, Bridge, Owned, HasLanes;
            public int SpeedKmh = -1, Volume = -1, ZoneCells = -1, ZoneBuilt;
            public List<string> Upgrades;
        }

        public sealed class Building
        {
            public int Id, Prefab, Level, LotWidth, LotDepth;
            public string Kind = "", Service, Name;
            public float X, Z, Y, Angle;
            public bool Abandoned, Condemned;
            public int District = -1, Efficiency = -1;
            public string UseWhat;                // what fills a service building: "pupils", "patients", "garbage"…
            public int UseNow, UseMax;
            public int Households = -1, HomesMax, Workers = -1, WorkersMax;
        }

        public sealed class District
        {
            public string Name = "";
            public readonly List<float[]> Outline = new List<float[]>();   // x, z
            public JToken Policies;
        }

        /// <summary>What changed between a session's start snapshot and a later one of the same session (the entity
        /// numbers only match within one session).</summary>
        public sealed class Changes
        {
            public string Since = "", SinceDate = "";
            public double RoadsAddedKm, RoadsRemovedKm, RailAddedKm, RailRemovedKm;
            public int Grew, Placed, Removed, Population, Money, Tiles;
            public bool RoadsKnown = true, BuildingsKnown = true;
        }

        public static bool IsZoned(string kind) => kind == "residential" || kind == "commercial" || kind == "industrial" || kind == "office";

        private static string Group(Edge e) =>
            e.Owned ? null : e.Kind == "road" || e.Kind == "highway" ? "road" : e.Kind == "train" || e.Kind == "tram" || e.Kind == "subway" ? "rail" : null;

        /// <summary>The changes from start to now, or null when they aren't from the same session.</summary>
        public static Changes Compare(CitySnapshot start, CitySnapshot now)
        {
            if (start == null || now == null || string.IsNullOrEmpty(start.Session) || start.Session != now.Session) return null;
            var c = new Changes
            {
                Since = start.Taken, SinceDate = start.DateText,
                Population = now.Population - start.Population,
                Money = now.Money - start.Money,
                Tiles = now.OwnedTiles - start.OwnedTiles,
                RoadsKnown = !start.Truncated.Exists(t => t.StartsWith("edges")) && !now.Truncated.Exists(t => t.StartsWith("edges")),
                BuildingsKnown = !start.Truncated.Exists(t => t.StartsWith("buildings")) && !now.Truncated.Exists(t => t.StartsWith("buildings")),
            };
            if (c.RoadsKnown)
            {
                var before = new Dictionary<int, Edge>();
                foreach (var e in start.Edges) before[e.Id] = e;
                var after = new HashSet<int>();
                foreach (var e in now.Edges)
                {
                    after.Add(e.Id);
                    if (before.ContainsKey(e.Id)) continue;
                    var g = Group(e);
                    if (g == "road") c.RoadsAddedKm += e.Length / 1000.0;
                    else if (g == "rail") c.RailAddedKm += e.Length / 1000.0;
                }
                foreach (var e in start.Edges)
                {
                    if (after.Contains(e.Id)) continue;
                    var g = Group(e);
                    if (g == "road") c.RoadsRemovedKm += e.Length / 1000.0;
                    else if (g == "rail") c.RailRemovedKm += e.Length / 1000.0;
                }
            }
            if (c.BuildingsKnown)
            {
                var before = new HashSet<int>();
                foreach (var b in start.Buildings) before.Add(b.Id);
                var after = new HashSet<int>();
                foreach (var b in now.Buildings)
                {
                    after.Add(b.Id);
                    if (before.Contains(b.Id)) continue;
                    if (IsZoned(b.Kind)) c.Grew++; else c.Placed++;
                }
                foreach (var id in before) if (!after.Contains(id)) c.Removed++;
            }
            return c;
        }

        public bool AddEdge(Edge e) => Add(Edges, e, MaxEdges, "edges");
        public bool AddBuilding(Building b) => Add(Buildings, b, MaxBuildings, "buildings");
        public bool AddNode(Node n) => Add(Nodes, n, MaxNodes, "nodes");
        public bool AddDistrict(District d) => Add(Districts, d, MaxDistricts, "districts");

        private bool Add<T>(List<T> list, T item, int max, string what)
        {
            if (list.Count >= max)
            {
                if (!Truncated.Contains(what)) Truncated.Add(what);
                return false;
            }
            list.Add(item);
            return true;
        }

        /// <summary>The snapshot as JSON. If it would pass MaxBytes, the buildings and then the edges are left out (and
        /// named in "truncated"), so a huge city still gets its numbers and budget.</summary>
        public string ToJson()
        {
            var text = Write(true, true);
            if (Encoding.UTF8.GetByteCount(text) <= MaxBytes) return text;
            Truncated.Add("buildings (file too large)");
            text = Write(false, true);
            if (Encoding.UTF8.GetByteCount(text) <= MaxBytes) return text;
            Truncated.Add("edges (file too large)");
            return Write(false, false);
        }

        private string Write(bool buildings, bool edges)
        {
            var sb = new StringBuilder(1 << 20);
            using (var sw = new StringWriter(sb, CultureInfo.InvariantCulture))
            using (var w = new JsonTextWriter(sw) { Formatting = Formatting.None, Culture = CultureInfo.InvariantCulture })
            {
                w.WriteStartObject();
                Prop(w, "format", Format);
                Prop(w, "mod", Mod);
                Prop(w, "taken", Taken);
                Prop(w, "why", Why);
                if (!string.IsNullOrEmpty(Save)) Prop(w, "save", Save);
                if (!string.IsNullOrEmpty(Session) || SessionChanges != null)
                {
                    w.WritePropertyName("session");
                    w.WriteStartObject();
                    Prop(w, "start", Session);
                    if (SessionChanges != null)
                    {
                        var c = SessionChanges;
                        w.WritePropertyName("changes");
                        w.WriteStartObject();
                        Prop(w, "since", c.Since);
                        Prop(w, "sinceDate", c.SinceDate);
                        if (c.RoadsKnown)
                        {
                            Km(w, "roadsAddedKm", c.RoadsAddedKm);
                            Km(w, "roadsRemovedKm", c.RoadsRemovedKm);
                            Km(w, "railAddedKm", c.RailAddedKm);
                            Km(w, "railRemovedKm", c.RailRemovedKm);
                        }
                        if (c.BuildingsKnown)
                        {
                            Prop(w, "grew", c.Grew);
                            Prop(w, "placed", c.Placed);
                            Prop(w, "removed", c.Removed);
                        }
                        Prop(w, "population", c.Population);
                        Prop(w, "money", c.Money);
                        Prop(w, "tiles", c.Tiles);
                        w.WriteEndObject();
                    }
                    w.WriteEndObject();
                }

                w.WritePropertyName("city");
                w.WriteStartObject();
                Prop(w, "name", Name);
                Prop(w, "population", Population);
                Prop(w, "happiness", Happiness);
                Prop(w, "money", Money);
                Prop(w, "unlimitedMoney", UnlimitedMoney);
                Prop(w, "xp", Xp);
                Prop(w, "milestone", Milestone);
                Prop(w, "tiles", OwnedTiles);
                w.WritePropertyName("date");
                w.WriteStartObject();
                Prop(w, "year", Year);
                Prop(w, "month", Month);
                Prop(w, "hour", Hour);
                Prop(w, "minute", Minute);
                Prop(w, "text", DateText);
                w.WriteEndObject();
                w.WriteEndObject();

                w.WritePropertyName("budget");
                w.WriteStartObject();
                Lines(w, "income", Income);
                Lines(w, "expenses", Expenses);
                Prop(w, "totalIncome", TotalIncome);
                Prop(w, "totalExpenses", TotalExpenses);
                Prop(w, "balance", Balance);
                w.WriteEndObject();

                foreach (var section in Sections)
                {
                    w.WritePropertyName(section.Key);
                    Finite(section.Value).WriteTo(w);
                }

                w.WritePropertyName("counts");
                w.WriteStartObject();
                Prop(w, "edges", Edges.Count);
                Prop(w, "nodes", Nodes.Count);
                Prop(w, "buildings", Buildings.Count);
                var kinds = new SortedDictionary<string, int>(StringComparer.Ordinal);
                foreach (var b in Buildings) kinds[b.Kind] = kinds.TryGetValue(b.Kind, out var n) ? n + 1 : 1;
                foreach (var k in kinds) Prop(w, k.Key, k.Value);
                Prop(w, "districts", Districts.Count);
                w.WriteEndObject();

                Strings(w, "prefabs", Prefabs.Names);
                var titles = new List<string>(Prefabs.Names.Count);
                for (var i = 0; i < Prefabs.Names.Count; i++) titles.Add(PrefabTitles.TryGetValue(i, out var t) ? t : "");
                Strings(w, "prefabTitles", titles);
                Strings(w, "streets", Streets.Names);

                w.WritePropertyName("nodes");
                w.WriteStartArray();
                if (edges)
                {
                    foreach (var n in Nodes)
                    {
                        w.WriteStartObject();
                        Prop(w, "id", n.Id);
                        Num(w, "x", n.X);
                        Num(w, "z", n.Z);
                        Num(w, "y", n.Y);
                        if (n.Lights) Prop(w, "lights", true);
                        if (n.Roundabout) Prop(w, "roundabout", true);
                        if (n.Outside) Prop(w, "outside", true);
                        w.WriteEndObject();
                    }
                }
                w.WriteEndArray();

                w.WritePropertyName("edges");
                w.WriteStartArray();
                if (edges)
                {
                    foreach (var e in Edges)
                    {
                        w.WriteStartObject();
                        Prop(w, "id", e.Id);
                        Prop(w, "prefab", e.Prefab);
                        Prop(w, "kind", e.Kind);
                        Prop(w, "a", e.A);
                        Prop(w, "b", e.B);
                        if (e.Street >= 0) Prop(w, "street", e.Street);
                        Num(w, "length", e.Length);
                        w.WritePropertyName("pts");
                        w.WriteStartArray();
                        for (var i = 0; i < 4; i++)
                        {
                            w.WriteStartArray();
                            for (var k = 0; k < 3; k++) w.WriteValue(R1(e.Pts[3 * i + k]));
                            w.WriteEndArray();
                        }
                        w.WriteEndArray();
                        if (e.HasLanes)
                        {
                            Pair(w, "lanes", e.LanesForward, e.LanesBackward);
                            if (e.BusForward + e.BusBackward > 0) Pair(w, "bus", e.BusForward, e.BusBackward);
                        }
                        if (R1(e.ElevationA) != 0 || R1(e.ElevationB) != 0)
                        {
                            w.WritePropertyName("elevation");
                            w.WriteStartArray();
                            w.WriteValue(R1(e.ElevationA));
                            w.WriteValue(R1(e.ElevationB));
                            w.WriteEndArray();
                        }
                        if (e.Tunnel) Prop(w, "tunnel", true);
                        if (e.Bridge) Prop(w, "bridge", true);
                        if (e.Flow >= 0) Prop(w, "flow", e.Flow);
                        if (e.Volume >= 0) Prop(w, "volume", e.Volume);
                        if (e.SpeedKmh > 0) Prop(w, "speed", e.SpeedKmh);
                        if (e.Upgrades != null && e.Upgrades.Count > 0) Strings(w, "upgrades", e.Upgrades);
                        if (e.ZoneCells > 0) Pair(w, "zoned", e.ZoneCells, e.ZoneBuilt);
                        if (e.Owned) Prop(w, "owned", true);
                        w.WriteEndObject();
                    }
                }
                w.WriteEndArray();

                w.WritePropertyName("buildings");
                w.WriteStartArray();
                if (buildings)
                {
                    foreach (var b in Buildings)
                    {
                        w.WriteStartObject();
                        Prop(w, "id", b.Id);
                        Prop(w, "prefab", b.Prefab);
                        Prop(w, "kind", b.Kind);
                        if (b.Level > 0) Prop(w, "level", b.Level);
                        if (!string.IsNullOrEmpty(b.Service)) Prop(w, "service", b.Service);
                        if (!string.IsNullOrEmpty(b.Name)) Prop(w, "name", b.Name);
                        Pair(w, "lot", b.LotWidth, b.LotDepth);
                        Num(w, "x", b.X);
                        Num(w, "z", b.Z);
                        Num(w, "y", b.Y);
                        Prop(w, "angle", (int)Math.Round(Finite(b.Angle)));
                        if (b.Abandoned) Prop(w, "abandoned", true);
                        if (b.Condemned) Prop(w, "condemned", true);
                        if (b.District >= 0) Prop(w, "district", b.District);
                        if (b.Efficiency >= 0) Prop(w, "efficiency", b.Efficiency);
                        if (!string.IsNullOrEmpty(b.UseWhat))
                        {
                            w.WritePropertyName("use");
                            w.WriteStartObject();
                            Prop(w, "what", b.UseWhat);
                            Prop(w, "now", b.UseNow);
                            Prop(w, "max", b.UseMax);
                            w.WriteEndObject();
                        }
                        if (b.Households >= 0) Pair(w, "homes", b.Households, b.HomesMax);
                        if (b.Workers >= 0) Pair(w, "jobs", b.Workers, b.WorkersMax);
                        w.WriteEndObject();
                    }
                }
                w.WriteEndArray();

                w.WritePropertyName("districts");
                w.WriteStartArray();
                foreach (var d in Districts)
                {
                    w.WriteStartObject();
                    Prop(w, "name", d.Name);
                    if (d.Policies != null)
                    {
                        w.WritePropertyName("policies");
                        Finite(d.Policies).WriteTo(w);
                    }
                    w.WritePropertyName("outline");
                    w.WriteStartArray();
                    foreach (var p in d.Outline)
                    {
                        w.WriteStartArray();
                        w.WriteValue(R1(p[0]));
                        w.WriteValue(R1(p[1]));
                        w.WriteEndArray();
                    }
                    w.WriteEndArray();
                    w.WriteEndObject();
                }
                w.WriteEndArray();

                w.WritePropertyName("tiles");
                w.WriteStartArray();
                foreach (var t in Tiles)
                {
                    w.WriteStartArray();
                    foreach (var v in t) w.WriteValue(R1(v));
                    w.WriteEndArray();
                }
                w.WriteEndArray();

                if (TerrainSize > 0 && Heights != null && Water != null)
                {
                    w.WritePropertyName("terrain");
                    w.WriteStartObject();
                    Prop(w, "size", TerrainSize);
                    Num(w, "cell", TerrainCell);
                    Num(w, "origin", TerrainOrigin);
                    Prop(w, "heights", Base64(Heights));
                    Prop(w, "water", Base64(Water));
                    w.WriteEndObject();
                }

                Strings(w, "truncated", Truncated);
                w.WriteEndObject();
            }
            return sb.ToString();
        }

        /// <summary>Metres to decimetres, clamped to what 16 bits hold (0 to 6,553.5 m).</summary>
        public static ushort Decimetres(float metres)
        {
            if (float.IsNaN(metres) || metres <= 0f) return 0;
            var d = Math.Round(metres * 10.0);
            return d >= ushort.MaxValue ? ushort.MaxValue : (ushort)d;
        }

        /// <summary>Little-endian 16-bit numbers as base64, whatever the machine's byte order.</summary>
        public static string Base64(ushort[] values)
        {
            var bytes = new byte[values.Length * 2];
            for (var i = 0; i < values.Length; i++)
            {
                bytes[2 * i] = (byte)(values[i] & 0xFF);
                bytes[2 * i + 1] = (byte)(values[i] >> 8);
            }
            return Convert.ToBase64String(bytes);
        }

        private static double Finite(float v) => float.IsNaN(v) || float.IsInfinity(v) ? 0.0 : v;

        /// <summary>A copy of a section with every NaN or infinite number replaced by 0 (they aren't valid JSON).</summary>
        public static JToken Finite(JToken t)
        {
            switch (t)
            {
                case JValue v when v.Type == JTokenType.Float:
                    var d = Convert.ToDouble(v.Value, CultureInfo.InvariantCulture);
                    return double.IsNaN(d) || double.IsInfinity(d) ? new JValue(0) : new JValue(Math.Round(d, 3));
                case JArray a:
                    var na = new JArray();
                    foreach (var x in a) na.Add(Finite(x));
                    return na;
                case JObject o:
                    var no = new JObject();
                    foreach (var p in o.Properties()) no[p.Name] = Finite(p.Value);
                    return no;
                default:
                    return t ?? JValue.CreateNull();
            }
        }
        public static double R1(float v) => Math.Round(Finite(v), 1);

        private static void Prop(JsonWriter w, string name, string value) { w.WritePropertyName(name); w.WriteValue(value ?? ""); }
        private static void Prop(JsonWriter w, string name, int value) { w.WritePropertyName(name); w.WriteValue(value); }
        private static void Prop(JsonWriter w, string name, bool value) { w.WritePropertyName(name); w.WriteValue(value); }
        private static void Num(JsonWriter w, string name, float value) { w.WritePropertyName(name); w.WriteValue(R1(value)); }
        private static void Km(JsonWriter w, string name, double km) { w.WritePropertyName(name); w.WriteValue(Math.Round(km, 2)); }

        private static void Pair(JsonWriter w, string name, int a, int b)
        {
            w.WritePropertyName(name);
            w.WriteStartArray();
            w.WriteValue(a);
            w.WriteValue(b);
            w.WriteEndArray();
        }

        private static void Strings(JsonWriter w, string name, List<string> values)
        {
            w.WritePropertyName(name);
            w.WriteStartArray();
            foreach (var v in values) w.WriteValue(v ?? "");
            w.WriteEndArray();
        }

        private static void Lines(JsonWriter w, string name, List<KeyValuePair<string, int>> lines)
        {
            w.WritePropertyName(name);
            w.WriteStartObject();
            foreach (var l in lines) Prop(w, l.Key, l.Value);
            w.WriteEndObject();
        }
    }
}
