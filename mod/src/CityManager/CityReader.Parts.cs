// The city-wide parts of the snapshot (step 4b): demand and money, people and jobs, problems on the map, how full each
// service building is, transit lines, zoning along roads, the build catalogue, map tiles and coarse land-value and
// pollution grids. Same rules as CityReader.cs: main thread, read only, one step per frame. Which game APIs to use was
// worked out from the game's code and its own UI systems (they show these numbers to the player), cross-checked with
// the LancerComet CS2 MCP bridge (Apache-2.0); this is our own code.

using System;
using System.Collections.Generic;
using Game.City;
using Game.Prefabs;
using Game.Simulation;
using Newtonsoft.Json.Linq;
using Unity.Collections;
using Unity.Entities;
using Unity.Jobs;
using Unity.Mathematics;
using Building = Game.Buildings.Building;
using Deleted = Game.Common.Deleted;
using NetNode = Game.Net.Node;
using Owner = Game.Common.Owner;
using Temp = Game.Tools.Temp;

namespace CityManager
{
    internal sealed partial class CityReader
    {
        public const int MaxProblems = 20000, MaxStops = 500, MaxLines = 2000, GridSize = 64;

        private T Sys<T>() where T : ComponentSystemBase => _world.GetOrCreateSystemManaged<T>();

        /// <summary>Which prefabs are locked: a lookup only a system can make, so JournalSystem updates and sets it
        /// before every step.</summary>
        public ComponentLookup<Locked> LockedLookup;

        /// <summary>A text from the game's language file, or null.</summary>
        private static string Loc(string key)
        {
            try
            {
                var d = Game.SceneFlow.GameManager.instance?.localizationManager?.activeDictionary;
                return d != null && d.TryGetValue(key, out var v) ? JournalStore.Clean(v, 200) : null;
            }
            catch (Exception)
            {
                return null;
            }
        }

        /// <summary>A prefab's place in the snapshot's prefab table, with its menu name in the game's language.</summary>
        private int PrefabIndex(Entity prefab)
        {
            var name = PrefabName(prefab);
            var i = Snap.Prefabs.Of(name);
            if (!Snap.PrefabTitles.ContainsKey(i)) Snap.PrefabTitles[i] = Loc($"Assets.NAME[{name}]") ?? "";
            return i;
        }

        private bool Enabled<T>(Entity e) where T : struct, IComponentData, IEnableableComponent =>
            _em.HasComponent<T>(e) && _em.IsComponentEnabled<T>(e);

        private int BufferLength<T>(Entity e) where T : unmanaged, IBufferElementData =>
            _em.HasBuffer<T>(e) ? _em.GetBuffer<T>(e, true).Length : 0;

        // --- demand, taxes, fees, service budgets, the loan, policies and the monthly history

