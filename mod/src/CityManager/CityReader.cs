// Reads the loaded city into a CitySnapshot, one part per frame (the city's numbers, the networks, the buildings, the
// terrain), so taking a snapshot never stalls a frame for long. Runs on the main thread from JournalSystem.OnUpdate.
// It only reads: components, the game's own names (NameSystem, what the Mayor sees on the map) and the budget; nothing
// in the city changes. The JSON is written afterwards, off the main thread (CitySnapshot.ToJson).
//
// Which components to read was worked out from the game's code and from the LancerComet CS2 MCP bridge
// (github.com/LancerComet/cities-skylines-2-mcp, Apache-2.0), whose road-graph and terrain handlers read the same
// data; this is our own code.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using Game.Prefabs;
using Unity.Collections;
using Unity.Entities;
using Unity.Jobs;
using Unity.Mathematics;
using AreaNode = Game.Areas.Node;
using Building = Game.Buildings.Building;
using CityServiceBudgetSystem = Game.Simulation.CityServiceBudgetSystem;
using CitySystem = Game.Simulation.CitySystem;
using Composition = Game.Net.Composition;
using Curve = Game.Net.Curve;
using Deleted = Game.Common.Deleted;
using District = Game.Areas.District;
using Edge = Game.Net.Edge;
using Elevation = Game.Net.Elevation;
using ExpenseSource = Game.City.ExpenseSource;
using IncomeSource = Game.City.IncomeSource;
using MapTile = Game.Areas.MapTile;
using NameSystem = Game.UI.NameSystem;
using Native = Game.Common.Native;
using NetNode = Game.Net.Node;
using Owner = Game.Common.Owner;
using Temp = Game.Tools.Temp;
using TerrainSystem = Game.Simulation.TerrainSystem;
using TerrainUtils = Game.Simulation.TerrainUtils;
using Transform = Game.Objects.Transform;
using WaterSystem = Game.Simulation.WaterSystem;
using WaterUtils = Game.Simulation.WaterUtils;

namespace CityManager
{
    internal sealed partial class CityReader
    {
        public const int TerrainSize = 256;
        public const float MapHalfSize = 7168f;   // the playable map is 14,336 m across, centred on 0

        /// <summary>The queries a snapshot reads, made once by the system that owns them.</summary>
        public sealed class Queries
        {
            public EntityQuery Edges, Buildings, Districts, Tiles, Icons, Services, HappinessParams, FeeParams,
                Lines, ZonePrefabs, Blocks, Placeable, Stamps, AllTiles;

