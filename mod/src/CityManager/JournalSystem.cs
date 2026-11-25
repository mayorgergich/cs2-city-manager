// Bindings for the journal panel (ui/CityManager.mjs, group "cityManager"). The journal and the Mayor's file go to
// the panel as JSON strings, pushed only when they changed (ValueBinding skips equal values); the panel merges them.
// Triggers record the Mayor's ticks, statuses, notes and wrap-up, pick or start a journal, and move the camera.
// Any mod in the same UI view can call these triggers, so every argument is checked again in JournalStore.
// It also takes the city snapshot (city.json beside mayor.json): after every save the game makes, on Done for today
// and from the City tab's button. CityReader reads the city one part per frame; the JSON is written off the main thread.

using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Threading.Tasks;
using Colossal.Serialization.Entities;
using Colossal.UI;
using Colossal.UI.Binding;
using Game;
using Game.City;
using Game.Rendering;
using Game.SceneFlow;
using Game.Simulation;
using Game.UI;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Unity.Entities;
using Unity.Mathematics;
using UnityEngine;
using UnityEngine.Scripting;

namespace CityManager
{
    public sealed class JournalSystem : UISystemBase
    {
        public const string Group = "cityManager";
        public const string Host = "citymanager";
        private const float PollSeconds = 1f;

        private JournalStore _store;
        private CityConfigurationSystem _city;
        private TimeSystem _time;
        private CameraUpdateSystem _camera;
        private TerrainSystem _terrain;
        private ValueBinding<bool> _open, _fresh;
        private ValueBinding<string> _journal, _mayor, _info;
        private string _sessionStart = "";
        private float _nextPoll;
        private bool _inCity;

        // The city snapshot: a request waits for the next frame, CityReader reads one part per frame, then a task writes it.
        private CityReader.Queries _queries;
        private ComponentLookup<Game.Prefabs.Locked> _locked;
        private CityReader _reader;
        private Task<int> _writing;
        private CityReader _written;
        private Stopwatch _writeClock;
        private string _snapWhy, _snapSave, _snapProblem = "";
        private volatile string _savedAs;   // set by the game's save event, which may come from another thread

        // The session's start snapshot (city-start.json), taken a few seconds after the city loads, and what changed since.
        private const float StartDelaySeconds = 5f;
        private float _loadedAt;
        private string _startFolder;          // the journal the start snapshot was taken for this session
        private CitySnapshot _startSnap;
        private string _startDir;
        private CitySnapshot.Changes _changes;
        private string _changesAsOf = "";

        [Preserve]
        protected override void OnCreate()
        {
            base.OnCreate();
            _store = new JournalStore(JournalStore.JournalsFolder(Path.Combine(Application.persistentDataPath, "ModsData")));
            _city = World.GetOrCreateSystemManaged<CityConfigurationSystem>();
            _time = World.GetOrCreateSystemManaged<TimeSystem>();
            _camera = World.GetOrCreateSystemManaged<CameraUpdateSystem>();
            _terrain = World.GetOrCreateSystemManaged<TerrainSystem>();
            try
            {
                // Pictures: coui://citymanager/<journal>/images/<file>. No file watching: journal.py gives every picture a
                // content-hashed name, so a changed picture is a new address and never comes from a cache.
                UIManager.defaultUISystem.AddHostLocation(Host, _store.Root, false);
            }
            catch (Exception e)
            {
                Mod.Log.Warn("Picture folder not registered: " + e.Message);
            }

            AddBinding(_open = new ValueBinding<bool>(Group, "open", false));
            AddBinding(_fresh = new ValueBinding<bool>(Group, "fresh", false));
            AddBinding(_journal = new ValueBinding<string>(Group, "journal", ""));
            AddBinding(_mayor = new ValueBinding<string>(Group, "mayor", "{}"));
            AddBinding(_info = new ValueBinding<string>(Group, "info", "{}"));
            AddBinding(new TriggerBinding(Group, "toggle", () => _open.Update(!_open.value)));
            AddBinding(new TriggerBinding(Group, "close", () => _open.Update(false)));
            AddBinding(new TriggerBinding<string, bool>(Group, "tick", (key, done) => Do(() => _store.SetTick(key, done, GameDate()))));
            AddBinding(new TriggerBinding<string, string>(Group, "setStatus", (id, status) => Do(() => _store.SetStatus(id, status, GameDate()))));
            AddBinding(new TriggerBinding<string, string, bool>(Group, "addNote", (project, text, here) => Do(() => _store.AddNote(project, text, here ? CameraSpot() : null, GameDate()))));
            AddBinding(new TriggerBinding<string>(Group, "deleteNote", id => Do(() => _store.DeleteNote(id))));
            AddBinding(new TriggerBinding<string>(Group, "markSeen", stamp => Do(() => _store.MarkSeen(stamp))));
            AddBinding(new TriggerBinding<string, string>(Group, "saveDebrief", (id, answers) => Do(() => _store.SaveDebrief(id, answers, GameDate()))));
            AddBinding(new TriggerBinding<string, bool>(Group, "finishDebrief", (id, done) => Do(() =>
            {
                _store.FinishDebrief(id, done, GameDate());
                if (done) RequestSnapshot("done", null);
            })));
            AddBinding(new TriggerBinding(Group, "snapshot", () => Do(() => RequestSnapshot("button", null))));
            AddBinding(new TriggerBinding<float, float, float>(Group, "flyTo", FlyTo));
            AddBinding(new TriggerBinding<string>(Group, "pick", folder => Do(() => _store.Pick(folder))));
            AddBinding(new TriggerBinding(Group, "unpick", () => Do(() => _store.Pick(null))));
            AddBinding(new TriggerBinding(Group, "create", () => Do(_store.Start)));

            _queries = CityReader.Queries.Make(d => GetEntityQuery(d));
            _locked = GetComponentLookup<Game.Prefabs.Locked>(true);
            try
            {
                GameManager.instance.onGameSaveLoad += OnGameSaved;
            }
            catch (Exception e)
            {
                Mod.Log.Warn("Save event not available, so no snapshots on save: " + e.Message);
            }
        }

