using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using CityManager;
using Newtonsoft.Json.Linq;
using Xunit;

// JournalStore.Warn is one static hook: run the tests one at a time so each sees only its own warnings.
[assembly: CollectionBehavior(DisableTestParallelization = true)]

namespace CityManager.Tests
{
    /// <summary>A throwaway ModsData/CityManager folder per test.</summary>
    public sealed class Sandbox : IDisposable
    {
        public readonly string Parent, Root;
        public readonly List<string> Warnings = new List<string>();

        public Sandbox()
        {
            Parent = Path.Combine(Path.GetTempPath(), "cj-test-" + Guid.NewGuid().ToString("N"));
            Root = Path.Combine(Parent, "CityManager");
            Directory.CreateDirectory(Root);
            JournalStore.Warn = Warnings.Add;
        }

        public string Journal(string folder, string json = "{\"format\":1,\"city\":\"Test\"}")
        {
            var dir = Path.Combine(Root, folder);
            Directory.CreateDirectory(dir);
            File.WriteAllText(Path.Combine(dir, "journal.json"), json);
            return dir;
        }

        public JObject Mayor(string folder)
        {
            using var reader = new Newtonsoft.Json.JsonTextReader(new StringReader(File.ReadAllText(Path.Combine(Root, folder, "mayor.json"))))
                { DateParseHandling = Newtonsoft.Json.DateParseHandling.None };
            return JObject.Load(reader);
        }

        public void Dispose()
        {
            JournalStore.Warn = _ => { };
            try { Directory.Delete(Parent, true); } catch (Exception) { }
        }
    }

    public class FolderSafety
    {
        [Theory]
        [InlineData("..")]
        [InlineData("../outside")]
        [InlineData("riverton/../../outside")]
        [InlineData("a\\b")]
        [InlineData("C:")]
        [InlineData("...")]
        [InlineData("")]
        [InlineData("  ")]
        [InlineData(null)]
        public void Existing_rejects_anything_but_a_plain_journal_name(string name)
        {
            using var s = new Sandbox();
            s.Journal("riverton");
            Directory.CreateDirectory(Path.Combine(s.Parent, "outside"));
            File.WriteAllText(Path.Combine(s.Parent, "outside", "journal.json"), "{}");
            Assert.Null(new JournalStore(s.Root).Existing(name));
        }

        [Fact]
        public void Existing_matches_case_insensitively_and_returns_the_real_name()
        {
            using var s = new Sandbox();
            s.Journal("Riverton");
            Assert.Equal("Riverton", new JournalStore(s.Root).Existing("riverton"));
        }

        [Fact]
        public void A_folder_without_journal_json_is_not_a_journal()
        {
            using var s = new Sandbox();
            Directory.CreateDirectory(Path.Combine(s.Root, "empty"));
            Assert.Null(new JournalStore(s.Root).Existing("empty"));
        }

        [Fact]
        public void Open_on_a_traversal_name_opens_nothing_and_writes_nothing_outside()
        {
            using var s = new Sandbox();
            Directory.CreateDirectory(Path.Combine(s.Parent, "outside"));
            File.WriteAllText(Path.Combine(s.Parent, "outside", "journal.json"), "{}");
            var store = new JournalStore(s.Root);
            store.Open("../outside");
            Assert.Null(store.Folder);
            store.SetTick("k", true, "");
            store.AddNote("", "hello", null, "");
            Assert.False(File.Exists(Path.Combine(s.Parent, "outside", "mayor.json")));
            Assert.Contains(s.Warnings, w => w.Contains("Not a journal folder"));
        }

        [Fact]
        public void SavePick_refuses_non_journals_and_remembers_real_ones()
        {
            using var s = new Sandbox();
            s.Journal("riverton");
            var store = new JournalStore(s.Root);
            Assert.False(store.SavePick("City", "../x"));
            Assert.False(File.Exists(Path.Combine(s.Root, "picks.json")));
            Assert.True(store.SavePick("City", "RIVERTON"));
            Assert.Equal("riverton", (string)JObject.Parse(File.ReadAllText(Path.Combine(s.Root, "picks.json")))["picks"]["City"]);
        }
    }

    public class Resolving
    {
        [Fact]
        public void Pick_beats_alias_beats_city_name()
        {
            using var s = new Sandbox();
            s.Journal("new-city-1");
            s.Journal("riverton");
            s.Journal("picked");
            var store = new JournalStore(s.Root);
            Assert.Equal("new-city-1", store.Resolve("New City 1"));
            File.WriteAllText(Path.Combine(s.Root, "cities.json"), "{\"aliases\":{\"New City 1\":\"riverton\"}}");
            Assert.Equal("riverton", store.Resolve("new city 1"));
            store.SavePick("New City 1", "picked");
            Assert.Equal("picked", store.Resolve("New City 1"));
        }

        [Fact]
        public void Aliases_and_picks_that_point_outside_are_ignored()
        {
            using var s = new Sandbox();
            s.Journal("city");
            File.WriteAllText(Path.Combine(s.Root, "cities.json"), "{\"aliases\":{\"City\":\"../../etc\"}}");
            File.WriteAllText(Path.Combine(s.Root, "picks.json"), "{\"picks\":{\"City\":{\"not\":\"a string\"}}}");
            Assert.Equal("city", new JournalStore(s.Root).Resolve("City"));
        }