            public static Queries Make(Func<EntityQueryDesc, EntityQuery> make)
            {
                var none = new[] { ComponentType.ReadOnly<Deleted>(), ComponentType.ReadOnly<Temp>() };
                return new Queries
                {
                    Edges = make(new EntityQueryDesc
                    {
                        All = new[] { ComponentType.ReadOnly<Edge>(), ComponentType.ReadOnly<Curve>(), ComponentType.ReadOnly<PrefabRef>() },
                        None = none,
                    }),
                    Buildings = make(new EntityQueryDesc
                    {
                        All = new[] { ComponentType.ReadOnly<Building>(), ComponentType.ReadOnly<PrefabRef>(), ComponentType.ReadOnly<Transform>() },
                        None = new[] { ComponentType.ReadOnly<Deleted>(), ComponentType.ReadOnly<Temp>(), ComponentType.ReadOnly<Owner>() },
                    }),
                    Districts = make(new EntityQueryDesc
                    {
                        All = new[] { ComponentType.ReadOnly<District>(), ComponentType.ReadOnly<AreaNode>() },
                        None = none,
                    }),
                    Tiles = make(new EntityQueryDesc
                    {
                        All = new[] { ComponentType.ReadOnly<MapTile>(), ComponentType.ReadOnly<AreaNode>() },
                        None = new[] { ComponentType.ReadOnly<Native>(), ComponentType.ReadOnly<Deleted>(), ComponentType.ReadOnly<Temp>() },
                    }),
                    Icons = make(new EntityQueryDesc
                    {
                        All = new[] { ComponentType.ReadOnly<Game.Notifications.Icon>(), ComponentType.ReadOnly<PrefabRef>() },
                        None = new[] { ComponentType.ReadOnly<Deleted>(), ComponentType.ReadOnly<Temp>(), ComponentType.ReadOnly<Game.Tools.Hidden>() },
                    }),
                    Services = make(new EntityQueryDesc
                    {
                        All = new[] { ComponentType.ReadOnly<PrefabData>(), ComponentType.ReadOnly<ServiceData>(), ComponentType.ReadOnly<UIObjectData>() },
                    }),
                    HappinessParams = make(new EntityQueryDesc { All = new[] { ComponentType.ReadOnly<HappinessFactorParameterData>() } }),
                    FeeParams = make(new EntityQueryDesc { All = new[] { ComponentType.ReadOnly<ServiceFeeParameterData>() } }),
                    Lines = make(new EntityQueryDesc
                    {
                        All = new[] { ComponentType.ReadOnly<Game.Routes.Route>(), ComponentType.ReadOnly<Game.Routes.TransportLine>(),
                            ComponentType.ReadOnly<Game.Routes.RouteWaypoint>(), ComponentType.ReadOnly<PrefabRef>() },
                        None = none,
                    }),
                    ZonePrefabs = make(new EntityQueryDesc { All = new[] { ComponentType.ReadOnly<PrefabData>(), ComponentType.ReadOnly<ZoneData>() } }),
                    Blocks = make(new EntityQueryDesc
                    {
                        All = new[] { ComponentType.ReadOnly<Game.Zones.Block>(), ComponentType.ReadOnly<Game.Zones.Cell>() },
                        None = none,
                    }),
                    Placeable = make(new EntityQueryDesc
                    {
                        All = new[] { ComponentType.ReadOnly<PrefabData>(), ComponentType.ReadOnly<PlaceableNetData>(), ComponentType.ReadOnly<UIObjectData>() },
                    }),
                    Stamps = make(new EntityQueryDesc
                    {
                        All = new[] { ComponentType.ReadOnly<PrefabData>(), ComponentType.ReadOnly<AssetStampData>(), ComponentType.ReadOnly<UIObjectData>() },
                    }),
                    AllTiles = make(new EntityQueryDesc
                    {
                        All = new[] { ComponentType.ReadOnly<MapTile>(), ComponentType.ReadOnly<Game.Areas.Geometry>() },
                        None = none,
                    }),
                };
            }
        }

        private sealed class NetPrefab
        {
            public int Index;
            public string Kind;   // null: not a network the snapshot keeps (pipes, power lines, fences)
        }

        private sealed class BuildingPrefab
        {
            public int Index, Level, LotWidth, LotDepth;
            public string Kind, Service;
        }

        private sealed class Lanes
        {
            public int Forward, Backward, BusForward, BusBackward, SpeedKmh = -1;
            public bool Tunnel, Bridge, Any;
        }

        private readonly EntityManager _em;
        private readonly Queries _q;
        private readonly PrefabSystem _prefabs;
        private readonly NameSystem _names;
        private readonly CitySystem _citySystem;
        private readonly CityServiceBudgetSystem _budget;
        private readonly TerrainSystem _terrain;
        private readonly WaterSystem _water;
        private readonly Dictionary<Entity, NetPrefab> _netPrefabs = new Dictionary<Entity, NetPrefab>();
        private readonly Dictionary<Entity, BuildingPrefab> _buildingPrefabs = new Dictionary<Entity, BuildingPrefab>();
        private readonly Dictionary<Entity, Lanes> _lanes = new Dictionary<Entity, Lanes>();
        private readonly Dictionary<Entity, int> _streets = new Dictionary<Entity, int>();
        private readonly HashSet<Entity> _nodes = new HashSet<Entity>();
        private int _phase;
        private readonly List<KeyValuePair<string, Func<bool>>> _steps = new List<KeyValuePair<string, Func<bool>>>();
        private readonly Dictionary<Entity, int> _districtIndex = new Dictionary<Entity, int>();
        private readonly Dictionary<Entity, int2> _prefabLanes = new Dictionary<Entity, int2>();   // lanes as built, per road prefab