        private bool Economy()
        {
            var res = Sys<ResidentialDemandSystem>();
            var com = Sys<CommercialDemandSystem>();
            var ind = Sys<IndustrialDemandSystem>();
            var demand = new JObject
            {
                ["residentialLow"] = res.buildingDemand.x,
                ["residentialMedium"] = res.buildingDemand.y,
                ["residentialHigh"] = res.buildingDemand.z,
                ["commercial"] = com.buildingDemand,
                ["industrial"] = ind.industrialBuildingDemand,
                ["storage"] = ind.storageBuildingDemand,
                ["office"] = ind.officeBuildingDemand,
            };
            var factors = new JObject();
            void Factors(string name, NativeArray<int> values, JobHandle deps)
            {
                deps.Complete();
                var o = new JObject();
                for (var i = 0; i < values.Length; i++)
                    if (values[i] != 0) o[((DemandFactor)i).ToString()] = values[i];
                if (o.Count > 0) factors[name] = o;
            }
            Factors("residentialLow", res.GetLowDensityDemandFactors(out var d1), d1);
            Factors("residentialMedium", res.GetMediumDensityDemandFactors(out var d2), d2);
            Factors("residentialHigh", res.GetHighDensityDemandFactors(out var d3), d3);
            Factors("commercial", com.GetDemandFactors(out var d4), d4);
            Factors("industrial", ind.GetIndustrialDemandFactors(out var d5), d5);
            Factors("office", ind.GetOfficeDemandFactors(out var d6), d6);
            demand["factors"] = factors;
            Snap.Section("demand", demand);

            var tax = Sys<TaxSystem>();
            var byEducation = new JArray();
            for (var i = 0; i < 5; i++) byEducation.Add(tax.GetResidentialTaxRate(i));
            Snap.Section("taxes", new JObject
            {
                ["residential"] = tax.GetTaxRate(TaxAreaType.Residential),
                ["commercial"] = tax.GetTaxRate(TaxAreaType.Commercial),
                ["industrial"] = tax.GetTaxRate(TaxAreaType.Industrial),
                ["office"] = tax.GetTaxRate(TaxAreaType.Office),
                ["residentialByEducation"] = byEducation,
            });

            var city = _citySystem.City;
            if (city != Entity.Null && _em.HasBuffer<ServiceFee>(city))
            {
                var fees = _em.GetBuffer<ServiceFee>(city, true);
                var hasParams = !_q.FeeParams.IsEmptyIgnoreFilter;
                var parameters = hasParams ? _q.FeeParams.GetSingleton<ServiceFeeParameterData>() : default;
                var o = new JObject();
                foreach (PlayerResource r in Enum.GetValues(typeof(PlayerResource)))
                {
                    if (!ServiceFeeSystem.TryGetFee(r, fees, out var fee)) continue;
                    var item = new JObject { ["fee"] = fee };
                    try
                    {
                        // The slider shows 200 × fee / max: the default fee reads 100%.
                        var max = hasParams ? parameters.GetFeeParameters(r).m_Max : 0f;
                        if (max > 0f) item["percent"] = Math.Round(200.0 * fee / max);
                    }
                    catch (Exception)
                    {
                    }
                    o[r.ToString()] = item;
                }
                Snap.Section("fees", o);
            }

            var services = new JArray();
            using (var list = Game.UI.UIObjectInfo.GetSortedObjects(_em, _q.Services, Allocator.Temp))
            {
                for (var i = 0; i < list.Length; i++)
                {
                    var e = list[i].entity;
                    if (Enabled<Locked>(e)) continue;
                    var name = PrefabName(e);
                    var budget = _budget.GetServiceBudget(e);
                    _budget.GetEstimatedServiceBudget(e, out var upkeep);
                    services.Add(new JObject
                    {
                        ["service"] = name,
                        ["title"] = Loc($"Services.NAME[{name}]") ?? name,
                        ["budget"] = budget,
                        ["efficiency"] = _budget.GetServiceEfficiency(e, budget),
                        ["upkeep"] = upkeep,
                        ["adjustable"] = _em.GetComponentData<ServiceData>(e).m_BudgetAdjustable,
                    });
                }
            }
            Snap.Section("services", services);

            var loan = Sys<Game.Tools.LoanSystem>();
            var current = loan.CurrentLoan;
            Snap.Section("loan", new JObject
            {
                ["amount"] = current.m_Amount,
                ["interestPercent"] = Math.Round(current.m_DailyInterestRate * 100.0, 2),
                ["monthlyCost"] = current.m_DailyPayment,
                ["limit"] = loan.Creditworthiness,
            });

            Snap.Section("policies", PoliciesOf(city));
            Snap.Section("history", History());
            return true;
        }

        private JArray PoliciesOf(Entity owner)
        {
            var a = new JArray();
            if (owner == Entity.Null || !_em.HasBuffer<Game.Policies.Policy>(owner)) return a;
            foreach (var p in _em.GetBuffer<Game.Policies.Policy>(owner, true))
            {
                if ((p.m_Flags & Game.Policies.PolicyFlags.Active) == 0) continue;
                var name = PrefabName(p.m_Policy);
                var o = new JObject { ["policy"] = name, ["title"] = Loc($"Policy.TITLE[{name}]") ?? name };
                if (Has<PolicySliderData>(p.m_Policy)) o["value"] = p.m_Adjustment;
                a.Add(o);
            }
            return a;
        }