        [Fact]
        public void Broken_map_files_do_not_stop_resolving()
        {
            using var s = new Sandbox();
            s.Journal("city");
            File.WriteAllText(Path.Combine(s.Root, "cities.json"), "{ not json");
            Assert.Equal("city", new JournalStore(s.Root).Resolve("City"));
            Assert.Contains(s.Warnings, w => w.StartsWith("cities.json"));
        }

        [Theory]
        [InlineData("New City 1", "new-city-1")]
        [InlineData("  Rain -- Shadow  ", "rain-shadow")]
        [InlineData("Ville Évreux", "ville-évreux")]
        [InlineData("", "")]
        public void Slug(string city, string slug) => Assert.Equal(slug, JournalStore.Slug(city));
    }

    public class Reading
    {
        [Fact]
        public void Poll_picks_up_changes_and_keeps_the_last_good_copy_when_a_write_is_half_done()
        {
            using var s = new Sandbox();
            var dir = s.Journal("j", "{\"v\":1}");
            var store = new JournalStore(s.Root);
            store.Open("j");
            Assert.Contains("\"v\":1", store.JournalText);
            File.WriteAllText(Path.Combine(dir, "journal.json"), "{\"v\":2, \"pad\":\"xx\"}");
            File.SetLastWriteTimeUtc(Path.Combine(dir, "journal.json"), DateTime.UtcNow.AddSeconds(5));
            Assert.True(store.Poll());
            Assert.Contains("\"v\":2", store.JournalText);
            File.WriteAllText(Path.Combine(dir, "journal.json"), "{\"v\":3, \"half");
            for (var i = 0; i < 3; i++) Assert.False(store.Poll());
            Assert.True(store.Poll());
            Assert.Contains("\"v\":2", store.JournalText);
            Assert.Contains("can't be read", store.Error);
        }

        [Fact]
        public void A_too_large_journal_is_refused()
        {
            using var s = new Sandbox();
            var dir = s.Journal("j");
            File.WriteAllText(Path.Combine(dir, "journal.json"), "{\"x\":\"" + new string('a', (int)JournalStore.MaxFileBytes) + "\"}");
            var store = new JournalStore(s.Root);
            store.Open("j");
            Assert.Equal("", store.JournalText);
            Assert.Contains("too large", store.Error);
        }

        [Fact]
        public void Deep_nesting_is_refused()
        {
            using var s = new Sandbox();
            s.Journal("j", new string('[', 200).Insert(0, "{\"a\":") + new string(']', 200) + "}");
            var store = new JournalStore(s.Root);
            store.Open("j");
            for (var i = 0; i < 4; i++) store.Poll();
            Assert.Equal("", store.JournalText);
            Assert.Contains("can't be read", store.Error);
        }

        [Fact]
        public void A_missing_journal_json_is_reported()
        {
            using var s = new Sandbox();
            var dir = s.Journal("j");
            var store = new JournalStore(s.Root);
            store.Open("j");
            File.Delete(Path.Combine(dir, "journal.json"));
            Assert.True(store.Poll());
            Assert.Contains("no journal.json", store.Error);
        }
    }

    public class MayorSide
    {
        internal static (Sandbox, JournalStore) Opened()
        {
            var s = new Sandbox();
            s.Journal("j");
            var store = new JournalStore(s.Root);
            store.Open("j");
            return (s, store);
        }

        [Fact]
        public void Ticks_statuses_notes_and_debriefs_are_written()
        {
            var (s, store) = Opened();
            using (s)
            {
                store.SetTick("p:roads/lights", true, "May 2026, 10:00");
                store.SetStatus("roads", "hold", "");
                store.AddNote("roads", "jam here", new[] { 1.23f, -4.56f, 700f }, "");
                store.SaveDebrief("2026-11-24", "{\"built\":\"lights\",\"ask\":\"cost?\"}", "");
                store.FinishDebrief("2026-11-24", true, "");
                var m = s.Mayor("j");
                Assert.True((bool)m["ticks"]["p:roads/lights"]["done"]);
                Assert.Equal("May 2026, 10:00", (string)m["ticks"]["p:roads/lights"]["gameDate"]);
                Assert.Equal("hold", (string)m["status"]["roads"]["status"]);
                Assert.Equal("jam here", (string)m["notes"][0]["text"]);
                Assert.Equal(1.2, (double)m["notes"][0]["where"]["x"]);
                Assert.Equal("cost?", (string)m["debriefs"]["2026-11-24"]["answers"]["ask"]);
                Assert.True((bool)m["debriefs"]["2026-11-24"]["done"]);
                store.SetStatus("roads", "", "");
                Assert.Null(s.Mayor("j")["status"]["roads"]);
            }
        }

        [Fact]
        public void Unknown_statuses_are_ignored()
        {
            var (s, store) = Opened();
            using (s)
            {
                store.SetStatus("roads", "<script>", "");
                Assert.False(File.Exists(Path.Combine(s.Root, "j", "mayor.json")));
            }
        }