        public readonly CitySnapshot Snap = new CitySnapshot();
        public readonly string Path;
        public double MainMs, LongestMs;
        public string LongestPart = "";
        public int Frames;

        public CityReader(World world, Queries queries, string path)
        {
            _em = world.EntityManager;
            _q = queries;
            Path = path;
            _prefabs = world.GetOrCreateSystemManaged<PrefabSystem>();
            _names = world.GetOrCreateSystemManaged<NameSystem>();
            _citySystem = world.GetOrCreateSystemManaged<CitySystem>();
            _budget = world.GetOrCreateSystemManaged<CityServiceBudgetSystem>();
            _terrain = world.GetOrCreateSystemManaged<TerrainSystem>();
            _water = world.GetOrCreateSystemManaged<WaterSystem>();
            _world = world;
            // Each step reads one part; a step that returns false runs again next frame (big lists go in slices).
            Steps(("city", City), ("economy", Economy), ("people", People), ("problems", Problems), ("networks", Networks),
                  ("zoning", Zoning), ("catalogue", Catalogue), ("transit", Transit), ("map tiles", MapTiles), ("grids", Grids),
                  ("buildings", Buildings), ("terrain", TerrainSlice));
        }

        private readonly World _world;

        private void Steps(params (string, Func<bool>)[] steps)
        {
            foreach (var (name, run) in steps) _steps.Add(new KeyValuePair<string, Func<bool>>(name, run));
        }

        private Func<bool> Once(Action a) => () => { a(); return true; };

        /// <summary>Reads the next part. True when every part is read.</summary>
        public bool Step()
        {
            var sw = Stopwatch.StartNew();
            var step = _steps[_phase];
            bool done;
            try
            {
                done = step.Value();
            }
            catch (Exception e)
            {
                // One part failing (a game update renamed something) leaves the rest of the snapshot intact.
                Snap.Truncated.Add(step.Key + " (failed: " + e.GetType().Name + ")");
                Mod.Log.Warn($"Snapshot part {step.Key} failed: {e}");
                done = true;
            }
            if (done) _phase++;
            var ms = sw.Elapsed.TotalMilliseconds;
            MainMs += ms;
            if (ms > LongestMs)
            {
                LongestMs = ms;
                LongestPart = step.Key;
            }
            Frames++;
            return _phase >= _steps.Count;
        }

        private bool Has<T>(Entity e) where T : struct, IComponentData => e != Entity.Null && _em.HasComponent<T>(e);

        private bool TryGet<T>(Entity e, out T value) where T : unmanaged, IComponentData
        {
            if (e != Entity.Null && _em.HasComponent<T>(e))
            {
                value = _em.GetComponentData<T>(e);
                return true;
            }
            value = default;
            return false;
        }

        private string PrefabName(Entity prefab)
        {
            try
            {
                return _prefabs.GetPrefabName(prefab);
            }
            catch (Exception)
            {
                return "?";
            }
        }

        private string Label(Entity e, int max)
        {
            try
            {
                return JournalStore.Clean(_names.GetRenderedLabelName(e) ?? "", max);
            }
            catch (Exception)
            {
                return "";
            }
        }

        // --- 0: the city's numbers, the budget, districts and owned tiles