        /// <summary>The game's own statistics, one value per in-game month (32 samples a month), oldest first, up to 24
        /// months: what its Statistics panel charts.</summary>
        private JObject History()
        {
            var st = Sys<CityStatisticsSystem>();
            const int perMonth = 32, months = 24;
            double[] Monthly(StatisticType type, int parameter)
            {
                var a = st.GetStatisticArray(type, parameter);
                if (!a.IsCreated || a.Length == 0) return null;
                var n = Math.Min(months, (a.Length + perMonth - 1) / perMonth);
                var o = new double[n];
                for (var k = 0; k < n; k++) o[n - 1 - k] = a[a.Length - 1 - perMonth * k].m_TotalValue;
                return o;
            }
            double[] Sum(StatisticType type, int count)
            {
                double[] total = null;
                for (var p = 0; p < count; p++)
                {
                    var m = Monthly(type, p);
                    if (m == null) continue;
                    if (total == null || m.Length > total.Length)
                    {
                        var grown = new double[m.Length];
                        if (total != null) Array.Copy(total, 0, grown, m.Length - total.Length, total.Length);
                        total = grown;
                    }
                    for (var k = 0; k < m.Length; k++) total[total.Length - m.Length + k] += m[k];   // newest ends line up
                }
                return total;
            }
            JArray Round(double[] v, int digits = 0)
            {
                var a = new JArray();
                if (v != null) foreach (var x in v) a.Add(Math.Round(x, digits));
                return a;
            }
            var population = Monthly(StatisticType.Population, 0);
            double[] PerPerson(double[] totals)
            {
                if (totals == null || population == null) return null;
                var n = Math.Min(totals.Length, population.Length);
                var o = new double[n];
                for (var k = 0; k < n; k++)
                {
                    var pop = population[population.Length - n + k];
                    o[k] = pop > 0 ? totals[totals.Length - n + k] / pop : 0;
                }
                return o;
            }
            return new JObject
            {
                ["perMonth"] = "oldest first, the last value is now",
                ["population"] = Round(population),
                ["money"] = Round(Monthly(StatisticType.Money, 0)),
                ["income"] = Round(Sum(StatisticType.Income, (int)IncomeSource.Count)),
                ["expenses"] = Round(Sum(StatisticType.Expense, (int)ExpenseSource.Count)),
                ["households"] = Round(Monthly(StatisticType.HouseholdCount, 0)),
                ["workers"] = Round(Monthly(StatisticType.WorkerCount, 0)),
                ["unemployed"] = Round(Monthly(StatisticType.Unemployed, 0)),
                ["happiness"] = Round(PerPerson(Monthly(StatisticType.Wellbeing, 0)), 1),
                ["health"] = Round(PerPerson(Monthly(StatisticType.Health, 0)), 1),
                ["tourists"] = Round(Monthly(StatisticType.TouristCount, 0)),
                ["crimeRate"] = Round(Monthly(StatisticType.CrimeRate, 0), 1),
                ["busPassengers"] = Round(Monthly(StatisticType.PassengerCountBus, 0)),
                ["tramPassengers"] = Round(Monthly(StatisticType.PassengerCountTram, 0)),
                ["trainPassengers"] = Round(Monthly(StatisticType.PassengerCountTrain, 0)),
                ["subwayPassengers"] = Round(Monthly(StatisticType.PassengerCountSubway, 0)),
            };
        }

        // --- people, jobs, happiness and utilities (totals the game already keeps for its info panels)