        [Preserve]
        protected override void OnDestroy()
        {
            try
            {
                if (GameManager.instance != null) GameManager.instance.onGameSaveLoad -= OnGameSaved;
            }
            catch (Exception)
            {
            }
            base.OnDestroy();
        }

        /// <summary>The game's save event: fires when a save starts and when it ends (autosaves too). Only notes the
        /// save's name; the snapshot is taken in OnUpdate, on the main thread.</summary>
        private void OnGameSaved(string saveName, string previewUri, bool start, bool success)
        {
            if (!start && success) _savedAs = saveName ?? "";
        }

        protected override void OnGamePreload(Purpose purpose, GameMode mode)
        {
            base.OnGamePreload(purpose, mode);
            // The game gives the world the next city's name while it loads, before OnGameLoadingComplete. Forget the old
            // city now, or that name change would look like the Mayor renaming the city.
            _store.Forget();
            _open.Update(false);
            _reader = null;              // a snapshot of the old city must not land in the next city's journal
            _snapWhy = null;
            _savedAs = null;
            _startFolder = null;
            _startSnap = null;
            _startDir = null;
            _changes = null;
            _changesAsOf = "";
            Push();
        }

        protected override void OnGameLoadingComplete(Purpose purpose, GameMode mode)
        {
            base.OnGameLoadingComplete(purpose, mode);
            _store.Forget();                        // and again, so nothing seen while loading carries over
            _sessionStart = JournalStore.Stamp();   // the Wrap-up tab lists what the Mayor did since then
            _loadedAt = UnityEngine.Time.realtimeSinceStartup;
            _open.Update(false);
        }

        [Preserve]
        protected override void OnUpdate()
        {
            base.OnUpdate();
            try
            {
                var inCity = GameManager.instance.gameMode == GameMode.Game && !GameManager.instance.isGameLoading;
                if (inCity != _inCity)
                {
                    _inCity = inCity;
                    if (!inCity) _open.Update(false);
                }
                if (!inCity) return;
                if (Mod.Toggle != null && Mod.Toggle.WasPerformedThisFrame()) _open.Update(!_open.value);
                SnapshotStep();
                if (UnityEngine.Time.realtimeSinceStartup < _nextPoll) return;
                _nextPoll = UnityEngine.Time.realtimeSinceStartup + PollSeconds;
                if (_store.Follow(_city.cityName)) Push();
            }
            catch (Exception e)
            {
                Mod.Log.Warn("Journal update failed: " + e.Message);
            }
        }

        private void Do(Action a)
        {
            try
            {
                a();
                Push();
            }
            catch (Exception e)
            {
                Mod.Log.Warn("Journal action failed: " + e.Message);
            }
        }

        // --- The city snapshot

        private bool SnapshotBusy => _reader != null || _writing != null || _snapWhy != null;

        private void RequestSnapshot(string why, string save)
        {
            if (_store.Folder == null)
            {
                if (why == "button") _snapProblem = "No journal is linked to this city, so there's nowhere to keep a snapshot.";
                return;
            }
            _snapWhy = why;
            _snapSave = save;
            _snapProblem = "";
        }