        private bool City()
        {
            var city = _citySystem.City;
            if (TryGet<Game.City.Population>(city, out var pop))
            {
                Snap.Population = pop.m_Population;
                Snap.Happiness = pop.m_AverageHappiness;
            }
            if (TryGet<Game.City.PlayerMoney>(city, out var money))
            {
                Snap.Money = money.money;
                Snap.UnlimitedMoney = money.m_Unlimited;
            }
            if (TryGet<Game.City.XP>(city, out var xp)) Snap.Xp = xp.m_XP;
            if (TryGet<Game.City.MilestoneLevel>(city, out var ms)) Snap.Milestone = ms.m_AchievedMilestone;

            var income = _budget.GetIncomeArray(out JobHandle incomeDeps);
            incomeDeps.Complete();
            for (var i = 0; i < (int)IncomeSource.Count; i++)
                Snap.Income.Add(new KeyValuePair<string, int>(((IncomeSource)i).ToString(), CityServiceBudgetSystem.GetIncome((IncomeSource)i, income)));
            var expenses = _budget.GetExpenseArray(out JobHandle expenseDeps);
            expenseDeps.Complete();
            for (var i = 0; i < (int)ExpenseSource.Count; i++)
                Snap.Expenses.Add(new KeyValuePair<string, int>(((ExpenseSource)i).ToString(), CityServiceBudgetSystem.GetExpense((ExpenseSource)i, expenses)));
            Snap.TotalIncome = CityServiceBudgetSystem.GetTotalIncome(income);
            Snap.TotalExpenses = Math.Abs(CityServiceBudgetSystem.GetTotalExpenses(expenses));   // the game keeps the total negative; the lines are positive
            Snap.Balance = CityServiceBudgetSystem.GetBalance(income, expenses);

            using (var districts = _q.Districts.ToEntityArray(Allocator.Temp))
            {
                foreach (var d in districts)
                {
                    var district = new CitySnapshot.District { Name = Label(d, 200), Policies = PoliciesOf(d) };
                    _districtIndex[d] = Snap.Districts.Count;
                    var nodes = _em.GetBuffer<AreaNode>(d, true);
                    for (var i = 0; i < nodes.Length && i < CitySnapshot.MaxOutline; i++)
                        district.Outline.Add(new[] { nodes[i].m_Position.x, nodes[i].m_Position.z });
                    Snap.AddDistrict(district);
                }
            }

            using (var tiles = _q.Tiles.ToEntityArray(Allocator.Temp))
            {
                foreach (var t in tiles)
                {
                    var nodes = _em.GetBuffer<AreaNode>(t, true);
                    if (nodes.Length == 0) continue;
                    float x0 = float.MaxValue, x1 = float.MinValue, z0 = float.MaxValue, z1 = float.MinValue;
                    for (var i = 0; i < nodes.Length; i++)
                    {
                        var p = nodes[i].m_Position;
                        x0 = math.min(x0, p.x); x1 = math.max(x1, p.x);
                        z0 = math.min(z0, p.z); z1 = math.max(z1, p.z);
                    }
                    Snap.Tiles.Add(new[] { x0, x1, z0, z1 });
                }
            }
            Snap.OwnedTiles = Snap.Tiles.Count;
            return true;
        }

        // --- 1: roads, rail and paths, with their end nodes

        private NetPrefab NetPrefabOf(Entity prefab)
        {
            if (_netPrefabs.TryGetValue(prefab, out var info)) return info;
            string kind = null;
            if (TryGet<RoadData>(prefab, out var road))
                kind = (road.m_Flags & RoadFlags.UseHighwayRules) != 0 ? "highway" : "road";
            else if (TryGet<TrackData>(prefab, out var track))
                kind = (track.m_TrackType & Game.Net.TrackTypes.Train) != 0 ? "train"
                    : (track.m_TrackType & Game.Net.TrackTypes.Tram) != 0 ? "tram"
                    : (track.m_TrackType & Game.Net.TrackTypes.Subway) != 0 ? "subway" : "track";
            else if (Has<PathwayData>(prefab))
                kind = "path";
            info = new NetPrefab { Kind = kind, Index = kind == null ? -1 : PrefabIndex(prefab) };
            _netPrefabs[prefab] = info;
            return info;
        }