        private bool People()
        {
            var hh = Sys<CountHouseholdDataSystem>();
            var pop = TryGet<Population>(_citySystem.City, out var p) ? p : default;
            Snap.Section("people", new JObject
            {
                ["households"] = hh.MovedInHouseholdCount,
                ["residents"] = hh.MovedInCitizenCount,
                ["children"] = hh.ChildrenCount,
                ["teens"] = hh.TeenCount,
                ["adults"] = hh.AdultCount,
                ["seniors"] = hh.SeniorCount,
                ["students"] = hh.StudentCount,
                ["education"] = new JArray(hh.UneducatedCount, hh.PoorlyEducatedCount, hh.EducatedCount, hh.WellEducatedCount, hh.HighlyEducatedCount),
                ["workable"] = hh.WorkableCitizenCount,
                ["workers"] = hh.CityWorkerCount,
                ["unemploymentPercent"] = Math.Round(hh.UnemploymentRate, 1),
                ["homelessHouseholds"] = hh.HomelessHouseholdCount,
                ["homeless"] = hh.HomelessCitizenCount,
                ["health"] = pop.m_AverageHealth,
            });

            var wp = Sys<CountWorkplacesSystem>();
            var total = wp.GetTotalWorkplaces();
            var free = wp.GetFreeWorkplaces();
            JArray Levels(Game.Companies.Workplaces w)
            {
                var a = new JArray();
                for (var i = 0; i < 5; i++) a.Add(w[i]);
                return a;
            }
            Snap.Section("jobs", new JObject
            {
                ["total"] = total.TotalCount,
                ["free"] = free.TotalCount,
                ["filled"] = total.TotalCount - free.TotalCount,
                ["totalByEducation"] = Levels(total),
                ["freeByEducation"] = Levels(free),
            });

            var factors = new List<KeyValuePair<string, int>>();
            if (!_q.HappinessParams.IsEmptyIgnoreFilter)
            {
                var hs = Sys<CitizenHappinessSystem>();
                var parameters = _em.GetBuffer<HappinessFactorParameterData>(_q.HappinessParams.GetSingletonEntity(), true);
                var locked = LockedLookup;   // handed over by the system, updated this frame
                for (var i = 0; i < (int)CitizenHappinessSystem.HappinessFactor.Count; i++)
                {
                    var f = (CitizenHappinessSystem.HappinessFactor)i;
                    var points = (int)math.round(hs.GetHappinessFactor(f, parameters, ref locked).x);
                    if (points != 0) factors.Add(new KeyValuePair<string, int>(f.ToString(), points));
                }
            }
            factors.Sort((a, b) => Math.Abs(b.Value).CompareTo(Math.Abs(a.Value)));
            var fa = new JArray();
            foreach (var f in factors) fa.Add(new JObject { ["factor"] = f.Key, ["points"] = f.Value });
            Snap.Section("happiness", new JObject { ["average"] = pop.m_AverageHappiness, ["factors"] = fa });

            var el = Sys<ElectricityStatisticsSystem>();
            var et = Sys<ElectricityTradeSystem>();
            var ws = Sys<WaterStatisticsSystem>();
            Snap.Section("utilities", new JObject
            {
                ["electricity"] = new JObject
                {
                    ["production"] = el.production, ["consumption"] = el.consumption, ["fulfilled"] = el.fulfilledConsumption,
                    ["batteryCharge"] = el.batteryCharge, ["batteryCapacity"] = el.batteryCapacity,
                    ["import"] = et.import, ["export"] = et.export,
                },
                ["water"] = new JObject
                {
                    ["freshCapacity"] = ws.freshCapacity, ["freshConsumption"] = ws.freshConsumption,
                    ["sewageCapacity"] = ws.sewageCapacity, ["sewageConsumption"] = ws.sewageConsumption,
                },
            });
            return true;
        }

        // --- problems: the warning icons over buildings, roads and junctions

        private bool Problems()
        {
            var kinds = new Dictionary<Entity, int>();
            var kindList = new JArray();
            var counts = new List<int>();
            var items = new JArray();
            using (var ents = _q.Icons.ToEntityArray(Allocator.Temp))
            using (var icons = _q.Icons.ToComponentDataArray<Game.Notifications.Icon>(Allocator.Temp))
            {
                for (var i = 0; i < ents.Length; i++)
                {
                    var icon = icons[i];
                    // Markers (selection, routes) and money pop-ups aren't problems, nor is plain information.
                    if (icon.m_ClusterLayer != Game.Notifications.IconClusterLayer.Default || icon.m_Priority < Game.Notifications.IconPriority.Problem) continue;
                    if (TryGet<Game.Notifications.Animation>(ents[i], out var anim) && anim.m_Type == Game.Notifications.AnimationType.WarningResolve) continue;
                    var prefab = _em.GetComponentData<PrefabRef>(ents[i]).m_Prefab;
                    if (!kinds.TryGetValue(prefab, out var k))
                    {
                        k = kindList.Count;
                        kinds[prefab] = k;
                        var name = PrefabName(prefab);
                        kindList.Add(new JObject { ["id"] = name, ["title"] = Loc($"Notifications.TITLE[{name}]") ?? name });
                        counts.Add(0);
                    }
                    counts[k]++;
                    if (items.Count >= MaxProblems)
                    {
                        if (!Snap.Truncated.Contains("problems")) Snap.Truncated.Add("problems");
                        continue;
                    }
                    var item = new JObject
                    {
                        ["kind"] = k,
                        ["x"] = CitySnapshot.R1(icon.m_Location.x),
                        ["z"] = CitySnapshot.R1(icon.m_Location.z),
                        ["level"] = icon.m_Priority.ToString(),
                    };
                    var owner = TryGet<Owner>(ents[i], out var o) ? o.m_Owner : Entity.Null;
                    if (Has<Building>(owner))
                    {
                        item["on"] = "building";
                        var bp = _em.GetComponentData<PrefabRef>(owner).m_Prefab;
                        item["prefab"] = PrefabIndex(bp);
                    }
                    else if (Has<Game.Net.Edge>(owner))
                    {
                        item["on"] = "road";
                        var street = StreetOf(owner);
                        if (street >= 0) item["street"] = street;
                    }
                    else if (Has<NetNode>(owner)) item["on"] = "junction";
                    else if (Has<Game.Vehicles.Vehicle>(owner)) item["on"] = "vehicle";
                    else if (Has<Game.Citizens.Citizen>(owner) || Has<Game.Creatures.Creature>(owner)) item["on"] = "citizen";
                    else item["on"] = "other";
                    items.Add(item);
                }
            }
            for (var k = 0; k < kindList.Count; k++) kindList[k]["count"] = counts[k];
            Snap.Section("problems", new JObject { ["kinds"] = kindList, ["items"] = items });
            return true;
        }