        [Fact]
        public void Untrusted_strings_are_capped_and_cleaned()
        {
            var (s, store) = Opened();
            using (s)
            {
                store.AddNote(new string('p', 1000), "  line one\nline\u0000two\u0007 " + new string('x', 5000), null, "");
                store.SetTick("p:a/b", true, new string('d', 1000));
                var m = s.Mayor("j");
                var text = (string)m["notes"][0]["text"];
                Assert.StartsWith("line one\nlinetwo", text);
                Assert.Equal(JournalStore.MaxNote, text.Length);
                Assert.Equal(JournalStore.MaxKey, ((string)m["notes"][0]["project"]).Length);
                Assert.Equal(40, ((string)m["ticks"]["p:a/b"]["gameDate"]).Length);
            }
        }

        [Fact]
        public void Empty_notes_and_bad_positions_are_dropped()
        {
            var (s, store) = Opened();
            using (s)
            {
                store.AddNote("", "   ", null, "");
                Assert.False(File.Exists(Path.Combine(s.Root, "j", "mayor.json")));
                store.AddNote("", "ok", new[] { float.NaN, 0f, 0f }, "");
                Assert.Null(s.Mayor("j")["notes"][0]["where"]);
            }
        }

        [Fact]
        public void The_number_of_notes_is_capped()
        {
            var (s, store) = Opened();
            using (s)
            {
                for (var i = 0; i < JournalStore.MaxNotes + 5; i++) store.AddNote("", "n" + i, null, "");
                Assert.Equal(JournalStore.MaxNotes, ((JArray)s.Mayor("j")["notes"]).Count);
                Assert.Contains(s.Warnings, w => w.Contains("already has"));
            }
        }

        [Fact]
        public void Debrief_answers_are_capped_and_non_strings_become_empty()
        {
            var (s, store) = Opened();
            using (s)
            {
                var answers = new JObject { ["built"] = new string('b', 9000), ["evil"] = new JObject { ["x"] = 1 } };
                for (var i = 0; i < 40; i++) answers["q" + i] = "a";
                store.SaveDebrief("b1", answers.ToString(), "");
                var a = (JObject)s.Mayor("j")["debriefs"]["b1"]["answers"];
                Assert.Equal(JournalStore.MaxAnswer, ((string)a["built"]).Length);
                Assert.Equal("", (string)a["evil"]);
                Assert.Equal(JournalStore.MaxAnswers, a.Count);
                store.SaveDebrief("b1", "not json", "");
                Assert.Equal(JournalStore.MaxAnswer, ((string)s.Mayor("j")["debriefs"]["b1"]["answers"]["built"]).Length);
            }
        }

        [Fact]
        public void Notes_can_be_deleted_by_id()
        {
            var (s, store) = Opened();
            using (s)
            {
                store.AddNote("", "one", null, "");
                store.AddNote("", "two", null, "");
                var id = (string)s.Mayor("j")["notes"][0]["id"];
                store.DeleteNote(id);
                store.DeleteNote("no-such-id");
                Assert.Equal("two", (string)s.Mayor("j")["notes"].Single()["text"]);
            }
        }

        [Fact]
        public void A_damaged_mayor_json_is_kept_aside_and_the_backup_restored()
        {
            var (s, store) = Opened();
            using (s)
            {
                store.AddNote("", "first", null, "");
                store.AddNote("", "second", null, "");   // the backup now holds "first"
                var path = Path.Combine(s.Root, "j", "mayor.json");
                File.WriteAllText(path, "{ damaged");
                var again = new JournalStore(s.Root);
                again.Open("j");
                Assert.Equal("first", (string)again.Mayor["notes"].Single()["text"]);
                Assert.Equal("{ damaged", File.ReadAllText(Directory.GetFiles(Path.Combine(s.Root, "j"), "mayor.broken-*.json").Single()));
                Assert.Contains(s.Warnings, w => w.Contains("restored the backup"));
            }
        }

        [Fact]
        public void Missing_sections_are_filled_in_on_load()
        {
            var (s, store) = Opened();
            using (s)
            {
                File.WriteAllText(Path.Combine(s.Root, "j", "mayor.json"), "{\"notes\":\"not an array\",\"extra\":1}");
                var again = new JournalStore(s.Root);
                again.Open("j");
                Assert.IsType<JArray>(again.Mayor["notes"]);
                Assert.IsType<JObject>(again.Mayor["debriefs"]);
                Assert.Equal(1, (int)again.Mayor["extra"]);
            }
        }

        [Fact]
        public void Nothing_is_written_while_no_journal_is_open()
        {
            using var s = new Sandbox();
            var store = new JournalStore(s.Root);
            store.SetTick("k", true, "");
            store.AddNote("", "x", null, "");
            store.MarkSeen("2026");
            Assert.Empty(Directory.GetFiles(s.Root, "*", SearchOption.AllDirectories));
        }
    }

    public class Cleaning
    {
        [Theory]
        [InlineData(null, 10, "")]
        [InlineData("  a\tb\r\nc  ", 10, "ab\nc")]
        [InlineData("abcdef", 3, "abc")]
        [InlineData("héllo wörld ✓", 50, "héllo wörld ✓")]
        public void Clean(string input, int max, string expected) => Assert.Equal(expected, JournalStore.Clean(input, max));
    }