        /// <summary>Car and bus lanes per direction, and whether the piece is a tunnel or a bridge, from the edge's
        /// composition (shared by every edge built the same way).</summary>
        private Lanes LanesOf(Entity composition)
        {
            if (_lanes.TryGetValue(composition, out var lanes)) return lanes;
            lanes = new Lanes();
            if (TryGet<NetCompositionData>(composition, out var data))
            {
                lanes.Tunnel = (data.m_Flags.m_General & CompositionFlags.General.Tunnel) != 0;
                lanes.Bridge = (data.m_Flags.m_General & CompositionFlags.General.Elevated) != 0;
            }
            if (TryGet<RoadComposition>(composition, out var rc) && rc.m_SpeedLimit > 0f)
                lanes.SpeedKmh = (int)math.round(rc.m_SpeedLimit * 3.6f);   // stored in metres per second
            if (composition != Entity.Null && _em.HasBuffer<NetCompositionLane>(composition))
            {
                const LaneFlags skip = LaneFlags.Master | LaneFlags.Parking | LaneFlags.Pedestrian | LaneFlags.Utility
                    | LaneFlags.Virtual | LaneFlags.BicyclesOnly;
                var buffer = _em.GetBuffer<NetCompositionLane>(composition, true);
                for (var i = 0; i < buffer.Length; i++)
                {
                    var f = buffer[i].m_Flags;
                    if ((f & LaneFlags.Road) == 0 || (f & skip) != 0) continue;
                    lanes.Any = true;
                    var bus = (f & LaneFlags.PublicOnly) != 0;
                    var back = (f & LaneFlags.Invert) != 0;
                    var both = (f & LaneFlags.Twoway) != 0;
                    if (!back || both) { if (bus) lanes.BusForward++; else lanes.Forward++; }
                    if (back || both) { if (bus) lanes.BusBackward++; else lanes.Backward++; }
                }
            }
            _lanes[composition] = lanes;
            return lanes;
        }

        private int StreetOf(Entity edge)
        {
            if (!TryGet<Game.Net.Aggregated>(edge, out var agg) || agg.m_Aggregate == Entity.Null) return -1;
            if (_streets.TryGetValue(agg.m_Aggregate, out var index)) return index;
            var name = Label(agg.m_Aggregate, 200);
            index = name == "" ? -1 : Snap.Streets.Of(name);
            _streets[agg.m_Aggregate] = index;
            return index;
        }

        private bool Networks()
        {
            using (var edges = _q.Edges.ToEntityArray(Allocator.Temp))
            {
                foreach (var e in edges)
                {
                    var info = NetPrefabOf(_em.GetComponentData<PrefabRef>(e).m_Prefab);
                    if (info.Kind == null) continue;
                    var owned = Has<Owner>(e);
                    if (owned && info.Kind == "path") continue;   // a building's own footpaths
                    var ends = _em.GetComponentData<Edge>(e);
                    var curve = _em.GetComponentData<Curve>(e);
                    var b = curve.m_Bezier;
                    var item = new CitySnapshot.Edge
                    {
                        Id = e.Index,
                        Prefab = info.Index,
                        Kind = info.Kind,
                        A = ends.m_Start.Index,
                        B = ends.m_End.Index,
                        Length = curve.m_Length,
                        Owned = owned,
                        Pts = new[] { b.a.x, b.a.z, b.a.y, b.b.x, b.b.z, b.b.y, b.c.x, b.c.z, b.c.y, b.d.x, b.d.z, b.d.y },
                    };
                    if (TryGet<Elevation>(e, out var elevation))
                    {
                        item.ElevationA = elevation.m_Elevation.x;
                        item.ElevationB = elevation.m_Elevation.y;
                    }
                    if (TryGet<Composition>(e, out var composition))
                    {
                        var lanes = LanesOf(composition.m_Edge);
                        item.Tunnel = lanes.Tunnel;
                        item.Bridge = lanes.Bridge;
                        item.SpeedKmh = lanes.SpeedKmh;
                        if (info.Kind == "road" || info.Kind == "highway" || lanes.Any)
                        {
                            item.HasLanes = true;
                            item.LanesForward = lanes.Forward;
                            item.LanesBackward = lanes.Backward;
                            item.BusForward = lanes.BusForward;
                            item.BusBackward = lanes.BusBackward;
                            var prefabEntity = _em.GetComponentData<PrefabRef>(e).m_Prefab;
                            if (!owned && lanes.Forward + lanes.Backward > 0 && !_prefabLanes.ContainsKey(prefabEntity))
                                _prefabLanes[prefabEntity] = new int2(lanes.Forward, lanes.Backward);
                        }
                    }
                    if (info.Kind == "road" || info.Kind == "highway")
                    {
                        item.Street = StreetOf(e);
                        if (TryGet<Game.Net.Road>(e, out var road))
                        {
                            var flow = math.csum(Game.Net.NetUtils.GetTrafficFlowSpeed(road)) * 25f;
                            if (!float.IsNaN(flow) && !float.IsInfinity(flow)) item.Flow = (int)math.round(math.clamp(flow, 0f, 100f));
                            // The road panel's volume: distance driven per day quarter, scaled as the game scales it, averaged.
                            var volume = math.csum((road.m_TrafficFlowDistance0 + road.m_TrafficFlowDistance1) * 2.666667f) * 0.25f;
                            if (!float.IsNaN(volume) && !float.IsInfinity(volume)) item.Volume = (int)math.round(math.max(volume, 0f));
                        }
                        if (TryGet<Game.Net.Upgraded>(e, out var up)) item.Upgrades = UpgradeNames(up.m_Flags);
                    }
                    if (!Snap.AddEdge(item)) break;
                    AddNode(ends.m_Start);
                    AddNode(ends.m_End);
                }
            }
            return true;
        }