        // --- per building: how full a service building is, its efficiency, the homes and jobs of a zoned one

        private void BuildingDetails(Entity e, Entity prefab, CitySnapshot.Building item)
        {
            var zoned = CitySnapshot.IsZoned(item.Kind);
            if (!zoned && _em.HasBuffer<Game.Buildings.Efficiency>(e))
                item.Efficiency = (int)math.round(100f * Game.Buildings.BuildingUtils.GetEfficiency(_em.GetBuffer<Game.Buildings.Efficiency>(e, true)));
            if (!zoned) ServiceUse(e, prefab, item);

            if (_em.HasBuffer<Game.Buildings.Renter>(e))
            {
                int households = 0, workers = -1, max = 0;
                foreach (var r in _em.GetBuffer<Game.Buildings.Renter>(e, true))
                {
                    if (Has<Game.Citizens.Household>(r.m_Renter)) households++;
                    else if (Has<Game.Companies.CompanyData>(r.m_Renter))
                    {
                        workers = Math.Max(workers, 0) + BufferLength<Game.Companies.Employee>(r.m_Renter);
                        if (TryGet<Game.Companies.WorkProvider>(r.m_Renter, out var wp)) max += wp.m_MaxWorkers;
                    }
                }
                if (TryGet<BuildingPropertyData>(prefab, out var bp) && bp.m_ResidentialProperties > 0)
                {
                    item.Households = households;
                    item.HomesMax = bp.m_ResidentialProperties;
                }
                if (workers >= 0)
                {
                    item.Workers = workers;
                    item.WorkersMax = max;
                }
            }
        }