    public class Review2026Fixes
    {
        [Fact]
        public void A_pick_can_be_cleared()
        {
            using var s = new Sandbox();
            s.Journal("a");
            s.Journal("city");
            var store = new JournalStore(s.Root);
            store.SavePick("City", "a");
            Assert.Equal("a", store.Resolve("City"));
            Assert.True(store.SavePick("CITY", null));
            Assert.Equal("city", store.Resolve("City"));
        }

        [Fact]
        public void Create_starts_an_empty_journal_once_and_never_outside()
        {
            using var s = new Sandbox();
            var store = new JournalStore(s.Root);
            Assert.Equal("new-city-1", store.Create("New City 1"));
            Assert.Equal("new-city-1", store.Create("new city 1"));
            Assert.Equal("my-city", store.Create("../.."));
            Assert.Equal("my-city", store.Create("???"));
            Assert.Equal(new[] { "my-city", "new-city-1" }, store.Available());
            store.Open("new-city-1");
            Assert.Equal("", store.Error);
            store.AddNote("", "works without a manager", null, "");
            Assert.Equal("works without a manager", (string)s.Mayor("new-city-1")["notes"][0]["text"]);
        }

        [Fact]
        public void A_damaged_mayor_file_without_backup_is_reported_once_not_reloaded_every_poll()
        {
            using var s = new Sandbox();
            var dir = s.Journal("j");
            File.WriteAllText(Path.Combine(dir, "mayor.json"), "{ damaged");
            var store = new JournalStore(s.Root);
            store.Open("j");
            Assert.Contains("set aside", store.MayorProblem);
            var warnings = s.Warnings.Count;
            Assert.False(store.Poll());
            Assert.False(store.Poll());
            Assert.Equal(warnings, s.Warnings.Count);
        }

        [Fact]
        public void Writes_leave_no_temporary_files_and_keep_a_backup()
        {
            using var s = new Sandbox();
            var dir = s.Journal("j");
            var store = new JournalStore(s.Root);
            store.Open("j");
            for (var i = 0; i < 5; i++) store.AddNote("", "n" + i, null, "");
            Assert.Empty(Directory.GetFiles(dir, "*.tmp"));
            Assert.Equal(4, ((JArray)JObject.Parse(File.ReadAllText(Path.Combine(dir, "mayor.json.bak")))["notes"]).Count);
        }

        [Fact]
        public void A_newer_format_is_flagged_and_the_journals_stamp_is_kept()
        {
            using var s = new Sandbox();
            s.Journal("j", "{\"format\":2,\"updated\":\"2026-11-24T10:00:00Z\"}");
            var store = new JournalStore(s.Root);
            store.Open("j");
            Assert.Contains("newer City Manager", store.Error);
            Assert.Equal("2026-11-24T10:00:00Z", store.Updated);
            Assert.NotEqual("", store.JournalText);
        }

        [Fact]
        public void A_journal_put_back_with_its_old_time_stamp_is_read_again()
        {
            using var s = new Sandbox();
            var dir = s.Journal("j", "{\"v\":1}");
            var path = Path.Combine(dir, "journal.json");
            var store = new JournalStore(s.Root);
            store.Open("j");
            var when = File.GetLastWriteTimeUtc(path);
            File.Delete(path);
            store.Poll();
            File.WriteAllText(path, "{\"v\":1}");
            File.SetLastWriteTimeUtc(path, when);
            Assert.True(store.Poll());
            Assert.Contains("\"v\":1", store.JournalText);
            Assert.Equal("", store.Error);
        }

        [Fact]
        public void Stamps_are_utc_with_seconds_and_sort_as_strings()
        {
            Assert.Matches(@"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", JournalStore.Stamp());
            Assert.True(string.CompareOrdinal("2026-11-24 19:00", "2026-11-24T00:00:00Z") < 0);
        }

        [Fact]
        public void Date_like_strings_round_trip_unchanged()
        {
            using var s = new Sandbox();
            var dir = s.Journal("j", "{\"updated\":\"2026-11-24T10:00:00Z\",\"d\":\"2026-11-24 19:00\"}");
            File.WriteAllText(Path.Combine(dir, "mayor.json"), "{\"ticks\":{\"k\":{\"done\":true,\"at\":\"2026-11-24T10:00:00Z\"}}}");
            var store = new JournalStore(s.Root);
            store.Open("j");
            store.AddNote("", "x", null, "");
            Assert.Contains("\"2026-11-24T10:00:00Z\"", store.JournalText);
            Assert.Contains("\"2026-11-24 19:00\"", store.JournalText);
            Assert.Equal("2026-11-24T10:00:00Z", (string)s.Mayor("j")["ticks"]["k"]["at"]);
        }

        [Fact]
        public void The_mayor_files_format_is_never_lowered()
        {
            using var s = new Sandbox();
            var dir = s.Journal("j");
            File.WriteAllText(Path.Combine(dir, "mayor.json"), "{\"format\":3}");
            var store = new JournalStore(s.Root);
            store.Open("j");
            store.SetTick("k", true, "");
            Assert.Equal(3, (int)s.Mayor("j")["format"]);
        }
    }