        /// <summary>The upgrades the Mayor added to a road (not the ones built into its type).</summary>
        private static List<string> UpgradeNames(CompositionFlags f)
        {
            var o = new List<string>();
            var side = f.m_Left | f.m_Right;
            if ((f.m_General & CompositionFlags.General.Lighting) != 0) o.Add("lighting");
            if ((side & CompositionFlags.Side.PrimaryBeautification) != 0) o.Add("grass");
            if ((side & CompositionFlags.Side.SecondaryBeautification) != 0) o.Add("trees");
            if ((side & CompositionFlags.Side.WideSidewalk) != 0) o.Add("wide sidewalk");
            if ((side & CompositionFlags.Side.SoundBarrier) != 0) o.Add("sound barrier");
            if ((side & CompositionFlags.Side.ParkingSpaces) != 0) o.Add("parking");
            if ((f.m_General & CompositionFlags.General.PrimaryMiddleBeautification) != 0) o.Add("median grass");
            if ((f.m_General & CompositionFlags.General.SecondaryMiddleBeautification) != 0) o.Add("median trees");
            return o;
        }

        private void AddNode(Entity node)
        {
            if (!_nodes.Add(node) || !TryGet<NetNode>(node, out var n)) return;
            Snap.AddNode(new CitySnapshot.Node
            {
                Id = node.Index,
                X = n.m_Position.x,
                Z = n.m_Position.z,
                Y = n.m_Position.y,
                Lights = Has<Game.Net.TrafficLights>(node),
                Roundabout = Has<Game.Net.Roundabout>(node),
                Outside = Has<Game.Net.OutsideConnection>(node) || Has<Game.Objects.OutsideConnection>(node),
            });
        }

        // --- 2: buildings on their own lots

        private BuildingPrefab BuildingPrefabOf(Entity prefab)
        {
            if (_buildingPrefabs.TryGetValue(prefab, out var info)) return info;
            info = new BuildingPrefab { Index = PrefabIndex(prefab), Kind = "other" };
            if (TryGet<BuildingData>(prefab, out var data))
            {
                info.LotWidth = data.m_LotSize.x;
                info.LotDepth = data.m_LotSize.y;
            }
            if (Has<SignatureBuildingData>(prefab))
            {
                info.Kind = "signature";
            }
            else if (TryGet<SpawnableBuildingData>(prefab, out var spawnable))
            {
                info.Level = spawnable.m_Level;
                if (TryGet<ZoneData>(spawnable.m_ZonePrefab, out var zone))
                {
                    switch (zone.m_AreaType)
                    {
                        case Game.Zones.AreaType.Residential: info.Kind = "residential"; break;
                        case Game.Zones.AreaType.Commercial: info.Kind = "commercial"; break;
                        case Game.Zones.AreaType.Industrial: info.Kind = (zone.m_ZoneFlags & ZoneFlags.Office) != 0 ? "office" : "industrial"; break;
                    }
                }
            }
            else if (TryGet<ServiceObjectData>(prefab, out var service))
            {
                info.Kind = "service";
                info.Service = service.m_Service == Entity.Null ? "" : PrefabName(service.m_Service);
            }
            _buildingPrefabs[prefab] = info;
            return info;
        }