        private void ServiceUse(Entity e, Entity prefab, CitySnapshot.Building item)
        {
            void Use(string what, int now, int max)
            {
                item.UseWhat = what;
                item.UseNow = now;
                item.UseMax = max;
            }
            if (Has<Game.Buildings.School>(e) && UpgradeUtils.TryGetCombinedComponent(_em, e, prefab, out SchoolData school))
                Use("pupils", BufferLength<Game.Buildings.Student>(e), school.m_StudentCapacity);
            else if (Has<Game.Buildings.Hospital>(e) && UpgradeUtils.TryGetCombinedComponent(_em, e, prefab, out HospitalData hospital))
                Use("patients", BufferLength<Game.Buildings.Patient>(e), hospital.m_PatientCapacity);
            else if (Has<Game.Buildings.Prison>(e) && UpgradeUtils.TryGetCombinedComponent(_em, e, prefab, out PrisonData prison))
                Use("prisoners", BufferLength<Game.Buildings.Occupant>(e), prison.m_PrisonerCapacity);
            else if (Has<Game.Buildings.PoliceStation>(e) && UpgradeUtils.TryGetCombinedComponent(_em, e, prefab, out PoliceStationData police))
                Use("jail", BufferLength<Game.Buildings.Occupant>(e), police.m_JailCapacity);
            else if (Has<Game.Buildings.GarbageFacility>(e) && UpgradeUtils.TryGetCombinedComponent(_em, e, prefab, out GarbageFacilityData garbage))
                Use("garbage", _em.HasBuffer<Game.Economy.Resources>(e)
                    ? Game.Economy.EconomyUtils.GetResources(Game.Economy.Resource.Garbage, _em.GetBuffer<Game.Economy.Resources>(e, true)) : 0,
                    garbage.m_GarbageCapacity);
            else if (TryGet<Game.Buildings.DeathcareFacility>(e, out var deathcare) && UpgradeUtils.TryGetCombinedComponent(_em, e, prefab, out DeathcareFacilityData dd))
                Use("bodies", deathcare.m_LongTermStoredCount + BufferLength<Game.Buildings.Patient>(e), dd.m_StorageCapacity);
            else if (Has<Game.Buildings.EmergencyShelter>(e) && UpgradeUtils.TryGetCombinedComponent(_em, e, prefab, out EmergencyShelterData shelter))
                Use("sheltered", BufferLength<Game.Buildings.Occupant>(e), shelter.m_ShelterCapacity);
            else if (TryGet<Game.Buildings.ElectricityProducer>(e, out var power))
                Use("power", power.m_LastProduction, power.m_Capacity);
            else if (TryGet<Game.Buildings.WaterPumpingStation>(e, out var pump))
                Use("water", pump.m_LastProduction, pump.m_Capacity);
            else if (TryGet<Game.Buildings.SewageOutlet>(e, out var sewage))
                Use("sewage", sewage.m_LastProcessed, sewage.m_Capacity);
            else if (TryGet<Game.Buildings.Park>(e, out var park) && UpgradeUtils.TryGetCombinedComponent(_em, e, prefab, out ParkData pd))
                Use("maintenance", park.m_Maintenance, pd.m_MaintenancePool);
        }

        // --- transit lines with their stops

        private bool Transit()
        {
            var lines = new JArray();
            using (var ents = _q.Lines.ToEntityArray(Allocator.Temp))
            {
                foreach (var line in ents)
                {
                    if (lines.Count >= MaxLines) break;
                    var data = Game.UI.InGame.TransportUIUtils.BuildTransportLine(line, _em, _prefabs);
                    var prefab = _em.GetComponentData<PrefabRef>(line).m_Prefab;
                    var number = TryGet<Game.Routes.RouteNumber>(line, out var rn) ? rn.m_Number : 0;
                    string name;
                    if (!_names.TryGetCustomName(line, out name))
                    {
                        name = null;
                        if (_prefabs.TryGetPrefab<RoutePrefab>(prefab, out var rp))
                            name = Loc(rp.m_LocaleID + "[" + rp.name + "]")?.Replace("{NUMBER}", number.ToString(System.Globalization.CultureInfo.InvariantCulture));
                        name = name ?? Label(line, 200);
                    }
                    var color = data.color;
                    var stops = new JArray();
                    if (_em.HasBuffer<Game.Routes.RouteWaypoint>(line))
                    {
                        foreach (var w in _em.GetBuffer<Game.Routes.RouteWaypoint>(line, true))
                        {
                            if (stops.Count >= MaxStops) break;
                            if (!TryGet<Game.Routes.Connected>(w.m_Waypoint, out var c) || !Has<Game.Routes.TransportStop>(c.m_Connected)) continue;
                            var pos = TryGet<Game.Routes.Position>(w.m_Waypoint, out var wp) ? wp.m_Position : default;
                            var stop = new JObject { ["x"] = CitySnapshot.R1(pos.x), ["z"] = CitySnapshot.R1(pos.z) };
                            var stopName = Label(c.m_Connected, 120);
                            if (stopName != "") stop["name"] = stopName;
                            if (TryGet<Game.Routes.WaitingPassengers>(c.m_Connected, out var waiting)) stop["waiting"] = waiting.m_Count;
                            stops.Add(stop);
                        }
                    }
                    lines.Add(new JObject
                    {
                        ["kind"] = data.type.ToString(),
                        ["name"] = JournalStore.Clean(name, 200),
                        ["number"] = number,
                        ["color"] = $"#{color.r:x2}{color.g:x2}{color.b:x2}",
                        ["vehicles"] = data.vehicles,
                        ["passengers"] = data.cargo,
                        ["usagePercent"] = Math.Round(data.usage * 100.0),
                        ["length"] = CitySnapshot.R1(data.length),
                        ["active"] = data.active,
                        ["stops"] = stops,
                    });
                }
            }
            Snap.Section("transit", lines);
            return true;
        }

