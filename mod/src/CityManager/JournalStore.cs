// The journal files on disk: following the loaded city to its journal, re-reading journal.json when the manager
// changes it, and keeping the Mayor's file (mayor.json). Plain file code with no game types, so it can be unit-tested.
//
// Everything that arrives from the panel (or from another mod calling the same triggers) is treated as untrusted:
// journal folders must be plain names of existing journals, keys and text are checked, capped and cleaned, statuses
// come from a fixed set, and the files have size limits. Nothing here reads or writes outside Root, and messages show
// paths relative to it (players paste their logs into bug reports).
//
// Time stamps that get compared ("at", "changed") are UTC, "yyyy-MM-ddTHH:mm:ssZ", so they sort as strings.

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace CityManager
{
    public sealed class JournalStore
    {
        public const int Format = 1;
        /// <summary>The largest journal.json, mayor.json, picks.json or cities.json read, and the largest mayor.json written.</summary>
        public const long MaxFileBytes = 4 * 1024 * 1024;
        public const int MaxKey = 200, MaxNote = 2000, MaxAnswer = 4000, MaxNotes = 2000, MaxAnswers = 16;
        /// <summary>Pictures the panel may show: plain PNG names, at most this size each (each one becomes a texture in
        /// video memory; the panel also limits the pixels it draws per page).</summary>
        public const int MaxPictureWidth = 2048, MaxPictureHeight = 4096, MaxPictures = 200;
        public const long MaxPictureBytes = 16 * 1024 * 1024;
        /// <summary>Pictures are checked again every this many polls (the mod polls about once a second), besides whenever
        /// journal.json changes. A folder's change time isn't reliable on Windows, so this doesn't watch the images folder.</summary>
        public const int PictureRecheckPolls = 10;
        public static readonly string[] Statuses = { "active", "next", "idea", "hold", "done" };
        private static readonly Regex PictureName = new Regex(@"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.png$");
        private static readonly Regex DeviceName = new Regex(@"^(con|prn|aux|nul|com\d|lpt\d)$");   // reserved on Windows
        private const string NotRemembered = "Your choice of journal couldn't be saved, so next time this city opens its usual journal.";

        /// <summary>Where warnings and notes go (the mod's log in game; tests can listen).</summary>
        public static Action<string> Warn = _ => { }, Info = _ => { };

        public string Root { get; }
        /// <summary>The loaded city's name as last followed (null while no city is followed).</summary>
        public string City { get; private set; }
        /// <summary>The open journal's folder name, or null when the city has none yet.</summary>
        public string Folder { get; private set; }
        /// <summary>The last journal.json that parsed (minified), or "" when there is none.</summary>
        public string JournalText { get; private set; } = "";
        /// <summary>The journal's own "updated" stamp ("" when none): the panel's new-update dot compares it with "seen".</summary>
        public string Updated { get; private set; } = "";
        /// <summary>The journal's pictures that exist and are within the limits: name → [width, height], read from the files
        /// themselves (the sizes a journal declares are not trusted).</summary>
        public JObject Pictures { get; private set; } = new JObject();
        public JObject Mayor { get; private set; } = NewMayor();
        /// <summary>Why the journal can't be shown (or why the last update was skipped); "" when all is well.</summary>
        public string Error { get; private set; } = "";
        /// <summary>A problem with the Mayor's own file (not saved, damaged); "" when all is well. Shown in the panel.</summary>
        public string MayorProblem { get; private set; } = "";
        /// <summary>When journal.json last changed on disk (local time), for the panel's "updated" line.</summary>
        public DateTime JournalFileTime { get; private set; }

        private JObject _declared;   // the journal's "images": what it says it shows
        private DateTime _jStamp, _mStamp;
        private long _jLength = -1;
        private int _badReads, _badMayorReads, _noteCounter, _pollsSincePictures;

        public JournalStore(string root)
        {
            Root = Path.GetFullPath(root);
            Directory.CreateDirectory(Root);
            Layout = ReadLayout();
        }

        // --- Where the Mayor put the panel: layout.json, one entry per screen shape ("1.78" for 16:9, "1.33" for 4:3).

        public const string LayoutFile = "layout.json";
        public const int MaxLayouts = 12, MaxLayoutChars = 16 * 1024;
        private static readonly System.Text.RegularExpressions.Regex ScreenShape = new System.Text.RegularExpressions.Regex(@"^\d{1,2}\.\d{2}$");

        /// <summary>The panel's saved places, already checked (empty when there are none).</summary>
        public JObject Layout { get; private set; }

        private JObject ReadLayout()
        {
            try
            {
                var fi = new FileInfo(Path.Combine(Root, LayoutFile));
                return fi.Exists && fi.Length <= MaxLayoutChars ? CleanLayout(ReadJson(fi)) : new JObject();
            }
            catch (Exception)
            {
                return new JObject();   // a damaged file just means the default place
            }
        }

        /// <summary>Only screen-shape keys, each with a mode and four finite numbers in a sane range; anything else is
        /// dropped. The panel's own trigger sends this, but any mod can call it.</summary>
        public static JObject CleanLayout(JObject input)
        {
            var o = new JObject();
            if (input == null) return o;
            foreach (var p in input.Properties())
            {
                if (o.Count >= MaxLayouts) break;
                if (!ScreenShape.IsMatch(p.Name) || !(p.Value is JObject v)) continue;
                var entry = new JObject { ["mode"] = (string)v["mode"] == "floating" ? "floating" : "docked" };
                foreach (var k in new[] { "x", "y", "w", "bodyH" })
                {
                    var t = v[k];
                    if (t == null || (t.Type != JTokenType.Integer && t.Type != JTokenType.Float)) continue;
                    var d = (double)t;
                    if (double.IsNaN(d) || double.IsInfinity(d)) continue;
                    entry[k] = Math.Round(Math.Max(-20000, Math.Min(20000, d)), 1);
                }
                o[p.Name] = entry;
            }
            return o;
        }

        /// <summary>The panel's trigger: saves the Mayor's layouts (checked) to layout.json.</summary>
        public void SaveLayout(string json)
        {
            if (string.IsNullOrEmpty(json) || json.Length > MaxLayoutChars) return;
            try
            {
                var clean = CleanLayout(Parse(json));
                WriteText(Path.Combine(Root, LayoutFile), clean.ToString(Formatting.Indented));
                Layout = clean;
            }
            catch (Exception e)
            {
                Warning("layout.json can't be written: " + e.Message);
            }
        }

        private string Dir => Path.Combine(Root, Folder);
        private string JournalPath => Path.Combine(Dir, "journal.json");
        private string MayorPath => Path.Combine(Dir, "mayor.json");
        private string ImagesDir => Path.Combine(Dir, "images");

        /// <summary>The journals' folder under ModsData. Before 0.5 the mod was called City Journal: the first time, its
        /// folder moves here, unless a CityManager folder exists already (then the old one is left alone).</summary>
        public static string JournalsFolder(string modsData)
        {
            string root = Path.Combine(modsData, "CityManager"), old = Path.Combine(modsData, "CityJournal");
            if (!Directory.Exists(old) || Directory.Exists(root)) return root;
            try
            {
                Directory.Move(old, root);
                Info("Moved the journals from ModsData/CityJournal to ModsData/CityManager");
                return root;
            }
            catch (Exception e)
            {
                Warn("Couldn't move ModsData/CityJournal to ModsData/CityManager, so it is used as it is: " + e.Message.Replace(modsData, "ModsData"));
                return old;
            }
        }

        public static string Stamp() => DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'", CultureInfo.InvariantCulture);

        public static string Slug(string name)
        {
            var sb = new StringBuilder();
            foreach (var ch in (name ?? "").Trim().ToLowerInvariant())
                sb.Append(char.IsLetterOrDigit(ch) ? ch : '-');
            var s = sb.ToString();
            while (s.Contains("--")) s = s.Replace("--", "-");
            return s.Trim('-');
        }

        // ---- Which journal: following the city ----

        /// <summary>Follows the loaded city's name (called about once a second). A new name in the same city is a rename:
        /// the open journal stays, and is remembered under the new name too. Call Forget() when another city starts
        /// loading, so its name is never taken for a rename. True when the panel needs a refresh.</summary>
        public bool Follow(string cityName)
        {
            cityName = cityName ?? "";
            if (cityName == City)
            {
                if (Folder != null) return Poll();
                var found = Resolve(cityName);   // a journal may have appeared since (the manager's first build)
                if (found != null) Open(found);
                return true;                     // also refreshes the list of journals the panel offers
            }
            var renamed = City != null && Folder != null;
            City = cityName;
            if (renamed)
            {
                if (!SavePick(cityName, Folder)) Error = NotRemembered;
                Info($"City renamed to \"{Clean(cityName, 80)}\": journal {Folder} kept");
            }
            else
            {
                Open(Resolve(cityName));
                Info($"City \"{Clean(cityName, 80)}\": journal {Folder ?? "(none yet)"}");
            }
            return true;
        }

        /// <summary>Another city is loading: close the journal and forget the old city's name.</summary>
        public void Forget()
        {
            City = null;
            Open(null);
        }

        /// <summary>Journal folders that hold a journal.json, by name.</summary>
        public List<string> Available()
        {
            try
            {
                return Directory.GetDirectories(Root).Where(d => File.Exists(Path.Combine(d, "journal.json")))
                    .Select(Path.GetFileName).OrderBy(x => x, StringComparer.OrdinalIgnoreCase).ToList();
            }
            catch (Exception)
            {
                return new List<string>();
            }
        }

        private static bool PlainName(string folder) =>
            !string.IsNullOrWhiteSpace(folder) && folder.Length <= MaxKey && folder.IndexOfAny(new[] { '/', '\\', ':' }) < 0 && folder.Trim('.').Length > 0;

        /// <summary>The existing journal folder with this name (case-insensitive), or null. Never a path.</summary>
        public string Existing(string folder) =>
            PlainName(folder) ? Available().FirstOrDefault(a => string.Equals(a, folder, StringComparison.OrdinalIgnoreCase)) : null;

        /// <summary>The journal folder for a city name: the Mayor's pick, then the manager's aliases, then the city's own name.</summary>
        public string Resolve(string cityName)
        {
            if (string.IsNullOrWhiteSpace(cityName)) return null;
            return Existing(ReadMap("picks.json", "picks", cityName)) ?? Existing(ReadMap("cities.json", "aliases", cityName)) ?? Existing(Slug(cityName));
        }

        private string ReadMap(string file, string key, string cityName)
        {
            try
            {
                var fi = new FileInfo(Path.Combine(Root, file));
                if (!fi.Exists || !(ReadJson(fi)[key] is JObject map)) return null;
                foreach (var p in map.Properties())
                    if (SameCity(p.Name, cityName))
                        return p.Value.Type == JTokenType.String ? (string)p.Value : null;
            }
            catch (Exception e)
            {
                Warning($"{file} can't be read: {e.Message}");
            }
            return null;
        }

        private static bool SameCity(string a, string b) => string.Equals(a.Trim(), b.Trim(), StringComparison.OrdinalIgnoreCase);

        /// <summary>Remembers (folder) or forgets (null) the Mayor's own pick for a city in picks.json. False if folder
        /// isn't a journal or picks.json can't be written.</summary>
        public bool SavePick(string cityName, string folder)
        {
            var existing = folder == null ? null : Existing(folder);
            if ((folder != null && existing == null) || string.IsNullOrWhiteSpace(cityName)) return false;
            try
            {
                var fi = new FileInfo(Path.Combine(Root, "picks.json"));
                JObject o;
                try { o = fi.Exists ? ReadJson(fi) : new JObject(); }
                catch (Exception) { o = new JObject(); }   // a damaged picks.json is replaced
                if (!(o["picks"] is JObject picks)) o["picks"] = picks = new JObject();
                foreach (var p in picks.Properties().Where(p => SameCity(p.Name, cityName)).ToList())
                    p.Remove();
                if (existing != null) picks[Clean(cityName, MaxKey)] = existing;
                WriteText(fi.FullName, o.ToString(Formatting.Indented));
                return true;
            }
            catch (Exception e)
            {
                Warning("picks.json can't be written: " + e.Message);
                return false;
            }
        }

        /// <summary>The Mayor picks a journal for the city (null goes back to the automatic choice), and it opens.</summary>
        public void Pick(string folder)
        {
            var existing = folder == null ? null : Existing(folder);
            if (folder != null && existing == null)
            {
                Warning($"Not a journal folder: \"{Clean(folder, 80)}\"");
                return;
            }
            var saved = SavePick(City, existing);
            Open(existing ?? Resolve(City));
            if (!saved) Error = NotRemembered;
        }

        /// <summary>Starts an empty journal for the city (so Notes and Wrap-up work without a manager) and opens it.</summary>
        public void Start()
        {
            var folder = Create(City);
            if (folder != null) Pick(folder);
        }

        /// <summary>Makes an empty journal folder for a city name, or finds the one it already has. Returns its folder.</summary>
        public string Create(string cityName)
        {
            var name = Clean(cityName, 80);
            var slug = Slug(name);
            if (slug == "" || !PlainName(slug)) slug = "my-city";
            if (DeviceName.IsMatch(slug)) slug += "-city";
            if (Existing(slug) != null) return slug;
            try
            {
                Directory.CreateDirectory(Path.Combine(Root, slug));
                var journal = new JObject
                {
                    ["format"] = Format, ["city"] = name, ["manager"] = "", ["updated"] = "",
                    ["projects"] = new JArray(), ["reports"] = new JArray(), ["briefings"] = new JArray(), ["replies"] = new JObject(), ["images"] = new JObject(),
                };
                WriteText(Path.Combine(Root, slug, "journal.json"), journal.ToString(Formatting.Indented));
                return slug;
            }
            catch (Exception e)
            {
                Warning("Couldn't start a journal: " + e.Message);
                return null;
            }
        }

        // ---- The manager's side (journal.json) ----

        /// <summary>Opens a journal by folder name (null closes it). Anything that isn't an existing journal opens nothing.</summary>
        public void Open(string folder)
        {
            Folder = folder == null ? null : Existing(folder);
            if (folder != null && Folder == null) Warning($"Not a journal folder: \"{Clean(folder, 80)}\"");
            JournalText = Updated = Error = MayorProblem = "";
            Pictures = new JObject();
            _declared = null;
            _jStamp = _mStamp = default;
            _jLength = -1;
            _badReads = _badMayorReads = 0;
            Mayor = NewMayor();
            if (Folder == null) return;
            LoadMayor();
            Poll();
        }

        /// <summary>Re-reads what changed on disk. True when the panel needs a refresh.</summary>
        public bool Poll()
        {
            if (Folder == null) return false;
            var changed = false;
            try
            {
                var fi = new FileInfo(JournalPath);
                if (!fi.Exists)
                {
                    _jStamp = default;   // a copy put back later (even with its old time stamp) is read again
                    _jLength = -1;
                    if (JournalText != "" || Error == "")
                    {
                        JournalText = Updated = "";
                        _declared = null;
                        Pictures = new JObject();
                        Error = "This journal has no journal.json yet.";
                        changed = true;
                    }
                }
                else if (fi.LastWriteTimeUtc != _jStamp || fi.Length != _jLength)
                {
                    changed = ReadJournal(fi);
                }
                else if (++_pollsSincePictures >= PictureRecheckPolls)
                {
                    changed = CheckPictures();
                }
                var mi = new FileInfo(MayorPath);
                if (mi.Exists && mi.LastWriteTimeUtc != _mStamp)
                {
                    LoadMayor(patient: true);
                    changed = true;
                }
            }
            catch (Exception e)
            {
                Warning("Journal poll failed: " + e.Message);
            }
            return changed;
        }

        private bool ReadJournal(FileInfo fi)
        {
            var lastGood = JournalText != "" ? " Showing the last good copy." : "";
            if (fi.Length > MaxFileBytes)
            {
                Seen(fi);
                Error = $"journal.json is too large ({fi.Length / 1024} KB; the limit is {MaxFileBytes / 1024} KB).{lastGood}";
                return true;
            }
            try
            {
                var o = Parse(File.ReadAllText(fi.FullName));
                var format = FormatOf(o["format"]);
                JournalText = o.ToString(Formatting.None);
                Updated = o["updated"]?.Type == JTokenType.String ? Clean((string)o["updated"], 40) : "";
                _declared = o["images"] as JObject;
                CheckPictures();
                JournalFileTime = fi.LastWriteTime;
                Error = format > Format ? $"This journal was written for a newer City Manager (format {format}); some of it may not show." : "";
                _badReads = 0;
                Seen(fi);
                return true;
            }
            catch (Exception e)
            {
                if (++_badReads < 4) return false;   // the manager may be half-way through writing it: try the next polls first
                Seen(fi);
                Error = $"The City Manager's latest update can't be read ({Scrub(e.Message)}).{lastGood}";
                Warning($"{Folder}/journal.json: {e.Message}");
                return true;
            }
        }

        private void Seen(FileInfo fi)
        {
            _jStamp = fi.LastWriteTimeUtc;
            _jLength = fi.Length;
        }

        /// <summary>Which of the journal's pictures may be shown, with their real sizes from the PNG header. Checked again
        /// whenever journal.json changes, and every PictureRecheckPolls polls. True when the answer changed.</summary>
        private bool CheckPictures()
        {
            _pollsSincePictures = 0;
            var ok = new JObject();
            foreach (var p in (_declared?.Properties() ?? Enumerable.Empty<JProperty>()).Take(MaxPictures))
            {
                if (!PictureName.IsMatch(p.Name)) continue;
                var file = new FileInfo(Path.Combine(ImagesDir, p.Name));
                var size = file.Exists && file.Length <= MaxPictureBytes ? PngSize(file.FullName) : null;
                if (size is (int w, int h) && w <= MaxPictureWidth && h <= MaxPictureHeight) ok[p.Name] = new JArray(w, h);
                else if (file.Exists) Warning($"Picture {p.Name} is not shown: not a PNG within {MaxPictureWidth}x{MaxPictureHeight} pixels and {MaxPictureBytes / 1024 / 1024} MB");
            }
            var changed = !JToken.DeepEquals(ok, Pictures);
            Pictures = ok;
            return changed;
        }

        /// <summary>Width and height from a PNG file's header, or null if it isn't a readable PNG.</summary>
        public static (int, int)? PngSize(string path)
        {
            try
            {
                var b = new byte[24];
                using (var f = File.OpenRead(path))
                    if (f.Read(b, 0, 24) != 24) return null;
                byte[] sig = { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A };
                if (!sig.SequenceEqual(b.Take(8)) || Encoding.ASCII.GetString(b, 12, 4) != "IHDR") return null;
                int Be(int i) => (b[i] << 24) | (b[i + 1] << 16) | (b[i + 2] << 8) | b[i + 3];
                int w = Be(16), h = Be(20);
                return w > 0 && h > 0 ? (w, h) : ((int, int)?)null;
            }
            catch (Exception)
            {
                return null;
            }
        }

        // ---- The Mayor's side (mayor.json) ----

        private static JObject NewMayor() => new JObject
        {
            ["format"] = Format,
            ["ticks"] = new JObject(),
            ["status"] = new JObject(),
            ["notes"] = new JArray(),
            ["debriefs"] = new JObject(),
            ["seen"] = "",
        };

        /// <summary>Reads mayor.json, or its backup if it's damaged. Patient: a file that can't be read gets a few more
        /// polls first, since someone may be half-way through writing it.</summary>
        private void LoadMayor(bool patient = false)
        {
            var main = new FileInfo(MayorPath);
            foreach (var fi in new[] { main, new FileInfo(MayorPath + ".bak") })
            {
                if (!fi.Exists) continue;
                try
                {
                    var o = ReadJson(fi);
                    foreach (var p in NewMayor().Properties())
                        if (o[p.Name] == null || o[p.Name].Type != p.Value.Type) o[p.Name] = p.Value;
                    Mayor = o;
                    _mStamp = main.Exists ? main.LastWriteTimeUtc : default;
                    _badMayorReads = 0;
                    MayorProblem = fi == main ? "" : "Your journal file was damaged; the copy from your previous change was restored.";
                    if (fi != main) Warning("mayor.json was damaged; restored the backup copy");
                    return;
                }
                catch (Exception e)
                {
                    if (fi == main && patient && ++_badMayorReads < 4) return;
                    Warning($"{fi.Name} can't be read ({e.Message})");
                    // Keep the damaged file for the manager to look at, then try the backup.
                    if (fi == main)
                        try { File.Copy(fi.FullName, Path.Combine(Dir, "mayor.broken-" + DateTime.UtcNow.ToString("yyyyMMddHHmmss", CultureInfo.InvariantCulture) + ".json"), true); } catch (Exception) { }
                }
            }
            _mStamp = main.Exists ? main.LastWriteTimeUtc : default;   // don't re-read this same file on every poll
            _badMayorReads = 0;
            if (main.Exists) MayorProblem = "Your journal file was damaged and no backup could be read; it was set aside as mayor.broken-<time>.json.";
            Mayor = NewMayor();
        }

        /// <summary>Before a change: true if a journal is open, after picking up any edit made to mayor.json since the last
        /// poll (so the change doesn't overwrite it).</summary>
        private bool Ready()
        {
            if (Folder == null) return false;
            var mi = new FileInfo(MayorPath);
            if (mi.Exists && mi.LastWriteTimeUtc != _mStamp) LoadMayor(patient: true);
            return true;
        }

        private void SaveMayor()
        {
            try
            {
                Mayor["format"] = Math.Max(FormatOf(Mayor["format"]), Format);   // never lowered
                Mayor["journal"] = Folder;
                Mayor["saved"] = Stamp();
                var text = Mayor.ToString(Formatting.Indented);
                if (Encoding.UTF8.GetByteCount(text) > MaxFileBytes)
                {
                    LoadMayor();   // back to what's on disk
                    MayorProblem = $"Not saved: your journal file is full ({MaxFileBytes / 1024 / 1024} MB). Delete some old notes to make room.";
                    Warning("mayor.json would be over the size limit; change not saved");
                    return;
                }
                if (File.Exists(MayorPath)) File.Copy(MayorPath, MayorPath + ".bak", true);
                WriteText(MayorPath, text);
                _mStamp = new FileInfo(MayorPath).LastWriteTimeUtc;
                MayorProblem = "";
            }
            catch (Exception e)
            {
                MayorProblem = $"Not saved: your last change couldn't be written to disk ({Scrub(e.Message)}).";
                Warning("mayor.json can't be written: " + e.Message);
            }
        }

        /// <summary>A key or id from the panel, unchanged, or null if it's empty or isn't clean as it is (too long, odd
        /// characters): a changed key would never match the panel's own lookups.</summary>
        private string Key(string key)
        {
            if (string.IsNullOrEmpty(key)) return null;
            if (key.Length <= MaxKey && Clean(key, MaxKey) == key) return key;
            MayorProblem = "Not saved: an item in this journal has an id that is too long or has odd characters. Ask the City Manager to fix it.";
            Warning($"Key refused: \"{Clean(key, 80)}\"");
            return null;
        }

        private static JObject Stamped(JObject o, string gameDate)
        {
            o["at"] = Stamp();
            o["gameDate"] = Clean(gameDate, 40);
            return o;
        }

        public void SetTick(string key, bool done, string gameDate)
        {
            if (!Ready() || (key = Key(key)) == null) return;
            ((JObject)Mayor["ticks"])[key] = Stamped(new JObject { ["done"] = done }, gameDate);
            SaveMayor();
        }

        /// <summary>The Mayor's own status for a project; "" clears it (the manager's status shows again).</summary>
        public void SetStatus(string projectId, string status, string gameDate)
        {
            if (!(string.IsNullOrEmpty(status) || Statuses.Contains(status)) || !Ready() || (projectId = Key(projectId)) == null) return;
            var s = (JObject)Mayor["status"];
            if (string.IsNullOrEmpty(status)) s.Remove(projectId);
            else s[projectId] = Stamped(new JObject { ["status"] = status }, gameDate);
            SaveMayor();
        }

        public void AddNote(string projectId, string text, float[] where, string gameDate)
        {
            text = Clean(text, MaxNote);
            if (text == "" || !Ready()) return;
            var notes = (JArray)Mayor["notes"];
            if (notes.Count >= MaxNotes)
            {
                MayorProblem = $"Not saved: this journal already has {MaxNotes} notes. Delete some old ones to make room.";
                Warning($"Note not saved: this journal already has {MaxNotes} notes");
                return;
            }
            var note = Stamped(new JObject { ["id"] = "n" + DateTime.UtcNow.ToString("yyyyMMddHHmmss", CultureInfo.InvariantCulture) + "-" + (++_noteCounter) }, gameDate);
            note["project"] = Clean(projectId, MaxKey);   // a note is never lost over an odd project id
            note["text"] = text;
            if (where != null && where.Length == 3 && where.All(v => !float.IsNaN(v) && !float.IsInfinity(v)))
                note["where"] = new JObject { ["x"] = Math.Round(where[0], 1), ["z"] = Math.Round(where[1], 1), ["zoom"] = Math.Round(where[2]) };
            notes.Add(note);
            SaveMayor();
        }

        public void DeleteNote(string id)
        {
            if (!Ready()) return;
            var notes = (JArray)Mayor["notes"];
            var hit = notes.OfType<JObject>().FirstOrDefault(n => n["id"]?.Type == JTokenType.String && (string)n["id"] == id);
            if (hit == null) return;
            notes.Remove(hit);
            SaveMayor();
        }

        /// <summary>The Mayor's wrap-up for a briefing: answers as a JSON object of strings (question id → text).</summary>
        public void SaveDebrief(string briefingId, string answersJson, string gameDate)
        {
            if (!Ready() || (briefingId = Key(briefingId)) == null) return;
            if ((answersJson ?? "").Length > MaxAnswers * (MaxAnswer + 100))
            {
                MayorProblem = "Not saved: the wrap-up is too long.";
                return;
            }
            JObject raw;
            try { raw = Parse(answersJson ?? "{}"); }
            catch (Exception) { return; }
            var answers = new JObject();
            foreach (var p in raw.Properties().Take(MaxAnswers))
                answers[Clean(p.Name, 40)] = p.Value.Type == JTokenType.String ? Clean((string)p.Value, MaxAnswer) : "";
            Stamped(Debrief(briefingId), gameDate)["answers"] = answers;
            SaveMayor();
        }

        public void FinishDebrief(string briefingId, bool done, string gameDate)
        {
            if (!Ready() || (briefingId = Key(briefingId)) == null) return;
            Stamped(Debrief(briefingId), gameDate)["done"] = done;
            SaveMayor();
        }

        private JObject Debrief(string briefingId)
        {
            var all = (JObject)Mayor["debriefs"];
            if (!(all[briefingId] is JObject d)) all[briefingId] = d = new JObject { ["answers"] = new JObject(), ["done"] = false };
            return d;
        }

        public void MarkSeen(string stamp)
        {
            stamp = Clean(stamp, 40);
            if (!Ready() || (string)Mayor["seen"] == stamp) return;
            Mayor["seen"] = stamp;
            SaveMayor();
        }

        // ---- Files and text ----

        /// <summary>JSON with a nesting limit (Json.NET's default is 64; journals need far less), and every value kept as
        /// written: by default Json.NET turns date-like strings into dates and writes them back differently, which would
        /// break the string comparisons of the "at" and "changed" stamps.</summary>
        private static JObject Parse(string text)
        {
            using (var reader = new JsonTextReader(new StringReader(text)) { MaxDepth = 32, DateParseHandling = DateParseHandling.None, FloatParseHandling = FloatParseHandling.Double })
                return JObject.Load(reader);
        }

        private static JObject ReadJson(FileInfo fi)
        {
            if (fi.Length > MaxFileBytes) throw new InvalidDataException($"over {MaxFileBytes / 1024 / 1024} MB");
            return Parse(File.ReadAllText(fi.FullName));
        }

        /// <summary>A file's "format" number. Odd or huge values are clamped, so a hand-edited file can't break saving.</summary>
        private static int FormatOf(JToken t)
        {
            if (t?.Type != JTokenType.Integer) return Format;
            try { return (int)Math.Max(int.MinValue, Math.Min(int.MaxValue, (double)t)); }
            catch (Exception) { return int.MaxValue; }
        }

        /// <summary>Writes a file so that a crash leaves the old or the new version, never half of one.</summary>
        internal static void WriteText(string path, string text)
        {
            var tmp = path + ".tmp";
            var bytes = new UTF8Encoding(false).GetBytes(text);
            using (var f = new FileStream(tmp, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                f.Write(bytes, 0, bytes.Length);
                f.Flush(true);   // on the disk before it replaces the old version
            }
            if (!File.Exists(path))
            {
                File.Move(tmp, path);
                return;
            }
            try
            {
                File.Replace(tmp, path, null);
                return;
            }
            // Windows refuses to replace a file another program has open without sharing deletion (antivirus, cloud
            // sync, an editor); some file systems can't replace atomically. Copy over it instead, if that's allowed.
            catch (Exception e) when (e is IOException || e is UnauthorizedAccessException || e is PlatformNotSupportedException) { }
            try
            {
                File.Copy(tmp, path, true);   // mayor.json's backup covers this moment
            }
            finally
            {
                File.Delete(tmp);   // no leftover, whether the copy worked or not
            }
        }

        /// <summary>Trimmed, without control characters (new lines kept), at most max characters, never half a character.</summary>
        public static string Clean(string s, int max)
        {
            if (string.IsNullOrEmpty(s)) return "";
            var sb = new StringBuilder(Math.Min(s.Length, max));
            foreach (var ch in s.Trim())
            {
                if (sb.Length >= max) break;
                if (ch == '\n' || !char.IsControl(ch)) sb.Append(ch);
            }
            if (sb.Length > 0 && char.IsHighSurrogate(sb[sb.Length - 1])) sb.Length--;
            return sb.ToString().TrimEnd();
        }

        /// <summary>A message without the user-data path (it holds the player's user name on Windows).</summary>
        public string Scrub(string s) => (s ?? "").Replace(Root, "CityManager").Replace(Root.Replace('\\', '/'), "CityManager");

        private void Warning(string s) => Warn(Scrub(s));
    }
}