        /// <summary>One step per frame: start a requested snapshot, read the next part of the city, or finish writing.</summary>
        private void SnapshotStep()
        {
            var saved = _savedAs;
            if (saved != null)
            {
                _savedAs = null;
                RequestSnapshot("save", saved);
            }
            if (_writing != null)
            {
                if (_writing.IsCompleted) FinishWriting();
                return;
            }
            if (_reader != null)
            {
                try
                {
                    _locked.Update(this);
                    _reader.LockedLookup = _locked;
                    if (_reader.Step()) StartWriting();
                }
                catch (Exception e)
                {
                    _reader = null;
                    _snapProblem = "The snapshot failed: " + _store.Scrub(e.Message);
                    Mod.Log.Warn("Snapshot failed: " + _store.Scrub(e.ToString()));
                    Push();
                }
                return;
            }
            // The start snapshot comes first, a few seconds after the city loads (or when a journal gets linked later).
            var startDue = _store.Folder != null && _startFolder != _store.Folder
                && UnityEngine.Time.realtimeSinceStartup - _loadedAt >= StartDelaySeconds;
            if (_snapWhy == null && !startDue) return;
            if (_store.Folder == null)
            {
                _snapWhy = null;
                return;
            }
            var why = startDue ? "start" : _snapWhy;
            if (startDue) _startFolder = _store.Folder;
            else _snapWhy = null;
            var file = why == "start" ? CitySnapshot.StartFileName : CitySnapshot.FileName;
            _reader = new CityReader(World, _queries, Path.Combine(_store.Root, _store.Folder, file));
            var dir = Path.GetDirectoryName(_reader.Path);   // built the same way as in StartWriting, on every platform
            var snap = _reader.Snap;
            snap.Mod = Mod.InformationalVersion;
            snap.Taken = JournalStore.Stamp();
            snap.Why = why;
            snap.Save = why == "save" ? _snapSave ?? "" : "";
            // A session is one load of the city: later snapshots take the start snapshot's stamp (the game can report
            // "loading complete" more than once for one load, seen 24 Nov, which moves _sessionStart).
            snap.Session = why != "start" && _startSnap != null && _startDir == dir ? _startSnap.Session : _sessionStart;
            snap.Name = _city.cityName ?? "";
            FillDate(snap);
            Push();
        }

        private void StartWriting()
        {
            var reader = _reader;
            _reader = null;
            _written = reader;
            _writeClock = Stopwatch.StartNew();
            var dir = Path.GetDirectoryName(reader.Path);   // as SnapshotStep computes it, so the comparison holds
            if (reader.Snap.Why == "start")
            {
                _startSnap = reader.Snap;   // kept to compare later snapshots of this session with
                _startDir = dir;
            }
            var start = reader.Snap.Why != "start" && _startDir == dir ? _startSnap : null;
            _writing = Task.Run(() =>
            {
                if (start != null) reader.Snap.SessionChanges = CitySnapshot.Compare(start, reader.Snap);
                var json = reader.Snap.ToJson();
                JournalStore.WriteText(reader.Path, json);
                return json.Length;
            });
        }

        private void FinishWriting()
        {
            var task = _writing;
            var reader = _written;
            _writing = null;
            _written = null;
            if (task.IsFaulted || task.IsCanceled)
            {
                var e = task.Exception?.GetBaseException();
                _snapProblem = "The snapshot couldn't be saved: " + _store.Scrub(e?.Message ?? "cancelled");
                Mod.Log.Warn("Snapshot not saved: " + _store.Scrub(e?.ToString() ?? "cancelled"));
            }
            else
            {
                var s = reader.Snap;
                if (s.SessionChanges != null)
                {
                    _changes = s.SessionChanges;
                    _changesAsOf = DateTime.Now.ToString("HH:mm", CultureInfo.InvariantCulture);
                }
                Mod.Log.Info($"Snapshot ({s.Why}): {s.Edges.Count} edges, {s.Nodes.Count} nodes, {s.Buildings.Count} buildings, " +
                             $"{task.Result / 1024} KB; read in {reader.MainMs:F0} ms over {reader.Frames} frames (longest {reader.LongestMs:F0} ms, {reader.LongestPart}), " +
                             $"written in {_writeClock.ElapsedMilliseconds} ms" +
                             (s.Truncated.Count > 0 ? "; cut: " + string.Join(", ", s.Truncated) : ""));
            }
            Push();
        }