    public class Pictures
    {
        /// <summary>The first 24 bytes of a PNG: signature, IHDR length and type, width and height (all a size check reads).</summary>
        private static byte[] PngHeader(int w, int h)
        {
            var b = new List<byte> { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0, 0, 0, 13 };
            b.AddRange(Encoding.ASCII.GetBytes("IHDR"));
            foreach (var v in new[] { w, h }) b.AddRange(new[] { (byte)(v >> 24), (byte)(v >> 16), (byte)(v >> 8), (byte)v });
            b.AddRange(new byte[13]);
            return b.ToArray();
        }

        [Fact]
        public void Only_existing_PNGs_within_the_limits_and_with_plain_names_are_offered()
        {
            using var s = new Sandbox();
            var dir = s.Journal("j", "{\"images\":{\"ok.png\":[1,1],\"huge.png\":[10,10],\"wide.png\":[1,1],\"eps.png\":[1,1],"
                + "\"missing.png\":[1,1],\"../mayor.png\":[1,1],\"a b.png\":[1,1],\"x.jpg\":[1,1]}}");
            var img = Directory.CreateDirectory(Path.Combine(dir, "images")).FullName;
            File.WriteAllBytes(Path.Combine(img, "ok.png"), PngHeader(1600, 900));
            File.WriteAllBytes(Path.Combine(img, "huge.png"), PngHeader(16384, 16384));
            File.WriteAllBytes(Path.Combine(img, "wide.png"), PngHeader(4000, 10));
            File.WriteAllText(Path.Combine(img, "eps.png"), "%!PS-Adobe-3.0 EPSF-3.0\n{} loop\n");
            File.WriteAllBytes(Path.Combine(dir, "mayor.png"), PngHeader(10, 10));
            var store = new JournalStore(s.Root);
            store.Open("j");
            Assert.Equal(new[] { "ok.png" }, store.Pictures.Properties().Select(p => p.Name));
            Assert.Equal(new JArray(1600, 900), store.Pictures["ok.png"]);
            Assert.Contains(s.Warnings, w => w.Contains("huge.png is not shown"));
        }

        [Fact]
        public void PngSize_reads_the_header_and_rejects_everything_else()
        {
            var path = Path.GetTempFileName();
            try
            {
                File.WriteAllBytes(path, PngHeader(640, 480));
                Assert.Equal((640, 480), JournalStore.PngSize(path));
                File.WriteAllBytes(path, new byte[] { 0x89, 0x50 });
                Assert.Null(JournalStore.PngSize(path));
                File.WriteAllBytes(path, PngHeader(0, 5));
                Assert.Null(JournalStore.PngSize(path));
                Assert.Null(JournalStore.PngSize(path + ".missing"));
            }
            finally { File.Delete(path); }
        }
    }

    /// <summary>Which journal is open as cities load and get renamed (the 2026-11-24 third review's finding 1).</summary>
    public class Following
    {
        [Fact]
        public void A_second_city_loaded_in_the_same_session_opens_its_own_journal()
        {
            using var s = new Sandbox();
            s.Journal("first");
            s.Journal("second-town");
            var store = new JournalStore(s.Root);
            store.Follow("First");
            Assert.Equal("first", store.Folder);
            store.Forget();               // the game starts loading another city, then gives the world its name
            store.Follow("Second Town");
            Assert.Equal("second-town", store.Folder);
            Assert.False(File.Exists(Path.Combine(s.Root, "picks.json")));
        }

        [Fact]
        public void A_rename_keeps_the_journal_and_remembers_it_under_the_new_name()
        {
            using var s = new Sandbox();
            s.Journal("first");
            var notes = new List<string>();
            JournalStore.Info = notes.Add;
            try
            {
                var store = new JournalStore(s.Root);
                store.Follow("First");
                Assert.True(store.Follow("Renamed"));
                Assert.Equal("first", store.Folder);
                Assert.Equal("first", new JournalStore(s.Root).Resolve("Renamed"));
                Assert.Contains(notes, n => n.Contains("renamed"));
            }
            finally { JournalStore.Info = _ => { }; }
        }

        [Fact]
        public void A_journal_that_appears_while_playing_is_picked_up()
        {
            using var s = new Sandbox();
            var store = new JournalStore(s.Root);
            Assert.True(store.Follow("My City"));
            Assert.Null(store.Folder);
            s.Journal("my-city");         // the manager's first build
            Assert.True(store.Follow("My City"));
            Assert.Equal("my-city", store.Folder);
        }

        [Fact]
        public void Pick_start_and_the_automatic_choice()
        {
            using var s = new Sandbox();
            s.Journal("other");
            var store = new JournalStore(s.Root);
            store.Follow("Home Town");
            Assert.Null(store.Folder);
            store.Pick("../other");
            Assert.Null(store.Folder);
            store.Pick("other");
            Assert.Equal("other", store.Folder);
            store.Pick(null);             // no journal is named after the city
            Assert.Null(store.Folder);
            store.Start();
            Assert.Equal("home-town", store.Folder);
            Assert.Equal("home-town", new JournalStore(s.Root).Resolve("Home Town"));
        }