        // --- zoning along roads: zoned cells and how many have a building, per zone type and per road

        private bool Zoning()
        {
            var zoneNames = new Dictionary<int, (string name, string title)>();
            using (var zones = _q.ZonePrefabs.ToEntityArray(Allocator.Temp))
            {
                foreach (var z in zones)
                {
                    var zd = _em.GetComponentData<ZoneData>(z);
                    var name = PrefabName(z);
                    zoneNames[zd.m_ZoneType.m_Index] = (name, Loc($"Assets.NAME[{name}]") ?? name);
                }
            }
            var cells = new Dictionary<int, int>();
            var built = new Dictionary<int, int>();
            var perEdge = new Dictionary<int, int2>();
            using (var blocks = _q.Blocks.ToEntityArray(Allocator.Temp))
            {
                foreach (var b in blocks)
                {
                    var road = TryGet<Owner>(b, out var o) ? o.m_Owner : Entity.Null;
                    var along = int2.zero;
                    foreach (var c in _em.GetBuffer<Game.Zones.Cell>(b, true))
                    {
                        if ((c.m_State & Game.Zones.CellFlags.Visible) == 0 || c.m_Zone.Equals(Game.Zones.ZoneType.None)) continue;
                        var z = c.m_Zone.m_Index;
                        cells[z] = cells.TryGetValue(z, out var n) ? n + 1 : 1;
                        along.x++;
                        if ((c.m_State & Game.Zones.CellFlags.Occupied) != 0)
                        {
                            built[z] = built.TryGetValue(z, out var m) ? m + 1 : 1;
                            along.y++;
                        }
                    }
                    if (road != Entity.Null && along.x > 0)
                        perEdge[road.Index] = perEdge.TryGetValue(road.Index, out var prev) ? prev + along : along;
                }
            }
            foreach (var edge in Snap.Edges)
            {
                if (perEdge.TryGetValue(edge.Id, out var v))
                {
                    edge.ZoneCells = v.x;
                    edge.ZoneBuilt = v.y;
                }
            }
            var list = new JArray();
            foreach (var kv in cells)
            {
                var names = zoneNames.TryGetValue(kv.Key, out var zn) ? zn : ($"zone {kv.Key}", $"zone {kv.Key}");
                list.Add(new JObject
                {
                    ["zone"] = names.Item1,
                    ["title"] = names.Item2,
                    ["cells"] = kv.Value,
                    ["built"] = built.TryGetValue(kv.Key, out var bt) ? bt : 0,
                });
            }
            Snap.Section("zoning", new JObject { ["cellMetres"] = 8, ["zones"] = list });
            return true;
        }

        // --- the build catalogue: every road, track and prebuilt junction in the game's menus, with what unlocks it

        private bool Catalogue()
        {
            var achieved = TryGet<MilestoneLevel>(_citySystem.City, out var ml) ? ml.m_AchievedMilestone : 0;
            var items = new JArray();
            using (var nets = _q.Placeable.ToEntityArray(Allocator.Temp))
            {
                foreach (var e in nets)
                {
                    var placeable = _em.GetComponentData<PlaceableNetData>(e);
                    if ((placeable.m_PlacementFlags & (Game.Net.PlacementFlags.IsUpgrade | Game.Net.PlacementFlags.UpgradeOnly)) != 0) continue;
                    var info = NetPrefabOf(e);
                    if (info.Kind == null || info.Kind == "path") continue;
                    var item = CatalogueItem(e, info.Kind, achieved);
                    item["costPerKm"] = (long)placeable.m_DefaultConstructionCost * 125;
                    item["upkeepPerKm"] = Math.Round(placeable.m_DefaultUpkeepCost * 125.0);
                    if (_prefabLanes.TryGetValue(e, out var lanes)) item["lanes"] = new JArray(lanes.x, lanes.y);
                    items.Add(item);
                }
            }
            using (var stamps = _q.Stamps.ToEntityArray(Allocator.Temp))
            {
                foreach (var e in stamps)
                {
                    var item = CatalogueItem(e, "junction", achieved);
                    item["upkeep"] = _em.GetComponentData<AssetStampData>(e).m_UpKeepCost;
                    items.Add(item);
                }
            }
            Snap.Section("catalogue", new JObject { ["milestone"] = achieved, ["items"] = items });
            return true;
        }

