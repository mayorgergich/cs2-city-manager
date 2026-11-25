// City Manager: the Mayor's briefing book inside the game.
//
// A City Manager (a person, a script or an AI assistant) writes one journal per city:
//   <LocalLow>/ModsData/CityManager/<journal>/journal.json   projects, the current briefing, reports, city notes
//   <LocalLow>/ModsData/CityManager/<journal>/images/*.png   pictures the pages show
// The mod writes the Mayor's side next to it (and writes a journal.json only to start an empty journal):
//   <LocalLow>/ModsData/CityManager/<journal>/mayor.json     ticks, status changes, notes, wrap-up answers
// journal.json is re-read within about a second whenever it changes, so it can be updated while the game runs.
// Which journal belongs to the loaded city: picks.json (the Mayor's own pick), then cities.json aliases, then the
// folder named after the city. format/README.md describes journal.json, mayor.json and city.json.

using System.Reflection;
using Colossal.IO.AssetDatabase;
using Colossal.Logging;
using Game;
using Game.Input;
using Game.Modding;
using Game.SceneFlow;

namespace CityManager
{
    public sealed class Mod : IMod
    {
        public const string Name = "CityManager";
        public const string ToggleAction = "ToggleJournal";

        public static readonly ILog Log = LogManager.GetLogger(Name).SetShowsErrorsInUI(false);

        /// <summary>The "open or close the journal" key (Ctrl+J by default; the player can rebind it in Options).</summary>
        public static ProxyAction Toggle { get; private set; }

        private Setting _setting;

        public static string InformationalVersion =>
            typeof(Mod).Assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion ?? "?";

        public void OnLoad(UpdateSystem updateSystem)
        {
            Log.Info($"City Manager {InformationalVersion} loading");
            JournalStore.Warn = Log.Warn;
            JournalStore.Info = Log.Info;
            _setting = new Setting(this);
            _setting.RegisterInOptionsUI();
            GameManager.instance.localizationManager.AddSource("en-US", new LocaleEN(_setting));
            _setting.RegisterKeyBindings();
            AssetDatabase.global.LoadSettings(Name, _setting, new Setting(this));
            Toggle = _setting.GetAction(ToggleAction);
            Toggle.shouldBeEnabled = true;
            Log.Info($"Toggle key registered: {Toggle.name}, bound {Toggle.isSet}");

            updateSystem.UpdateAt<JournalSystem>(SystemUpdatePhase.UIUpdate);
        }

        public void OnDispose()
        {
            _setting?.UnregisterInOptionsUI();
            _setting = null;
            Toggle = null;
        }
    }
}