        [Fact]
        public void A_pick_that_cant_be_saved_still_opens_and_says_so_without_the_user_data_path()
        {
            using var s = new Sandbox();
            s.Journal("a");
            Directory.CreateDirectory(Path.Combine(s.Root, "picks.json.tmp"));   // makes the write fail
            var store = new JournalStore(s.Root);
            store.Follow("City");
            Assert.False(store.SavePick("City", "a"));
            store.Pick("a");
            Assert.Equal("a", store.Folder);
            Assert.Contains("couldn't be saved", store.Error);
            Assert.Contains(s.Warnings, w => w.Contains("picks.json can't be written"));
            Assert.DoesNotContain(s.Warnings, w => w.Contains(s.Root) || w.Contains(s.Parent));
        }

        [Fact]
        public void A_city_named_after_a_windows_device_gets_a_usable_folder()
        {
            using var s = new Sandbox();
            Assert.Equal("con-city", new JournalStore(s.Root).Create("CON"));
            Assert.Equal("lpt1-city", new JournalStore(s.Root).Create("Lpt1"));
        }
    }

    /// <summary>Size limits and odd input (the third review's findings 3, 4, 8, 10, 13 and 16).</summary>
    public class Limits
    {
        [Fact]
        public void A_change_that_would_outgrow_the_read_limit_is_refused_and_the_file_stays_readable()
        {
            var (s, store) = MayorSide.Opened();
            using (s)
            {
                // A mayor.json just under the limit, written the way the mod writes it; then one more long note.
                var big = new string('x', JournalStore.MaxNote);
                var path = Path.Combine(s.Root, "j", "mayor.json");
                JObject Fill(int n, int pad) => new JObject
                {
                    ["format"] = 1, ["pad"] = new string('p', pad),
                    ["notes"] = new JArray(Enumerable.Range(0, n).Select(i => new JObject { ["id"] = "n" + i.ToString("D6"), ["text"] = big })),
                };
                int Size(JObject o) => Encoding.UTF8.GetByteCount(o.ToString(Newtonsoft.Json.Formatting.Indented));
                const int count = 1000;   // under the note cap: the size limit must be what stops it
                var pad = (int)(JournalStore.MaxFileBytes - 500 - Size(Fill(count, 0)));
                File.WriteAllText(path, Fill(count, pad).ToString(Newtonsoft.Json.Formatting.Indented));
                Assert.InRange(new FileInfo(path).Length, JournalStore.MaxFileBytes - 600, JournalStore.MaxFileBytes);
                store.AddNote("", big, null, "");
                Assert.Contains("full", store.MayorProblem);
                Assert.True(new FileInfo(path).Length <= JournalStore.MaxFileBytes);
                var again = new JournalStore(s.Root);
                again.Open("j");
                Assert.Equal("", again.MayorProblem);
                Assert.Equal(count, ((JArray)again.Mayor["notes"]).Count);
            }
        }

        [Theory]
        [InlineData("99999999999")]
        [InlineData("1000000000000000000000000000000")]
        [InlineData("-5")]
        public void Odd_format_numbers_never_stop_saving(string format)
        {
            var (s, store) = MayorSide.Opened();
            using (s)
            {
                File.WriteAllText(Path.Combine(s.Root, "j", "mayor.json"), "{\"format\": " + format + "}");
                store.Open("j");
                store.SetTick("p:a/b", true, "");
                Assert.Equal("", store.MayorProblem);
                Assert.True((bool)s.Mayor("j")["ticks"]["p:a/b"]["done"]);
            }
        }

        [Fact]
        public void Notes_that_are_not_objects_do_not_stop_deleting()
        {
            var (s, store) = MayorSide.Opened();
            using (s)
            {
                File.WriteAllText(Path.Combine(s.Root, "j", "mayor.json"), "{\"notes\": [1, {\"id\": {\"x\": 1}}, {\"id\": \"n1\", \"text\": \"real\"}]}");
                store.Open("j");
                store.DeleteNote("n1");
                Assert.Equal(2, ((JArray)s.Mayor("j")["notes"]).Count);
            }
        }

        [Theory]
        [InlineData("p:roads/exit ")]
        [InlineData(" p:roads/exit")]
        [InlineData("p:roads/\u0007exit")]
        public void Keys_the_panel_would_not_find_again_are_refused_not_altered(string key)
        {
            var (s, store) = MayorSide.Opened();
            using (s)
            {
                store.SetTick(key, true, "");
                store.SetTick(new string('k', JournalStore.MaxKey + 1), true, "");
                store.SetStatus("roads ", "hold", "");
                store.FinishDebrief("2026-11-24\u0001", true, "");
                Assert.False(File.Exists(Path.Combine(s.Root, "j", "mayor.json")));
                Assert.Contains("odd characters", store.MayorProblem);
                store.SetTick("p:roads/exit", true, "");
                Assert.True((bool)s.Mayor("j")["ticks"]["p:roads/exit"]["done"]);
                Assert.Equal("", store.MayorProblem);
            }
        }