        private JObject CatalogueItem(Entity e, string kind, int achieved)
        {
            var name = PrefabName(e);
            var o = new JObject
            {
                ["prefab"] = name,
                ["title"] = Loc($"Assets.NAME[{name}]") ?? name,
                ["kind"] = kind,
                ["unlocked"] = !Enabled<Locked>(e),
            };
            try
            {
                var milestone = Game.UI.InGame.ProgressionUtils.GetRequiredMilestone(_em, e);
                if (milestone > 0) o["milestone"] = milestone;
            }
            catch (Exception)
            {
            }
            if (TryGet<UIObjectData>(e, out var ui) && ui.m_Group != Entity.Null)
            {
                var group = PrefabName(ui.m_Group);
                o["menu"] = Loc($"SubServices.NAME[{group}]") ?? group;
            }
            return o;
        }

        // --- map tiles (owned or not) with their natural resources

        private bool MapTiles()
        {
            var tiles = new JArray();
            using (var ents = _q.AllTiles.ToEntityArray(Allocator.Temp))
            {
                foreach (var t in ents)
                {
                    var g = _em.GetComponentData<Game.Areas.Geometry>(t);
                    var o = new JObject
                    {
                        ["owned"] = !Has<Game.Common.Native>(t),
                        ["box"] = new JArray(CitySnapshot.R1(g.m_Bounds.min.x), CitySnapshot.R1(g.m_Bounds.max.x), CitySnapshot.R1(g.m_Bounds.min.z), CitySnapshot.R1(g.m_Bounds.max.z)),
                    };
                    if (_em.HasBuffer<Game.Areas.MapFeatureElement>(t))
                    {
                        var f = _em.GetBuffer<Game.Areas.MapFeatureElement>(t, true);
                        var res = new JObject();
                        for (var i = 0; i < f.Length; i++)
                            if (f[i].m_Amount > 0f) res[((Game.Areas.MapFeature)i).ToString()] = Math.Round(f[i].m_Amount, 1);
                        o["resources"] = res;
                    }
                    tiles.Add(o);
                }
            }
            var purchase = Sys<MapTilePurchaseSystem>();
            Snap.Section("mapTiles", new JObject { ["permitsLeft"] = purchase.GetAvailableTiles(), ["tiles"] = tiles });
            return true;
        }

        // --- land value and pollution, averaged down to 64 x 64 (224 m cells)

        private bool Grids()
        {
            var grids = new JObject { ["size"] = GridSize, ["cell"] = 2f * MapHalfSize / GridSize, ["origin"] = -MapHalfSize };
            var land = Sys<LandValueSystem>().GetMap(true, out var d1);
            d1.Complete();
            grids["landValue"] = Downsample(land.Length, i => land[i].m_LandValue);
            var ground = Sys<GroundPollutionSystem>().GetMap(true, out var d2);
            d2.Complete();
            grids["groundPollution"] = Downsample(ground.Length, i => ground[i].m_Pollution);
            var air = Sys<AirPollutionSystem>().GetMap(true, out var d3);
            d3.Complete();
            grids["airPollution"] = Downsample(air.Length, i => air[i].m_Pollution);
            var noise = Sys<NoisePollutionSystem>().GetMap(true, out var d4);
            d4.Complete();
            grids["noisePollution"] = Downsample(noise.Length, i => noise[i].m_Pollution);
            Snap.Section("grids", grids);
            return true;
        }

        /// <summary>A square map (row = z) averaged down to GridSize x GridSize, as base64 of 16-bit numbers.</summary>
        private static string Downsample(int length, Func<int, float> value)
        {
            var n = (int)math.round(math.sqrt(length));
            if (n < GridSize || n * n != length) return "";
            var k = n / GridSize;
            var sum = new double[GridSize * GridSize];
            for (var i = 0; i < length; i++)
            {
                var row = i / n / k;
                var col = i % n / k;
                if (row < GridSize && col < GridSize) sum[row * GridSize + col] += value(i);
            }
            var o = new ushort[GridSize * GridSize];
            for (var i = 0; i < o.Length; i++)
            {
                var v = sum[i] / (k * k);
                o[i] = v <= 0 || double.IsNaN(v) ? (ushort)0 : v >= ushort.MaxValue ? ushort.MaxValue : (ushort)Math.Round(v);
            }
            return CitySnapshot.Base64(o);
        }
    }
}