        private const int BuildingsPerFrame = 4000;
        private Entity[] _buildingList;
        private int _buildingNext;

        private bool Buildings()
        {
            if (_buildingList == null)
            {
                using (var all = _q.Buildings.ToEntityArray(Allocator.Temp)) _buildingList = all.ToArray();
            }
            var end = Math.Min(_buildingList.Length, _buildingNext + BuildingsPerFrame);
            for (; _buildingNext < end; _buildingNext++)
            {
                var e = _buildingList[_buildingNext];
                if (!_em.Exists(e) || !_em.HasComponent<PrefabRef>(e)) continue;   // gone since the list was taken
                {
                    var info = BuildingPrefabOf(_em.GetComponentData<PrefabRef>(e).m_Prefab);
                    var t = _em.GetComponentData<Transform>(e);
                    var forward = math.mul(t.m_Rotation, new float3(0f, 0f, 1f));
                    var angle = math.degrees(math.atan2(forward.x, forward.z));
                    var item = new CitySnapshot.Building
                    {
                        Id = e.Index,
                        Prefab = info.Index,
                        Kind = info.Kind,
                        Level = info.Level,
                        Service = info.Service,
                        LotWidth = info.LotWidth,
                        LotDepth = info.LotDepth,
                        X = t.m_Position.x,
                        Z = t.m_Position.z,
                        Y = t.m_Position.y,
                        Angle = angle < 0f ? angle + 360f : angle,
                        Abandoned = Has<Game.Buildings.Abandoned>(e),
                        Condemned = Has<Game.Buildings.Condemned>(e),
                    };
                    if (!CitySnapshot.IsZoned(info.Kind)) item.Name = Label(e, 120);
                    if (TryGet<Game.Areas.CurrentDistrict>(e, out var cd) && _districtIndex.TryGetValue(cd.m_District, out var di)) item.District = di;
                    BuildingDetails(e, _em.GetComponentData<PrefabRef>(e).m_Prefab, item);
                    if (!Snap.AddBuilding(item))
                    {
                        _buildingNext = _buildingList.Length;
                        break;
                    }
                }
            }
            return _buildingNext >= _buildingList.Length;
        }

        // --- 3 to 6: the terrain and water on a 256 x 256 grid (56 m cells), a quarter of the rows per frame

        private const int TerrainSlices = 4;
        private ushort[] _heightGrid, _waterGrid;
        private int _terrainSlice;

        private bool TerrainSlice()
        {
            var slice = _terrainSlice++;
            var heights = _terrain.GetHeightData();
            if (!heights.isCreated) return true;   // the snapshot then has no terrain section
            var water = _water.GetSurfaceData(out JobHandle waterDeps);
            waterDeps.Complete();
            var size = TerrainSize;
            var cell = 2f * MapHalfSize / size;
            var h = _heightGrid ?? (_heightGrid = new ushort[size * size]);
            var d = _waterGrid ?? (_waterGrid = new ushort[size * size]);
            for (var row = slice * size / TerrainSlices; row < (slice + 1) * size / TerrainSlices; row++)
            {
                var z = -MapHalfSize + (row + 0.5f) * cell;
                for (var col = 0; col < size; col++)
                {
                    var p = new float3(-MapHalfSize + (col + 0.5f) * cell, 0f, z);
                    h[row * size + col] = CitySnapshot.Decimetres(TerrainUtils.SampleHeight(ref heights, p));
                    if (water.isCreated)
                    {
                        var depth = WaterUtils.SampleDepth(ref water, p);
                        d[row * size + col] = depth > 0.05f ? CitySnapshot.Decimetres(depth) : (ushort)0;
                    }
                }
            }
            if (slice < TerrainSlices - 1) return false;
            Snap.TerrainSize = size;
            Snap.TerrainCell = cell;
            Snap.TerrainOrigin = -MapHalfSize;
            Snap.Heights = h;
            Snap.Water = d;
            return true;
        }
    }
}