        [Fact]
        public void A_wrap_up_too_long_to_save_says_so()
        {
            var (s, store) = MayorSide.Opened();
            using (s)
            {
                store.SaveDebrief("2026-11-24", "{\"a\":\"" + new string('x', JournalStore.MaxAnswers * (JournalStore.MaxAnswer + 100)) + "\"}", "");
                Assert.Contains("too long", store.MayorProblem);
            }
        }

        [Fact]
        public void Note_ids_use_utc_like_every_other_stamp()
        {
            var (s, store) = MayorSide.Opened();
            using (s)
            {
                store.AddNote("", "x", null, "");
                var id = (string)s.Mayor("j")["notes"][0]["id"];
                var at = DateTime.ParseExact(id.Substring(1, 14), "yyyyMMddHHmmss", System.Globalization.CultureInfo.InvariantCulture);
                Assert.InRange((DateTime.UtcNow - at).TotalSeconds, -2, 10);
            }
        }

        [Fact]
        public void Cleaning_never_cuts_a_character_in_half()
        {
            Assert.Equal("ab", JournalStore.Clean("ab😀", 3));
            Assert.Equal("ab😀", JournalStore.Clean("ab😀", 4));
        }

        [Fact]
        public void A_too_large_update_says_the_last_good_copy_is_still_shown()
        {
            using var s = new Sandbox();
            var dir = s.Journal("j");
            var store = new JournalStore(s.Root);
            store.Open("j");
            File.WriteAllText(Path.Combine(dir, "journal.json"), "{\"x\":\"" + new string('a', (int)JournalStore.MaxFileBytes) + "\"}");
            Assert.True(store.Poll());
            Assert.Contains("too large", store.Error);
            Assert.Contains("last good copy", store.Error);
            Assert.Contains("Test", store.JournalText);
        }

        private static byte[] Png(int w, int h, int extra = 0)
        {
            var b = new List<byte> { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0, 0, 0, 13 };
            b.AddRange(Encoding.ASCII.GetBytes("IHDR"));
            foreach (var v in new[] { w, h }) b.AddRange(new[] { (byte)(v >> 24), (byte)(v >> 16), (byte)(v >> 8), (byte)v });
            b.AddRange(new byte[13 + extra]);
            return b.ToArray();
        }

        [Fact]
        public void Pictures_over_the_file_size_limit_are_not_offered()
        {
            using var s = new Sandbox();
            var dir = s.Journal("j", "{\"images\":{\"ok.png\":[1,1],\"bloated.png\":[1,1]}}");
            var img = Directory.CreateDirectory(Path.Combine(dir, "images")).FullName;
            File.WriteAllBytes(Path.Combine(img, "ok.png"), Png(100, 100));
            File.WriteAllBytes(Path.Combine(img, "bloated.png"), Png(100, 100, (int)JournalStore.MaxPictureBytes));
            var store = new JournalStore(s.Root);
            store.Open("j");
            Assert.Equal(new[] { "ok.png" }, store.Pictures.Properties().Select(p => p.Name));
        }

        [Fact]
        public void Pictures_are_checked_again_every_few_polls()
        {
            using var s = new Sandbox();
            var dir = s.Journal("j", "{\"images\":{\"late.png\":[1,1]}}");
            var store = new JournalStore(s.Root);
            store.Open("j");
            Assert.Empty(store.Pictures);
            var img = Directory.CreateDirectory(Path.Combine(dir, "images")).FullName;
            File.WriteAllBytes(Path.Combine(img, "late.png"), Png(64, 32));
            Assert.True(PollUntilChanged(store));
            Assert.Equal(new JArray(64, 32), store.Pictures["late.png"]);
            File.Delete(Path.Combine(img, "late.png"));
            Assert.True(PollUntilChanged(store));
            Assert.Empty(store.Pictures);
            for (var i = 0; i < JournalStore.PictureRecheckPolls; i++) Assert.False(store.Poll());   // nothing new, nothing to redraw
        }

        /// <summary>Polls like the mod until something changed: within PictureRecheckPolls polls, or a few rounds of them
        /// when Windows takes a moment to finish deleting a file that antivirus still holds.</summary>
        private static bool PollUntilChanged(JournalStore store)
        {
            for (var i = 0; i < 6 * JournalStore.PictureRecheckPolls; i++)
            {
                if (store.Poll()) return true;
                System.Threading.Thread.Sleep(50);
            }
            return false;
        }
    }

    /// <summary>Edits to mayor.json from outside the game while it runs (the third review's finding 9).</summary>
    public class OutsideEdits
    {
        private static void Write(string path, string text, int seconds)
        {
            File.WriteAllText(path, text);
            File.SetLastWriteTimeUtc(path, DateTime.UtcNow.AddSeconds(seconds));
        }

