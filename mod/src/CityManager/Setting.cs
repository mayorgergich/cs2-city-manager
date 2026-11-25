// The mod's Options page: one key binding (open or close the journal, Ctrl+J by default) and a reset button.
// Ctrl+J was free in the base game and in every enabled mod's bindings when it was picked (2026-11-24).

using System.Collections.Generic;
using Colossal;
using Colossal.IO.AssetDatabase;
using Game.Input;
using Game.Modding;
using Game.Settings;

namespace CityManager
{
    [FileLocation(nameof(CityManager))]
    [SettingsUIGroupOrder(KeysGroup)]
    [SettingsUIShowGroupName(KeysGroup)]
    [SettingsUIKeyboardAction(Mod.ToggleAction, ActionType.Button,
        usages: new[] { Usages.kDefaultUsage, Usages.kToolUsage, Usages.kCancelableToolUsage, Usages.kDiscardableToolUsage })]
    public sealed class Setting : ModSetting
    {
        public const string Section = "Main";
        public const string KeysGroup = "Keys";

        public Setting(IMod mod) : base(mod)
        {
        }

        [SettingsUIKeyboardBinding(BindingKeyboard.J, Mod.ToggleAction, ctrl: true)]
        [SettingsUISection(Section, KeysGroup)]
        public ProxyBinding ToggleBinding { get; set; }

        [SettingsUISection(Section, KeysGroup)]
        public bool ResetBindings
        {
            set { ResetKeyBindings(); }
        }

        public override void SetDefaults()
        {
        }
    }

    /// <summary>English text for the Options page.</summary>
    public sealed class LocaleEN : IDictionarySource
    {
        private readonly Setting _setting;

        public LocaleEN(Setting setting) => _setting = setting;

        public IEnumerable<KeyValuePair<string, string>> ReadEntries(IList<IDictionaryEntryError> errors, Dictionary<string, int> indexCounts) =>
            new Dictionary<string, string>
            {
                { _setting.GetSettingsLocaleID(), "City Manager" },
                { _setting.GetOptionTabLocaleID(Setting.Section), "Main" },
                { _setting.GetOptionGroupLocaleID(Setting.KeysGroup), "Keys" },
                { _setting.GetOptionLabelLocaleID(nameof(Setting.ToggleBinding)), "Open or close the journal" },
                { _setting.GetOptionDescLocaleID(nameof(Setting.ToggleBinding)), "Opens the City Manager panel, or closes it when it's open." },
                { _setting.GetOptionLabelLocaleID(nameof(Setting.ResetBindings)), "Reset keys" },
                { _setting.GetOptionDescLocaleID(nameof(Setting.ResetBindings)), "Put the City Manager's keys back to their defaults." },
                { _setting.GetBindingKeyLocaleID(Mod.ToggleAction), "Open or close the journal" },
                { _setting.GetBindingMapLocaleID(), "City Manager" },
            };

        public void Unload()
        {
        }
    }
}