        private void FillDate(CitySnapshot snap)
        {
            try
            {
                var dt = _time.GetCurrentDateTime();
                snap.Year = dt.Year;
                snap.Month = dt.Day;   // the game's year has 12 days; day N shows as month N
                snap.Hour = dt.Hour;
                snap.Minute = dt.Minute;
                snap.DateText = GameDate();
            }
            catch (Exception)
            {
            }
        }

        /// <summary>What changed since the city loaded, for the Wrap-up tab (empty until a snapshot after the start one).</summary>
        private JObject SessionInfo()
        {
            var c = _changes;
            if (c == null) return new JObject();
            var o = new JObject { ["asOf"] = _changesAsOf, ["population"] = c.Population, ["money"] = c.Money, ["tiles"] = c.Tiles };
            if (c.RoadsKnown)
            {
                o["roadsAddedKm"] = Math.Round(c.RoadsAddedKm, 2);
                o["roadsRemovedKm"] = Math.Round(c.RoadsRemovedKm, 2);
                o["railAddedKm"] = Math.Round(c.RailAddedKm, 2);
                o["railRemovedKm"] = Math.Round(c.RailRemovedKm, 2);
            }
            if (c.BuildingsKnown)
            {
                o["grew"] = c.Grew;
                o["placed"] = c.Placed;
                o["removed"] = c.Removed;
            }
            return o;
        }

        private string SnapshotTime()
        {
            try
            {
                if (_store.Folder == null) return "";
                var path = Path.Combine(_store.Root, _store.Folder, CitySnapshot.FileName);
                return File.Exists(path) ? File.GetLastWriteTime(path).ToString("d MMM HH:mm", CultureInfo.InvariantCulture) : "";
            }
            catch (Exception)
            {
                return "";
            }
        }

        private void Push()
        {
            _journal.Update(_store.JournalText);
            _mayor.Update(_store.Mayor.ToString(Formatting.None));
            _fresh.Update(_store.Updated != "" && _store.Updated != (string)_store.Mayor["seen"]);
            _info.Update(new JObject
            {
                ["city"] = _store.City ?? "",
                ["folder"] = _store.Folder ?? "",
                ["journals"] = new JArray(_store.Available()),
                ["error"] = _store.Error,
                ["mayorProblem"] = _store.MayorProblem,
                ["pictures"] = _store.Pictures,
                ["fileTime"] = _store.Folder != null && _store.JournalText != "" ? _store.JournalFileTime.ToString("d MMM HH:mm", CultureInfo.InvariantCulture) : "",
                ["host"] = "coui://" + Host + "/",
                ["sessionStart"] = _sessionStart,
                ["snapshot"] = new JObject
                {
                    ["time"] = SnapshotTime(),
                    ["busy"] = SnapshotBusy,
                    ["problem"] = _snapProblem,
                },
                ["session"] = SessionInfo(),
            }.ToString(Formatting.None));
        }

        private string GameDate()
        {
            try
            {
                // The game's year has 12 days and its clock shows day N as month N ("June 2026" on day 6).
                var dt = _time.GetCurrentDateTime();
                var month = dt.Day >= 1 && dt.Day <= 12 ? CultureInfo.InvariantCulture.DateTimeFormat.GetMonthName(dt.Day) : dt.ToString("d MMM", CultureInfo.InvariantCulture);
                return $"{month} {dt.Year}, {dt.ToString("HH:mm", CultureInfo.InvariantCulture)}";
            }
            catch (Exception)
            {
                return "";
            }
        }

        /// <summary>Where the camera looks now: x, z and zoom (for "pin to this view").</summary>
        private float[] CameraSpot()
        {
            var c = _camera.gamePlayController;
            return c == null ? null : new[] { c.pivot.x, c.pivot.z, c.zoom };
        }

        private void FlyTo(float x, float z, float zoom)
        {
            // The playable map is 14,336 m across, centred on 0; ignore anything else (another mod could call this trigger).
            const float limit = 8000f;
            if (float.IsNaN(x) || float.IsNaN(z) || float.IsNaN(zoom) || Math.Abs(x) > limit || Math.Abs(z) > limit) return;
            try
            {
                var c = _camera.gamePlayController;
                if (c == null) return;
                var heights = _terrain.GetHeightData();
                c.pivot = new Vector3(x, TerrainUtils.SampleHeight(ref heights, new float3(x, 0f, z)), z);
                if (zoom > 0f && !float.IsInfinity(zoom)) c.zoom = math.clamp(zoom, 10f, 10000f);
            }
            catch (Exception e)
            {
                Mod.Log.Warn("Camera move failed: " + e.Message);
            }
        }
    }
}