        [Fact]
        public void A_half_written_mayor_json_gets_a_few_polls_before_it_counts_as_damaged()
        {
            var (s, store) = MayorSide.Opened();
            using (s)
            {
                store.SetTick("p:a/1", true, "");
                store.SetTick("p:a/2", true, "");
                var path = Path.Combine(s.Root, "j", "mayor.json");
                var good = File.ReadAllText(path);
                Write(path, good.Substring(0, good.Length / 2), 5);
                for (var i = 0; i < 3; i++) store.Poll();
                Assert.Equal(2, ((JObject)store.Mayor["ticks"]).Count);
                Assert.Equal("", store.MayorProblem);
                Assert.Empty(Directory.GetFiles(Path.Combine(s.Root, "j"), "mayor.broken-*"));
                var o = JObject.Parse(good);
                ((JObject)o["ticks"])["p:a/3"] = new JObject { ["done"] = true, ["at"] = "2026-11-24T10:00:00Z" };
                Write(path, o.ToString(), 10);
                store.Poll();
                Assert.Equal(3, ((JObject)store.Mayor["ticks"]).Count);
            }
        }

        [Fact]
        public void A_file_that_stays_damaged_is_set_aside_and_the_message_clears_after_the_next_save()
        {
            var (s, store) = MayorSide.Opened();
            using (s)
            {
                store.SetTick("p:a/1", true, "");
                store.SetTick("p:a/2", true, "");   // the backup holds the first tick
                Write(Path.Combine(s.Root, "j", "mayor.json"), "{ damaged", 5);
                for (var i = 0; i < 4; i++) store.Poll();
                Assert.Contains("restored", store.MayorProblem);
                Assert.Single(Directory.GetFiles(Path.Combine(s.Root, "j"), "mayor.broken-*"));
                store.SetTick("p:a/3", true, "");
                Assert.Equal("", store.MayorProblem);
            }
        }

        [Fact]
        public void An_edit_made_between_polls_is_kept_by_the_next_change()
        {
            var (s, store) = MayorSide.Opened();
            using (s)
            {
                store.AddNote("", "first", null, "");
                var path = Path.Combine(s.Root, "j", "mayor.json");
                var o = JObject.Parse(File.ReadAllText(path));
                ((JArray)o["notes"]).Clear();                // someone tidies the notes...
                Write(path, o.ToString(), 5);
                store.SetTick("p:a/1", true, "");             // ...and the Mayor clicks before the next poll
                var m = s.Mayor("j");
                Assert.Empty((JArray)m["notes"]);
                Assert.True((bool)m["ticks"]["p:a/1"]["done"]);
            }
        }
    }

    /// <summary>The rename from City Journal (0.5): the journals' folder moves once.</summary>
    public class Rename
    {
        [Fact]
        public void The_old_folder_moves_to_CityManager_once()
        {
            using var s = new Sandbox();
            var modsData = s.Parent;
            var old = Directory.CreateDirectory(Path.Combine(modsData, "CityJournal", "riverton")).FullName;
            File.WriteAllText(Path.Combine(old, "journal.json"), "{}");
            Directory.Delete(s.Root, true);   // no CityManager folder yet
            var root = JournalStore.JournalsFolder(modsData);
            Assert.Equal(Path.Combine(modsData, "CityManager"), root);
            Assert.True(File.Exists(Path.Combine(root, "riverton", "journal.json")));
            Assert.False(Directory.Exists(Path.Combine(modsData, "CityJournal")));
        }

        [Fact]
        public void An_existing_CityManager_folder_is_used_and_the_old_one_left_alone()
        {
            using var s = new Sandbox();
            var modsData = s.Parent;
            Directory.CreateDirectory(Path.Combine(modsData, "CityJournal", "old"));
            Assert.Equal(s.Root, JournalStore.JournalsFolder(modsData));
            Assert.True(Directory.Exists(Path.Combine(modsData, "CityJournal", "old")));
        }
    }

    /// <summary>Saving while another program holds mayor.json open. On Windows these are real locks (antivirus or cloud
    /// sync share it for reading and writing; some editors only for reading); elsewhere the save simply works. Either way
    /// nothing is lost, the file is never half-written, and nothing is left behind.</summary>
    public class FilesHeldOpen
    {
        [Theory]
        [InlineData(FileShare.ReadWrite)]
        [InlineData(FileShare.Read)]
        public void Nothing_is_lost_while_another_program_holds_the_file(FileShare share)
        {
            var (s, store) = MayorSide.Opened();
            using (s)
            {
                var dir = Path.Combine(s.Root, "j");
                var path = Path.Combine(dir, "mayor.json");
                store.SetTick("p:a/1", true, "");
                using (new FileStream(path, FileMode.Open, FileAccess.Read, share))
                {
                    store.SetTick("p:a/2", true, "");
                    Assert.True(store.MayorProblem == "" || store.MayorProblem.StartsWith("Not saved"), store.MayorProblem);
                }
                Assert.True((bool)s.Mayor("j")["ticks"]["p:a/1"]["done"]);   // whole and readable, whatever happened
                store.SetTick("p:a/3", true, "");                             // once it's let go, everything is saved
                Assert.Equal("", store.MayorProblem);
                var ticks = (JObject)s.Mayor("j")["ticks"];
                Assert.Equal(new[] { "p:a/1", "p:a/2", "p:a/3" }, ticks.Properties().Select(p => p.Name).OrderBy(n => n));
                Assert.Empty(Directory.GetFiles(dir, "*.tmp"));
            }
        }
    }
}
