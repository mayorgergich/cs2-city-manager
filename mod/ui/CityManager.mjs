/*!
 * Cities: Skylines II UI Module
 *
 * Id: CityManager
 * Author: mayorgergich
 * Version: 0.4.0
 * Dependencies:
 */
// City Manager: the Mayor's briefing book. One button (top left) or Ctrl+J opens a panel with five tabs: Today (the
// briefing, what's still open, the next steps), Projects, Notes, Wrap-up and City (the manager's city notes and reports).
// Hand-written, no bundler: React, cs2/api and cs2/ui are the game's own. Bindings: JournalSystem.cs.
// Sizes in rem (the game's UI unit: 1920 wide on 16:9 and on the iPad's 4:3).

const React = window.React;
const api = window["cs2/api"];
const ui = window["cs2/ui"];

// The player's text scale (Options, Interface). The game sets --fontScale on the page's root element and sizes its own
// text by it (index.css: --fontSizeS is calc(16rem * var(--fontScale)), and so on). A literal font size ignores it, so
// every style passes through textScaled() on its way into an element: its rem font size and line height, and the height
// of a one-line control (a button, a text box), are multiplied by the scale. The scale is read the way the game's own
// code reads it, and a scale of 1 changes nothing.
let textK = 1;
const fontScale = () => {
    try {
        const v = Number.parseFloat(String(document.documentElement.style.getPropertyValue("--fontScale") || "1").trim());
        return v >= 0.5 && v <= 3 ? v : 1;
    } catch (e) {
        return 1;
    }
};
const remOf = (v) => {
    const m = /^(-?[0-9]+(?:\.[0-9]+)?)rem$/.exec(String(v));
    return m ? Number.parseFloat(m[1]) : null;
};
const scaledStyles = new WeakMap();
function textScaled(style, k = textK) {
    if (k === 1 || !style || typeof style !== "object") return style;
    const hit = scaledStyles.get(style);
    if (hit && hit.k === k) return hit.style;
    let out = null;
    const put = (key, n) => {
        out = out || { ...style };
        out[key] = Math.round(n * k * 100) / 100 + "rem";
    };
    const fs = remOf(style.fontSize), lh = remOf(style.lineHeight), ht = remOf(style.height), wd = remOf(style.width);
    if (fs !== null) put("fontSize", fs);
    if (lh !== null) put("lineHeight", lh);
    if (ht !== null && (ht === lh || (fs !== null && lh === null))) {
        put("height", ht);
        if (wd !== null && wd === ht) put("width", wd);   // a square box stays square
    }
    const res = out || style;
    scaledStyles.set(style, { k, style: res });
    return res;
}
const h = (type, props, ...children) =>
    React.createElement(type, props && props.style && textK !== 1 ? { ...props, style: textScaled(props.style) } : props, ...children);
const G = "cityManager";
const trigger = (name, ...args) => api.trigger(G, name, ...args);

const open$ = api.bindValue(G, "open", false);
const journal$ = api.bindValue(G, "journal", "");
const mayor$ = api.bindValue(G, "mayor", "{}");
const info$ = api.bindValue(G, "info", "{}");
const fresh$ = api.bindValue(G, "fresh", false);

// Every mod's images share the coui://ui-mods/ host, so the names carry the mod's name.
const ICON = "coui://ui-mods/images/CityManager-icon.svg";
const ICON_NEW = "coui://ui-mods/images/CityManager-icon-new.svg";

const COMMAND = "/city-manager";   // the City Manager plugin's command in Claude Code (in full, /city-manager:city-manager)
const PANEL_W = 590;      // rem
const BODY_W = PANEL_W - 28 - 14; // content width inside the padding, less the scrollbar
const BODY_H = 700;       // rem
// The content width of the panel being drawn: pictures and the wrap-up's text boxes follow the window's width.
let bodyW = BODY_W;
const MAX_NOTE = 2000, MAX_ANSWER = 4000; // what the mod saves (JournalStore.MaxNote, MaxAnswer)

const STATUS = {
    active: { label: "In progress", color: "rgba(80, 160, 255, 0.9)" },
    next: { label: "Up next", color: "rgba(240, 180, 60, 0.9)" },
    idea: { label: "Idea", color: "rgba(170, 140, 255, 0.85)" },
    hold: { label: "On hold", color: "rgba(150, 150, 160, 0.85)" },
    done: { label: "Done", color: "rgba(70, 180, 100, 0.9)" },
};
const STATUS_ORDER = ["active", "next", "idea", "hold", "done"];
const SCALE = { city: "Citywide", district: "District", street: "Street", building: "Building", system: "Systems" };

const BLUE = "rgba(80, 160, 255, 0.85)";
const TAB = { flex: 1, padding: "6rem 0", textAlign: "center", backgroundColor: "rgba(255,255,255,0.10)", borderRadius: "4rem", marginRight: "4rem" };
const BOX = { width: "18rem", height: "18rem", lineHeight: "18rem", textAlign: "center", border: "2rem solid rgba(255,255,255,0.7)", borderRadius: "3rem", marginRight: "8rem", marginTop: "1rem" };
const BUTTON = { padding: "6rem 10rem", textAlign: "center", backgroundColor: "rgba(255,255,255,0.14)", borderRadius: "4rem", marginRight: "4rem" };
const CHECK_TEXT = { flex: 1, lineHeight: "20rem" };
const TR = { display: "flex", flexDirection: "row", padding: "4rem 6rem" };
const TD = { flexGrow: 1, flexShrink: 1, flexBasis: "0rem", paddingRight: "6rem", lineHeight: "19rem" };
const BOXED = { padding: "6rem 8rem", borderRadius: "4rem", lineHeight: "19rem" };
const SMALL = { fontSize: "12rem", color: "rgba(255,255,255,0.6)" };

const C = {
    panel: { position: "absolute", right: "12rem", top: "110rem", width: PANEL_W + "rem", backgroundColor: "rgba(22, 30, 46, 0.95)",
        borderRadius: "6rem", padding: "12rem 14rem", color: "#ffffff", fontSize: "15rem", pointerEvents: "auto" },
    header: { display: "flex", flexDirection: "row", alignItems: "flex-start", marginBottom: "6rem" },
    titleBox: { flex: 1 },
    title: { fontSize: "19rem", fontWeight: "bold" },
    sub: { ...SMALL, marginTop: "2rem" },
    close: { width: "26rem", height: "26rem", lineHeight: "26rem", textAlign: "center", borderRadius: "4rem", backgroundColor: "rgba(255,255,255,0.12)" },
    tabs: { display: "flex", flexDirection: "row", marginTop: "4rem", marginBottom: "8rem" },
    tab: TAB,
    tabOn: { ...TAB, backgroundColor: BLUE },
    scroll: { height: BODY_H + "rem", width: (PANEL_W - 28) + "rem" },
    inner: { width: BODY_W + "rem", paddingBottom: "12rem" },
    dockButton: { height: "26rem", lineHeight: "26rem", padding: "0 8rem", marginRight: "6rem", borderRadius: "4rem", fontSize: "13rem", backgroundColor: "rgba(255,255,255,0.12)" },
    // A corner grip drawn with two borders (the game's font has no corner glyphs).
    grip: { position: "absolute", bottom: "9rem", width: "14rem", height: "14rem", borderBottom: "2rem solid rgba(255,255,255,0.65)" },
    dragLayer: { position: "absolute", left: "0", top: "0", width: "100%", height: "100%", pointerEvents: "auto" },
    h1: { fontSize: "18rem", fontWeight: "bold", marginTop: "12rem", marginBottom: "2rem" },
    h2: { fontSize: "16rem", fontWeight: "bold", marginTop: "12rem", marginBottom: "2rem", color: "#cfe3ff" },
    h3: { fontSize: "15rem", fontWeight: "bold", marginTop: "10rem", color: "rgba(255,255,255,0.85)" },
    p: { marginTop: "6rem", lineHeight: "21rem" },
    dim: { marginTop: "6rem", lineHeight: "20rem", color: "rgba(255,255,255,0.65)" },
    small: SMALL,
    warn: { marginTop: "6rem", lineHeight: "20rem", color: "#ffd27a" },
    b: { fontWeight: "bold" },
    i: { color: "#e6dcff" }, // no italic face in the game font: Gameface falls back to a monospace one
    code: { color: "#ffe9a8" },
    link: { color: "#9cc8ff" },
    hr: { height: "1rem", backgroundColor: "rgba(255,255,255,0.18)", marginTop: "10rem", marginBottom: "4rem" },
    quote: { marginTop: "8rem", padding: "6rem 10rem", lineHeight: "20rem", backgroundColor: "rgba(255, 210, 120, 0.10)", borderLeft: "3rem solid rgba(255, 210, 120, 0.7)" },
    li: { display: "flex", flexDirection: "row", marginTop: "4rem", lineHeight: "20rem" },
    bullet: { width: "18rem", color: "rgba(255,255,255,0.6)" },
    liBody: { flex: 1 },
    table: { marginTop: "8rem", backgroundColor: "rgba(255,255,255,0.04)", borderRadius: "4rem" },
    tr: TR,
    trHead: { ...TR, backgroundColor: "rgba(255,255,255,0.08)", fontWeight: "bold" },
    td: TD,
    td1: { ...TD, flexGrow: 1.5 },
    factLabel: { ...TD, flexGrow: 1.3, color: "rgba(255,255,255,0.7)" },
    factValue: { ...TD, flexGrow: 0.8, fontWeight: "bold" },
    factNote: { ...TD, flexGrow: 1.7, ...SMALL },
    card: { marginTop: "6rem", padding: "8rem 10rem", borderRadius: "4rem", backgroundColor: "rgba(255,255,255,0.07)" },
    row: { display: "flex", flexDirection: "row", alignItems: "center" },
    cardTitle: { flex: 1, fontWeight: "bold" },
    chip: { fontSize: "12rem", padding: "1rem 7rem", borderRadius: "8rem", marginLeft: "6rem", color: "#ffffff" },
    tag: { fontSize: "12rem", padding: "1rem 7rem", borderRadius: "8rem", marginLeft: "6rem", backgroundColor: "rgba(255,255,255,0.12)" },
    section: { marginTop: "14rem", fontSize: "13rem", color: "rgba(255,255,255,0.6)", textTransform: "uppercase" },
    check: { display: "flex", flexDirection: "row", alignItems: "flex-start", marginTop: "6rem", padding: "5rem 6rem", borderRadius: "4rem", backgroundColor: "rgba(255,255,255,0.05)" },
    box: BOX,
    boxOn: { ...BOX, border: "2rem solid rgba(110, 220, 130, 0.95)", backgroundColor: "rgba(70, 180, 100, 0.9)" },
    checkText: CHECK_TEXT,
    checkDone: { ...CHECK_TEXT, color: "rgba(255,255,255,0.55)", textDecoration: "line-through" },
    button: BUTTON,
    buttonOn: { ...BUTTON, backgroundColor: BLUE },
    danger: { ...BUTTON, backgroundColor: "rgba(200, 60, 50, 0.85)" },
    primary: { padding: "6rem 12rem", textAlign: "center", backgroundColor: "rgba(60, 170, 90, 0.9)", borderRadius: "4rem", fontWeight: "bold" },
    back: { marginBottom: "4rem", color: "#9cc8ff" },
    plan: { ...BOXED, marginTop: "4rem", padding: "5rem 8rem", backgroundColor: "rgba(120, 180, 255, 0.10)" },
    note: { ...BOXED, marginTop: "5rem", backgroundColor: "rgba(255,255,255,0.05)" },
    reply: { ...BOXED, marginTop: "6rem", marginLeft: "14rem", padding: "5rem 8rem", backgroundColor: "rgba(120, 180, 255, 0.10)" },
    noteMayor: { ...BOXED, marginTop: "5rem", backgroundColor: "rgba(255, 210, 120, 0.10)" },
    textarea: { width: (BODY_W - 20) + "rem", height: "64rem", padding: "6rem 8rem", marginTop: "4rem", backgroundColor: "rgba(0,0,0,0.35)", border: "1rem solid rgba(255,255,255,0.3)", borderRadius: "4rem", color: "#ffffff", fontSize: "15rem" },
    input: { flex: 1, height: "30rem", padding: "0 8rem", backgroundColor: "rgba(0,0,0,0.35)", border: "1rem solid rgba(255,255,255,0.3)", borderRadius: "4rem", color: "#ffffff", fontSize: "15rem", marginRight: "6rem" },
    picker: { display: "flex", flexDirection: "row", alignItems: "center", marginTop: "6rem", backgroundColor: "rgba(255,255,255,0.07)", borderRadius: "4rem" },
    arrow: { width: "30rem", padding: "5rem 0", textAlign: "center", backgroundColor: "rgba(255,255,255,0.12)", borderRadius: "4rem" },
    pickName: { flex: 1, textAlign: "center", padding: "5rem 4rem" },
    caption: { ...SMALL, marginTop: "2rem" },
    command: { ...BOXED, marginTop: "6rem", backgroundColor: "rgba(255,255,255,0.10)", fontWeight: "bold", color: "#cfe3ff" },
    stepTools: { display: "flex", flexDirection: "row", marginLeft: "26rem", marginTop: "2rem", marginBottom: "4rem" },
    miniButton: { ...BUTTON, padding: "2rem 8rem", fontSize: "13rem", lineHeight: "18rem" },
    viewer: { position: "absolute", left: "0", top: "0", width: "100%", height: "100%", backgroundColor: "rgba(0,0,0,0.82)", pointerEvents: "auto",
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" },
};

// What a journal can make the panel draw. Journals can come from anywhere, the game's UI thread must stay responsive,
// and every picture is a texture in video memory. A real journal's busiest page has about 5,000 characters and
// 6 million picture pixels.
//   page/pixels: per page (tab), all text and all pictures together; the rest is cut, with a notice
//   line: any one field (a title, a step, a summary); body: a page's Markdown; items: any list; notes: the Mayor's notes
const LIMIT = { page: 40000, pixels: 24e6, line: 2000, body: 30000, items: 300, notes: 500 };
const PICTURE_TALL = 4; // a picture is laid out at most four times as tall as it is wide
// A picture is a plain PNG file name inside the journal's own images folder: nothing that could reach other files.
const PICTURE_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.png$/;

const parse = (s, fallback) => { try { return s ? JSON.parse(s) : fallback; } catch (e) { return fallback; } };
const obj = (x) => (x && typeof x === "object" && !Array.isArray(x) ? x : null);
// A journal's own property only: ids like "constructor" or "__proto__" must not reach Object's built-ins.
const own = (o, k) => (obj(o) && Object.prototype.hasOwnProperty.call(o, k) ? o[k] : undefined);
// Lists from a journal, capped, without null or non-object holes (a foreign journal can contain anything).
const arr = (x, max = LIMIT.items) => (Array.isArray(x) ? x.filter((v) => v !== null && v !== undefined).slice(0, max) : []);
const objs = (x, max) => arr(x, max).filter((v) => typeof v === "object");
const str = (x) => (typeof x === "string" ? x : x == null ? "" : String(x));
const stepKey = (projectId, stepId) => "p:" + str(projectId) + "/" + str(stepId);
const taskKey = (briefingId, taskId) => "b:" + str(briefingId) + "/" + str(taskId);
const prio = (p) => (typeof p.priority === "number" ? p.priority : 9);
const byPriority = (a, b) => prio(a) - prio(b);
// The Mayor's notes, oldest first, at most LIMIT.notes of the newest.
const mayorNotes = (mayor) => objs(mayor.notes, Infinity).slice(-LIMIT.notes);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad = (n) => (n < 10 ? "0" : "") + n;
// Stamps are UTC ("2026-11-24T19:00:05Z"); shown in the player's local time. Anything else is shown as written.
function when(at) {
    const s = str(at);
    if (/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(s)) {
        const d = new Date(s);
        if (!isNaN(d.getTime())) return d.getDate() + " " + MONTHS[d.getMonth()] + " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
    }
    return s;
}

// ---------- the page budget ----------

// Each tab makes a budget when it draws. The tab's own text takes from it first, then its Markdown and pictures (child
// components draw after their parent) take what is left; anything cut says so. A component with state of its own, which
// can redraw without its parent, gets its text already taken: that redraw would find the parent's budget spent.
const budget = () => ({ chars: LIMIT.page, pixels: LIMIT.pixels, cut: false });
function take(b, x, max = LIMIT.line) {
    let s = str(x);
    if (s.length > max) s = s.slice(0, max);
    if (s.length > b.chars) { s = s.slice(0, Math.max(0, b.chars)); b.cut = true; }
    b.chars -= s.length;
    return s;
}
const inline = (b, x, max) => markup(take(b, x, max));
const more = (b) => (b.cut ? h("div", { key: "more", style: C.dim }, "This page has more than the panel shows; the rest is cut off.") : null);

// ---------- a small Markdown renderer (headings, paragraphs, lists, tables, quotes, pictures, bold/italic/code) ----------

// Links exclude "[" and "(" inside, which keeps matching linear: the looser form took seconds on "[[[[…" (2026-11-24 review).
const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\][]+\]\([^()\s]+\)|\*[^*\s][^*]*\*|_[^_\s][^_]*_)/g;

// Gameface lays out text mixed with styled spans as separate blocks (a bold phrase lands on its own line, seen in
// game 2026-11-23), so marked-up text becomes one wrapping flex item per word. Plain text stays a single string.
const FLOW = { display: "flex", flexDirection: "row", flexWrap: "wrap" };

function markup(s) {
    INLINE.lastIndex = 0;
    if (!INLINE.test(s)) return s;
    INLINE.lastIndex = 0;
    const runs = [];
    let last = 0, m;
    while ((m = INLINE.exec(s)) !== null) {
        if (m.index > last) runs.push([s.slice(last, m.index), null]);
        const t = m[0];
        if (t.startsWith("**")) runs.push([t.slice(2, -2), C.b]);
        else if (t.startsWith("`")) runs.push([t.slice(1, -1), C.code]);
        else if (t.startsWith("[")) {
            const mm = /^\[([^\][]+)\]\(([^()\s]+)\)$/.exec(t);
            runs.push([mm ? mm[1] : t, C.link]);
        } else {
            // *a* and _a_ are italic only at word boundaries: city_layout_py and 2*3*4 stay as written.
            const before = m.index > 0 ? s[m.index - 1] : "", after = s[m.index + t.length] || "";
            runs.push(/\w/.test(before) || /\w/.test(after) ? [t, null] : [t.slice(1, -1), C.i]);
        }
        last = m.index + t.length;
    }
    if (last < s.length) runs.push([s.slice(last), null]);
    const words = [];
    runs.forEach((run) => {
        (run[0].match(/\S+|\s+/g) || []).forEach((piece) => {
            if (/^\s+$/.test(piece)) { if (words.length) words[words.length - 1].space = true; }
            else words.push({ t: piece, style: run[1], space: false });
        });
    });
    // A word's following space is a hard space inside it (Gameface drops a leading space in a text item).
    return h("div", { style: FLOW }, words.map((w, i) => h("span", { key: i, style: w.style }, w.space ? w.t + " " : w.t)));
}

const IS_ITEM = /^\s*([-*]|\d+\.)\s+/;
const IS_HEAD = /^(#{1,4})\s+(.*)$/;
const IS_RULE = /^\s*(---|\*\*\*)\s*$/;
const IS_PIC = /^!\[([^\]]*)\]\(([^)\s]+)\)\s*$/;
const IS_ROW = /^\s*\|/;
const IS_QUOTE = /^\s*>/;

function startsBlock(line) {
    return IS_HEAD.test(line) || IS_RULE.test(line) || IS_PIC.test(line.trim()) || IS_ROW.test(line) || IS_QUOTE.test(line) || IS_ITEM.test(line);
}

function Markdown(props) {
    const { b, ctx } = props;
    const raw = str(props.text);
    const text = take(b, raw, LIMIT.body);
    const lines = (text.length < raw.length ? text + "\n\n> This page is longer than the journal panel shows; the rest is cut off." : text).replace(/\r/g, "").split("\n");
    const blocks = [];
    let i = 0, k = 0;
    while (i < lines.length) {
        const line = lines[i];
        if (!line.trim()) { i++; continue; }
        let m;
        if ((m = IS_HEAD.exec(line))) {
            blocks.push(h("div", { key: k++, style: m[1].length === 1 ? C.h1 : m[1].length === 2 ? C.h2 : C.h3 }, markup(m[2])));
            i++;
        } else if (IS_RULE.test(line)) {
            blocks.push(h("div", { key: k++, style: C.hr }));
            i++;
        } else if ((m = IS_PIC.exec(line.trim()))) {
            blocks.push(h(Picture, { key: k++, b, ctx, file: m[2], caption: m[1] }));
            i++;
        } else if (IS_ROW.test(line)) {
            const rows = [];
            while (i < lines.length && IS_ROW.test(lines[i])) rows.push(lines[i++]);
            blocks.push(h(Table, { key: k++, rows }));
        } else if (IS_QUOTE.test(line)) {
            const q = [];
            while (i < lines.length && IS_QUOTE.test(lines[i])) q.push(lines[i++].replace(/^\s*>\s?/, ""));
            blocks.push(h("div", { key: k++, style: C.quote }, markup(q.join(" "))));
        } else if (IS_ITEM.test(line)) {
            const items = [];
            while (i < lines.length && IS_ITEM.test(lines[i])) {
                const mm = /^(\s*)([-*]|\d+\.)\s+(.*)$/.exec(lines[i++]);
                let body = mm[3];
                while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !IS_ITEM.test(lines[i])) body += " " + lines[i++].trim();
                items.push({ indent: mm[1].length, mark: mm[2], body });
            }
            items.forEach((it) => {
                let mark = /\d/.test(it.mark) ? it.mark : "•";
                let body = it.body;
                const cb = /^\[( |x|X)\]\s+(.*)$/.exec(body);
                if (cb) { mark = cb[1] === " " ? "☐" : "☑"; body = cb[2]; }
                blocks.push(h("div", { key: k++, style: { ...C.li, marginLeft: Math.min(3, Math.floor(it.indent / 2)) * 16 + "rem" } },
                    h("div", { style: /\d/.test(mark) ? { ...C.bullet, width: "24rem" } : C.bullet }, mark),
                    h("div", { style: C.liBody }, markup(body))));
            });
        } else {
            const p = [lines[i++].trim()];
            while (i < lines.length && lines[i].trim() && !startsBlock(lines[i])) p.push(lines[i++].trim());
            blocks.push(h("div", { key: k++, style: C.p }, markup(p.join(" "))));
        }
    }
    return h("div", null, blocks);
}

// The second row is the |---|---| line under the header when every cell is dashes (with optional colons).
const SEPARATOR = /^:?-+:?$/;

function Table(props) {
    const cells = (row) => row.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
    const rows = props.rows.map(cells).filter((r, i) => !(i === 1 && r.every((c) => SEPARATOR.test(c))));
    return h("div", { style: C.table }, rows.map((r, ri) => h("div", { key: ri, style: ri === 0 ? C.trHead : C.tr },
        r.map((c, ci) => h("div", { key: ci, style: ci === 0 ? C.td1 : C.td }, markup(c))))));
}

// Pictures come from the journal's images folder, at the sizes the mod read from the files (ctx.sizes), so the panel can
// lay them out before they load (Gameface wants a height). Click to see one large.
function Picture(props) {
    const { b, ctx, file, caption } = props;
    const size = PICTURE_NAME.test(str(file)) ? own(ctx.sizes, file) : undefined;
    const known = Array.isArray(size) && size[0] > 0 && size[1] > 0;
    if (!known || size[0] * size[1] > b.pixels) return h("div", { style: C.dim }, "(picture not shown: " + take(b, caption || file, 80) + ")");
    b.pixels -= size[0] * size[1];
    const s = Math.min(bodyW / size[0], bodyW * PICTURE_TALL / size[1]);
    const w = Math.round(size[0] * s), hgt = Math.round(size[1] * s);
    const src = ctx.base + file;
    const text = take(b, caption, 200);
    return h("div", { style: { marginTop: "8rem" } },
        h("img", { src, style: { width: w + "rem", height: hgt + "rem", borderRadius: "3rem" }, onClick: () => ctx.zoom({ src, size, caption: text }) }),
        text ? h("div", { style: C.caption }, text + "  ·  click to enlarge") : null);
}

function Viewer(props) {
    const z = props.image;
    if (!z) return null;
    const s = Math.min(1700 / z.size[0], 880 / z.size[1]);
    return h("div", { style: C.viewer, onClick: props.onClose },
        h("img", { src: z.src, style: { width: Math.round(z.size[0] * s) + "rem", height: Math.round(z.size[1] * s) + "rem" } }),
        h("div", { style: { ...C.caption, fontSize: "15rem", marginTop: "8rem" } }, (z.caption ? z.caption + "  ·  " : "") + "click anywhere to close"));
}

// ---------- merging the manager's journal with the Mayor's own changes ----------

// The Mayor's tick or status counts unless the manager changed that same step or status after it
// (journal.py stamps "changed" / "statusChanged" when the manager's value changes, or when the manager forces it).
// A tie goes to the Mayor. journal.py's mayor_done and mayor_status apply the same rule (tests/merge_cases.json).
const stamp = (x) => (typeof x === "string" ? x : "");
const newer = (mine, theirs) => !!obj(mine) && stamp(mine.at) >= stamp(theirs);

function stepDone(mayor, key, step) {
    const t = own(mayor.ticks, key);
    return newer(t, step.changed) ? t.done === true : step.done === true;
}

function projectStatus(mayor, p) {
    const s = own(mayor.status, str(p.id));
    if (newer(s, p.statusChanged) && own(STATUS, s.status)) return { status: s.status, byMayor: true };
    return { status: own(STATUS, p.status) ? p.status : "active", byMayor: false };
}

function Chip(props) {
    const s = own(STATUS, props.status) || STATUS.active;
    return h("div", { style: { ...C.chip, backgroundColor: s.color } }, s.label + (props.byMayor ? " (you)" : ""));
}

/** A checklist line; text and sub are already taken from the page's budget. */
function Check(props) {
    return h("div", { style: C.check, onClick: props.onToggle },
        h("div", { style: props.done ? C.boxOn : C.box }, props.done ? "✓" : ""),
        h("div", { style: props.done ? C.checkDone : C.checkText }, props.text,
            props.sub ? h("div", { style: C.small }, props.sub) : null));
}

const section = (key, text) => h("div", { key, style: C.section }, text);

// ---------- tabs ----------

// Today: the manager's briefing, what's still open from the last one, and the next step of every active project,
// so nothing quietly drops off the list.
function TodayTab(props) {
    const { j, mayor, ctx, onOpenProject } = props;
    const b = budget();
    const br = obj(j.briefing);
    const projects = objs(j.projects);
    const byId = new Map(projects.map((p) => [str(p.id), p]));
    const taskCheck = (bid, t) => {
        const key = taskKey(bid, t.id);
        const isDone = stepDone(mayor, key, t);
        const p = t.project ? byId.get(str(t.project)) : null;
        const sub = [take(b, t.note), p ? "Project: " + take(b, p.title) : ""].filter((x) => x).join("  ·  ");
        return h(Check, { key, done: isDone, text: inline(b, t.text), sub, onToggle: () => trigger("tick", key, !isDone) });
    };
    const out = [];
    const tasks = br ? objs(br.tasks) : [];
    if (br) {
        const done = tasks.filter((t) => stepDone(mayor, taskKey(br.id, t.id), t)).length;
        out.push(h("div", { key: "t", style: C.h1 }, take(b, br.title) || "Briefing"));
        if (br.date) out.push(h("div", { key: "d", style: C.small }, take(b, br.date)));
        if (br.summary) out.push(h("div", { key: "s", style: C.p }, inline(b, br.summary)));
        if (tasks.length) out.push(section("ls", `Today's list · ${done} of ${tasks.length} done`));
        tasks.forEach((t) => out.push(taskCheck(br.id, t)));
    } else if (!str(j.manager) && !projects.length) {
        // A journal started in game, with no City Manager yet: what it is, and the one step to get one.
        out.push(h("div", { key: "gs", style: C.h1 }, "Your journal is ready"));
        out.push(h("div", { key: "g1", style: C.p }, "On its own it's a notebook: write notes on the Notes tab as you play, and answer the Wrap-up when you're done."));
        out.push(section("gm", "Want a City Manager to plan with you?"));
        out.push(h("div", { key: "g2", style: C.p }, "The journal takes a snapshot of your city by itself, and that's what the City Manager reads. Save, go back to the main menu or close the game, then in Claude Code type:"));
        out.push(h("div", { key: "g3", style: C.command }, COMMAND));
        out.push(h("div", { key: "g4", style: C.small }, "It needs the City Manager plugin for Claude Code: the mod's page says how to install it."));
    } else {
        out.push(h("div", { key: "nb", style: C.dim }, "No briefing yet. Before you play, ask the City Manager for one: in Claude Code, type " + COMMAND + "."));
    }
    // A task the new briefing carries on (its "from") shows only there, not twice.
    const prev = objs(j.briefings)[0];
    const carriedOn = new Set(tasks.map((t) => str(t.from)).filter((x) => x));
    const carried = prev ? objs(prev.tasks).filter((t) => !stepDone(mayor, taskKey(prev.id, t.id), t) && !carriedOn.has(str(prev.id) + "/" + str(t.id))) : [];
    if (carried.length) {
        out.push(section("cs", `Still open from ${take(b, prev.title) || "last time"} · ${carried.length}`));
        carried.forEach((t) => out.push(taskCheck(prev.id, t)));
    }
    const plate = projects.filter((p) => projectStatus(mayor, p).status === "active").sort(byPriority)
        .map((p) => ({ p, s: objs(p.steps).find((s) => !stepDone(mayor, stepKey(p.id, s.id), s)) }))
        .filter((x) => x.s).slice(0, 6);
    if (plate.length) {
        out.push(section("ps", "On your plate · the next step of your top projects"));
        plate.forEach(({ p, s }) => {
            const key = stepKey(p.id, s.id);
            out.push(h("div", { key, style: C.row },
                h("div", { style: { flex: 1 } }, h(Check, { done: false, text: inline(b, s.text), sub: take(b, p.title), onToggle: () => trigger("tick", key, true) })),
                h("div", { style: { ...C.button, marginLeft: "6rem", marginRight: 0, marginTop: "6rem" }, onClick: () => onOpenProject(str(p.id)) }, "›")));
        });
    }
    if (br && br.body) out.push(h(Markdown, { key: "body", text: br.body, ctx, b }));
    out.push(more(b));
    return h("div", null, out);
}

// The city snapshot (city.json, written by the mod): when it was last taken, and a button to take one now.
function SnapshotRow(props) {
    const s = obj(obj(props.info) && props.info.snapshot) || {};
    const b = budget();
    const busy = s.busy === true;
    return h("div", null,
        h("div", { style: C.section }, "City snapshot"),
        h("div", { style: C.dim }, busy ? "Taking a snapshot…" : str(s.time) ? `Last taken ${take(b, str(s.time), 40)}.` : "None taken yet."),
        h("div", { style: C.dim }, "It records the roads, buildings and budget for the City Manager's report. It's also taken when you press Done for today and whenever the game saves."),
        str(s.problem) ? h("div", { style: C.warn }, take(b, str(s.problem), 400)) : null,
        h("div", { style: { ...C.row, marginTop: "4rem" } },
            h("div", { style: C.button, onClick: () => { if (!busy) trigger("snapshot"); } }, busy ? "Taking…" : "Take a snapshot")));
}

// City: the manager's notes on the whole city (numbers, the latest map, what's where), the snapshot, then the reports.
function CityTab(props) {
    const { j, ctx, info } = props;
    const b = budget();
    const c = obj(j.cityPage);
    const facts = c ? objs(c.facts) : [];
    return h("div", null,
        c ? [
            h("div", { key: "t", style: C.h1 }, take(b, c.title || j.city)),
            c.date ? h("div", { key: "d", style: C.small }, take(b, c.date)) : null,
            c.summary ? h("div", { key: "s", style: C.p }, inline(b, c.summary)) : null,
            facts.length ? h("div", { key: "f", style: C.table }, facts.map((f, i) => h("div", { key: i, style: C.tr },
                h("div", { style: C.factLabel }, take(b, f.label)),
                h("div", { style: C.factValue }, take(b, f.value)),
                h("div", { style: C.factNote }, inline(b, f.note))))) : null,
            c.body ? h(Markdown, { key: "b", text: c.body, ctx, b }) : null,
            more(b),
        ] : h("div", { style: C.dim }, "No city notes yet. The City Manager writes them with the first report."),
        h(SnapshotRow, { info }),
        h("div", { style: C.hr }),
        h(ReportsTab, { j, ctx }));
}

/** A whole number with thousands separators (Gameface's toLocaleString adds none). */
const digits = (n) => String(Math.round(Math.abs(Number(n) || 0))).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
const signed = (n, unit = "") => (Number(n) < 0 ? "−" : "+") + unit + digits(n);
const km = (n) => { const v = Math.abs(Number(n) || 0); return v >= 10 ? v.toFixed(0) : v.toFixed(1); };
const plural = (n, one, many) => `${digits(n)} ${Math.round(Math.abs(Number(n) || 0)) === 1 ? one : many}`;

/** What changed since the city loaded, from the mod's snapshots (info.session): the lines the Wrap-up shows. */
function sessionLines(sess) {
    const c = obj(sess);
    if (!c || !str(c.asOf)) return [];
    const out = [];
    const n = (v) => Number(v) || 0;
    const pair = (added, removed, what) => {
        if (n(added) < 0.05 && n(removed) < 0.05) return;
        out.push(n(added) >= 0.05 ? `${km(added)} km of new ${what}` + (n(removed) >= 0.05 ? `, ${km(removed)} km removed` : "") : `${km(removed)} km of ${what} removed`);
    };
    pair(c.roadsAddedKm, c.roadsRemovedKm, "road");
    pair(c.railAddedKm, c.railRemovedKm, "track");
    const b = [];
    if (n(c.grew)) b.push(`${plural(c.grew, "new building", "new buildings")} grew`);
    if (n(c.placed)) b.push(`you placed ${digits(c.placed)}`);
    if (n(c.removed)) b.push(`${digits(c.removed)} removed`);
    if (b.length) out.push(b.join(", "));
    if (n(c.population)) out.push(`${signed(c.population)} people`);
    if (n(c.money)) out.push(`money ${signed(c.money, "$")}`);
    if (n(c.tiles) > 0) out.push(plural(c.tiles, "more map tile", "more map tiles"));
    return out.length ? out : ["No changes to the city yet."];
}

function SessionSummary(props) {
    const c = obj(props.session) || {};
    const lines = sessionLines(c);
    return h("div", null,
        h("div", { style: C.section }, "Since you loaded the city"),
        lines.length
            ? [lines.map((t, i) => h("div", { key: i, style: C.li }, h("div", { style: C.bullet }, "•"), h("div", { style: C.liBody }, t))),
               h("div", { key: "asof", style: C.dim }, `As of ${str(c.asOf)}. Done for today brings it up to date.`)]
            : h("div", { style: C.dim }, "This fills in after the game next saves, or when you press Done for today."));
}

const DEBRIEF = [
    ["built", "What did you build or change?"],
    ["issues", "What went wrong, or what bugged you?"],
    ["next", "What do you want to do next time?"],
    ["ask", "Anything for the City Manager to look into?"],
];

// Where this session's wrap-up goes: the briefing's id, or, in a journal without a manager, one per session.
const wrapUpId = (j, info) => str(obj(j.briefing) && j.briefing.id) || "session-" + str(info.sessionStart);

// Wrap-up: filled in before closing the game. The City Manager reads it with the newest save for the report. The panel
// keys it by wrapUpId, so a new briefing arriving mid-session starts a fresh one (the old answers are saved on the way).
function WrapUpTab(props) {
    const { j, mayor, info } = props;
    const b = budget();
    const bid = wrapUpId(j, info);
    const saved = obj(own(mayor.debriefs, bid)) || {};
    const savedAnswers = obj(saved.answers) || {};
    const savedKey = JSON.stringify(savedAnswers);
    const [ans, setAns] = React.useState(savedAnswers);
    const [dirty, setDirty] = React.useState(false);
    React.useEffect(() => { if (!dirty) setAns(savedAnswers); }, [savedKey]);
    const save = () => { trigger("saveDebrief", bid, JSON.stringify(ans)); setDirty(false); };
    // Unsaved answers are saved when the tab goes away (the panel closed, a new briefing came), not only on blur.
    const latest = React.useRef(null);
    latest.current = { ans, dirty, bid };
    React.useEffect(() => () => { const l = latest.current; if (l && l.dirty) trigger("saveDebrief", l.bid, JSON.stringify(l.ans)); }, []);

    // What the Mayor did since this city was loaded.
    const since = str(info.sessionStart);
    const texts = new Map();
    objs(j.projects).forEach((p) => objs(p.steps).forEach((s) => texts.set(stepKey(p.id, s.id), s.text)));
    [obj(j.briefing)].concat(objs(j.briefings)).forEach((bb) => { if (bb) objs(bb.tasks).forEach((t) => texts.set(taskKey(bb.id, t.id), t.text)); });
    const ticks = obj(mayor.ticks) || {};
    const ticked = since ? Object.keys(ticks).filter((k) => obj(ticks[k]) && ticks[k].done === true && stamp(ticks[k].at) >= since).slice(0, LIMIT.items) : [];
    const notes = since ? mayorNotes(mayor).filter((n) => stamp(n.at) >= since) : [];

    return h("div", null,
        h("div", { style: C.h1 }, "Wrap-up"),
        h("div", { style: C.dim }, "Fill this in before you close the game. A line or two is plenty; skip any question."),
        h("div", { style: C.section }, `This session · ${ticked.length} ticked · ${notes.length} note${notes.length === 1 ? "" : "s"}`),
        ticked.length === 0 && notes.length === 0 ? h("div", { style: C.dim }, "Nothing ticked or noted yet this session.") : null,
        ticked.map((k) => h("div", { key: k, style: C.li }, h("div", { style: C.bullet }, "✓"), h("div", { style: C.liBody }, inline(b, texts.get(k) || k)))),
        notes.map((n, i) => h("div", { key: "n" + i, style: C.li }, h("div", { style: C.bullet }, "•"), h("div", { style: C.liBody }, take(b, n.text)))),
        more(b),
        h(SessionSummary, { session: info.session }),
        DEBRIEF.map(([id, q]) => h("div", { key: id },
            h("div", { style: C.section }, q),
            h("textarea", { value: str(ans[id]), maxLength: MAX_ANSWER, style: { ...C.textarea, width: (bodyW - 20) + "rem" },
                onChange: (e) => { setAns({ ...ans, [id]: e.target.value.slice(0, MAX_ANSWER) }); setDirty(true); },
                onBlur: () => { if (dirty) save(); } }))),
        h("div", { style: { ...C.row, marginTop: "10rem" } },
            h("div", { style: C.button, onClick: save }, dirty ? "Save" : "Saved"),
            saved.done === true
                ? h("div", { style: C.button, onClick: () => trigger("finishDebrief", bid, false) }, "Reopen")
                : h("div", { style: C.primary, onClick: () => { save(); trigger("finishDebrief", bid, true); } }, "Done for today")),
        saved.done === true ? h("div", { style: C.quote },
            markup(`Wrap-up saved ${when(saved.at)}. Now **save your game**, close it, and ask the City Manager for a report.`)) : null);
}

function ProjectList(props) {
    const { j, mayor, onOpen } = props;
    const b = budget();
    const projects = objs(j.projects).map((p) => ({ p, st: projectStatus(mayor, p) }));
    if (projects.length === 0) return h("div", { style: C.dim }, "No projects yet.");
    const out = [];
    STATUS_ORDER.forEach((s) => {
        const group = projects.filter((x) => x.st.status === s).sort((x, y) => byPriority(x.p, y.p));
        if (group.length === 0) return;
        out.push(section("g" + s, STATUS[s].label + " · " + group.length));
        group.forEach(({ p }, i) => {
            const steps = objs(p.steps);
            const done = steps.filter((st) => stepDone(mayor, stepKey(p.id, st.id), st)).length;
            out.push(h("div", { key: s + i, style: C.card, onClick: () => onOpen(str(p.id)) },
                h("div", { style: C.row },
                    h("div", { style: C.cardTitle }, take(b, p.title)),
                    p.scale ? h("div", { style: C.tag }, own(SCALE, p.scale) || take(b, p.scale, 40)) : null,
                    steps.length ? h("div", { style: C.tag }, `${done}/${steps.length}`) : null),
                p.summary ? h("div", { style: C.dim }, inline(b, p.summary)) : null));
        });
    });
    out.push(more(b));
    return h("div", null, out);
}

function NoteInput(props) {
    const [text, setText] = React.useState("");
    const [here, setHere] = React.useState(false);
    const save = () => { if (text.trim()) { trigger("addNote", str(props.project), text, here); setText(""); } };
    return h("div", { style: { marginTop: "8rem" } },
        h("div", { style: C.row },
            h("input", { type: "text", value: text, maxLength: MAX_NOTE, placeholder: props.placeholder || "Add a note for the City Manager…", style: C.input,
                onChange: (e) => setText(e.target.value.slice(0, MAX_NOTE)), onKeyDown: (e) => { if (e.key === "Enter" || e.keyCode === 13) save(); } }),
            h("div", { style: C.primary, onClick: save }, "Add")),
        h("div", { style: { ...C.row, marginTop: "5rem" }, onClick: () => setHere(!here) },
            h("div", { style: here ? C.boxOn : C.box }, here ? "✓" : ""),
            h("div", { style: C.small }, "Pin to where the camera is looking")));
}

/** The Mayor's notes with the manager's replies, as MayorNote elements; their text is taken from the page's budget here,
 *  because a MayorNote can redraw on its own (its delete confirmation). */
function noteList(b, j, notes, titles) {
    return notes.map((n) => {
        const r = obj(own(j.replies, str(n.id)));
        return h(MayorNote, { key: str(n.id), note: n, text: take(b, n.text), projectTitle: titles ? take(b, titles.get(str(n.project)), 200) : "",
            reply: r ? { date: when(take(b, r.date, 40)), text: inline(b, r.text, LIMIT.line * 2) } : null });
    });
}

function MayorNote(props) {
    const { note: n, reply } = props;
    const [confirm, setConfirm] = React.useState(false);
    const small = { padding: "2rem 8rem" };
    const where = obj(n.where);
    return h("div", { style: C.noteMayor },
        h("div", { style: C.row },
            h("div", { style: { flex: 1, ...C.small } }, "You · " + when(n.at) + (n.gameDate ? " · in game " + str(n.gameDate).slice(0, 40) : "") + (props.projectTitle ? " · " + props.projectTitle : "")),
            where && !confirm ? h("div", { style: { ...C.button, ...small }, onClick: () => trigger("flyTo", Number(where.x), Number(where.z), Number(where.zoom) || 0) }, "Go") : null,
            confirm
                ? [h("div", { key: "d", style: { ...C.danger, ...small }, onClick: () => trigger("deleteNote", str(n.id)) }, "Delete"),
                    h("div", { key: "k", style: { ...C.button, ...small, marginRight: 0 }, onClick: () => setConfirm(false) }, "Keep")]
                : h("div", { style: { ...C.button, ...small, marginRight: 0 }, onClick: () => setConfirm(true) }, "×")),
        h("div", { style: { marginTop: "2rem" } }, props.text),
        reply ? h("div", { style: C.reply },
            h("div", { style: C.small }, "City Manager" + (reply.date ? " · " + reply.date : "")),
            h("div", { style: { marginTop: "2rem" } }, reply.text)) : null);
}

function ProjectDetail(props) {
    const { j, mayor, ctx, id, onBack } = props;
    const b = budget();
    const p = objs(j.projects).find((x) => str(x.id) === id);
    const back = h("div", { style: C.back, onClick: onBack }, "‹ All projects");
    if (!p) return h("div", null, back, h("div", { style: C.dim }, "This project is no longer in the journal."));
    const st = projectStatus(mayor, p);
    const where = obj(p.where);
    const plans = objs(p.plans), steps = objs(p.steps);
    const notes = mayorNotes(mayor).filter((n) => str(n.project) === id).reverse();
    return h("div", null,
        back,
        h("div", { style: C.row },
            h("div", { style: { flex: 1, ...C.h1, marginTop: "2rem" } }, take(b, p.title)),
            p.scale ? h("div", { style: C.tag }, own(SCALE, p.scale) || take(b, p.scale, 40)) : null,
            h(Chip, st)),
        p.updated ? h("div", { style: C.small }, "City Manager's last update " + when(take(b, p.updated, 40))) : null,
        p.summary ? h("div", { style: C.p }, inline(b, p.summary)) : null,
        where ? h("div", { style: { ...C.row, marginTop: "8rem" } },
            h("div", { style: C.button, onClick: () => trigger("flyTo", Number(where.x), Number(where.z), Number(where.zoom) || 0) },
                "Show on map" + (where.label ? ": " + take(b, where.label, 80) : ""))) : null,
        section("st", "Your status"),
        h("div", { style: { ...C.row, marginTop: "4rem" } }, STATUS_ORDER.map((s) =>
            h("div", { key: s, style: st.status === s ? C.buttonOn : C.button, onClick: () => trigger("setStatus", id, s) }, STATUS[s].label))),
        st.byMayor ? h("div", { style: { ...C.small, ...C.link, marginTop: "4rem" }, onClick: () => trigger("setStatus", id, "") },
            "Use the City Manager's status (" + (own(STATUS, p.status) || STATUS.active).label + ") instead") : null,
        plans.length ? section("pl", "Planner") : null,
        plans.map((pl, i) => h("div", { key: i, style: C.plan },
            pl.kind === "draft"
                ? [h("div", { key: "a" }, markup("**Planning Draft:** " + take(b, pl.name))),
                    arr(pl.layers).length ? h("div", { key: "b", style: C.small }, "Layers: " + take(b, arr(pl.layers).map(str).join(" · "))) : null]
                : h("div", { style: C.b }, (pl.kind === "doc" ? "Doc: " : "") + take(b, pl.title || pl.name)),
            pl.note ? h("div", { style: C.small }, take(b, pl.note)) : null,
            pl.kind === "doc" && pl.url ? h("div", { style: C.small }, "On your phone: " + take(b, pl.url).replace(/^https?:\/\//, "")) : null)),
        steps.length ? section("sp", "Steps") : null,
        steps.map((s) => {
            const key = stepKey(p.id, s.id);
            const isDone = stepDone(mayor, key, s);
            const check = h(Check, { key, done: isDone, text: inline(b, s.text), sub: take(b, s.note), onToggle: () => trigger("tick", key, !isDone) });
            const tools = StepTools({ b, ctx, step: s });
            return tools ? h("div", { key }, check, tools) : check;
        }),
        p.body ? h(Markdown, { text: p.body, ctx, b }) : null,
        section("nt", "Notes"),
        h(NoteInput, { project: id, placeholder: "Note on this project…" }),
        noteList(b, j, notes, null),
        objs(p.log).slice().reverse().map((n, i) => h("div", { key: "l" + i, style: C.note },
            h("div", { style: C.small }, "City Manager · " + when(take(b, n.date, 40))), h("div", { style: { marginTop: "2rem" } }, inline(b, n.text)))),
        more(b));
}

// A step's build card: Show on map flies the camera to its place, Picture opens its close-up in the viewer (the picture
// isn't drawn on the page, so it costs the page's picture budget nothing until it's opened).
function StepTools(props) {
    const { b, ctx, step } = props;
    const where = obj(step.where);
    const pic = str(step.picture);
    const size = PICTURE_NAME.test(pic) ? own(ctx.sizes, pic) : undefined;
    const hasPic = Array.isArray(size) && size[0] > 0 && size[1] > 0;
    const placed = where && Number.isFinite(Number(where.x)) && Number.isFinite(Number(where.z));
    if (!placed && !hasPic) return null;
    return h("div", { style: C.stepTools },
        placed ? h("div", { style: C.miniButton, onClick: () => trigger("flyTo", Number(where.x), Number(where.z), Number(where.zoom) || 0) }, "Show on map") : null,
        hasPic ? h("div", { style: C.miniButton, onClick: () => ctx.zoom({ src: ctx.base + pic, size, caption: take(b, step.text, 200) }) }, "Picture") : null);
}

function ReportsTab(props) {
    const { j, ctx } = props;
    const b = budget();
    const [openId, setOpenId] = React.useState(null); // "r:<id>" or "b:<id>": a report and a briefing can share a date id
    const reports = objs(j.reports);
    const past = objs(j.briefings);
    if (openId) {
        const isReport = openId.startsWith("r:");
        const r = (isReport ? reports : past).find((x) => (isReport ? "r:" : "b:") + str(x.id) === openId);
        if (r) {
            const numbers = objs(r.numbers), tasks = objs(r.tasks);
            return h("div", null,
                h("div", { style: C.back, onClick: () => setOpenId(null) }, "‹ All reports"),
                h("div", { style: { ...C.h1, marginTop: "2rem" } }, take(b, r.title)),
                r.date ? h("div", { style: C.small }, take(b, r.date)) : null,
                r.summary ? h("div", { style: C.p }, inline(b, r.summary)) : null,
                numbers.length ? h("div", { style: C.table },
                    h("div", { style: C.trHead }, ["", "Before", "After", "Change"].map((t, i) => h("div", { key: i, style: i === 0 ? C.td1 : C.td }, t))),
                    numbers.map((n, i) => h("div", { key: i, style: C.tr },
                        h("div", { style: C.td1 }, take(b, n.label)),
                        h("div", { style: C.td }, take(b, n.before)),
                        h("div", { style: C.td }, take(b, n.after)),
                        h("div", { style: C.td }, take(b, n.change))))) : null,
                tasks.length ? section("tl", "That session's list") : null,
                tasks.map((t, i) => h("div", { key: i, style: C.li }, h("div", { style: C.bullet }, "•"), h("div", { style: C.liBody }, inline(b, t.text)))),
                r.body ? h(Markdown, { text: r.body, ctx, b }) : null,
                more(b));
        }
    }
    if (reports.length === 0 && past.length === 0) return h("div", { style: C.dim }, "No reports yet. After you play, close the game and ask the City Manager for a recap.");
    const card = (kind) => (r, i) => h("div", { key: kind + i, style: C.card, onClick: () => setOpenId(kind + ":" + str(r.id)) },
        h("div", { style: C.row }, h("div", { style: C.cardTitle }, take(b, r.title)), r.date ? h("div", { style: C.tag }, take(b, r.date, 40)) : null),
        r.summary ? h("div", { style: C.dim }, inline(b, r.summary)) : null);
    return h("div", null,
        reports.length ? section("rs", "Reports from the City Manager") : null,
        reports.map(card("r")),
        past.length ? section("eb", "Earlier briefings") : null,
        past.map(card("b")),
        more(b));
}

function NotesTab(props) {
    const { j, mayor } = props;
    const b = budget();
    const projects = objs(j.projects);
    const [pid, setPid] = React.useState(""); // "" = a general note; the id survives live updates that reorder projects
    const cur = projects.find((p) => str(p.id) === pid) || null;
    const go = (d) => {
        const ids = [""].concat(projects.map((p) => str(p.id)));
        const i = Math.max(0, ids.indexOf(pid));
        setPid(ids[(i + d + ids.length) % ids.length]);
    };
    const titles = new Map(projects.map((p) => [str(p.id), p.title]));
    const notes = mayorNotes(mayor).reverse();
    return h("div", null,
        h("div", { style: C.dim }, "Jot things down while you play: problems, ideas, what you built. The City Manager reads them for the next report."),
        h("div", { style: C.picker },
            h("div", { style: C.arrow, onClick: () => go(-1) }, "◀"),
            h("div", { style: C.pickName }, cur ? "About: " + take(b, cur.title, 200) : "General note"),
            h("div", { style: C.arrow, onClick: () => go(1) }, "▶")),
        h(NoteInput, { project: cur ? pid : "" }),
        section("yn", `Your notes · ${notes.length}`),
        notes.length === 0 ? h("div", { style: C.dim }, "None yet.") : null,
        noteList(b, j, notes, titles),
        more(b));
}

// ---------- the panel ----------

const TABS = ["Today", "Projects", "Notes", "Wrap-up", "City"];

// The game's UI has no error boundary of its own: an exception while drawing a mod's component unmounts the whole UI,
// pause menu included. Anything odd in a journal therefore ends here, as a message in the panel.
class Guard extends React.Component {
    constructor(props) { super(props); this.state = { error: null }; }
    static getDerivedStateFromError(error) { return { error }; }
    componentDidUpdate(prev) {
        const a = prev.resetKeys || [], z = this.props.resetKeys || [];
        if (this.state.error && (a.length !== z.length || a.some((x, i) => x !== z[i]))) this.setState({ error: null });
    }
    render() {
        if (!this.state.error) return this.props.children;
        if (this.props.quiet) return null;
        return h("div", { style: C.panel },
            h("div", { style: C.header }, h("div", { style: C.titleBox }, h("div", { style: C.title }, "City Manager")),
                h("div", { style: C.close, onClick: () => trigger("close") }, "×")),
            h("div", { style: C.warn }, "This journal has something the panel can't show (" + str(this.state.error && this.state.error.message).slice(0, 200) + "). The rest of the game is fine; ask the City Manager to check the journal."));
    }
}

/** The journals list: pick one, start one for this city, or go back to the automatic choice. */
function Chooser(props) {
    const { info, onDone } = props;
    const journals = arr(info.journals).map(str);
    const go = (fn) => () => { fn(); if (onDone) onDone(); };
    return h("div", null,
        h("div", { style: C.p }, info.folder ? `This city uses the journal "${str(info.folder)}".` : `No journal is linked to the city "${str(info.city) || "?"}" yet.`),
        journals.length ? section("j", "Journals") : null,
        journals.map((f) => h("div", { key: f, style: f === info.folder ? { ...C.card, backgroundColor: "rgba(80, 160, 255, 0.35)" } : C.card, onClick: go(() => trigger("pick", f)) }, f)),
        section("or", "Or"),
        h("div", { style: { ...C.row, marginTop: "4rem" } },
            h("div", { style: C.button, onClick: go(() => trigger("create")) }, "Start a new journal for this city"),
            info.folder ? h("div", { style: C.button, onClick: go(() => trigger("unpick")) }, "Use the automatic choice") : null),
        h("div", { style: C.dim }, "A journal keeps your notes and wrap-ups even without a City Manager. Journals live in ModsData/CityManager."),
        onDone ? h("div", { style: { ...C.back, marginTop: "10rem" }, onClick: onDone }, "‹ Back") : null);
}

/** The page for a tab. */
function tabPage(tab, s) {
    const { j, mayor, info, ctx, projectId, setProjectId, openProject } = s;
    if (tab === 0) return h(TodayTab, { j, mayor, ctx, onOpenProject: openProject });
    if (tab === 1) return projectId ? h(ProjectDetail, { j, mayor, ctx, id: projectId, onBack: () => setProjectId(null) }) : h(ProjectList, { j, mayor, onOpen: setProjectId });
    if (tab === 2) return h(NotesTab, { j, mayor });
    if (tab === 3) return h(WrapUpTab, { key: wrapUpId(j, info), j, mayor, info });
    return h(CityTab, { j, ctx, info });
}

// ---------- the window: docked (its usual place) or floating, moved and resized by the Mayor ----------
// Sizes are in rem: the game's UI is 1920 x 1080 rem on a 16:9 screen; taller screens (the iPad's 4:3) scale by width
// and wider ones by height. A floating window is remembered per screen shape and always kept on screen, clear of the
// game's buttons at the top left and its toolbar at the bottom. Dragging uses a full-screen layer while the mouse is down,
// because Gameface fires no pointer capture or native drag events.
const WIN = { minW: 420, maxW: 1400, minBodyH: 220, top: 64, bottom: 110, header: 120, dockRight: 12, dockTop: 110, edge: 10, still: 3 };
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const fin = (v, d) => (typeof v === "number" && isFinite(v) ? v : d);

/** The screen in px and rem, and how many px one rem is. */
function screenSize() {
    const w = fin(window.innerWidth, 1920) || 1920, h = fin(window.innerHeight, 1080) || 1080;
    const k = Math.min(w / 1920, h / 1080) || 1;
    return { px: [w, h], w: w / k, h: h / k, k };
}

/** The key a layout is remembered under: the screen's shape, "1.78" (16:9) or "1.33" (4:3). */
const screenKey = (scr) => (scr.px[0] / scr.px[1]).toFixed(2);

/** A layout that fits the screen. Docked keeps the usual place and size; floating stays on screen. */
function fitLayout(l, scr) {
    const o = obj(l) || {};
    const w = clamp(fin(o.w, PANEL_W), WIN.minW, Math.max(WIN.minW, Math.min(WIN.maxW, scr.w)));
    const roomH = scr.h - WIN.top - WIN.bottom - WIN.header;
    const bodyH = clamp(fin(o.bodyH, BODY_H), WIN.minBodyH, Math.max(WIN.minBodyH, roomH));
    const x = clamp(fin(o.x, scr.w - w - WIN.dockRight), 0, Math.max(0, scr.w - w));
    const y = clamp(fin(o.y, WIN.dockTop), WIN.top, Math.max(WIN.top, scr.h - WIN.bottom - WIN.header - bodyH));
    return { mode: o.mode === "floating" ? "floating" : "docked", x, y, w, bodyH };
}

/** The layout after dragging the title ("move") or an edge or corner ("l", "r", "b", "bl", "br") by dx, dy rem. */
function dragged(start, kind, dx, dy, scr) {
    let { x, y, w, bodyH } = start;
    if (kind === "move") {
        x += dx;
        y += dy;
    }
    // Resizing stops at the screen's edge and the bottom toolbar; only moving shifts the window.
    if (kind.includes("r")) w = Math.min(w + dx, scr.w - x);
    if (kind.includes("l")) {
        w = clamp(start.w - dx, WIN.minW, Math.min(WIN.maxW, start.x + start.w));
        x = start.x + start.w - w;   // the right edge stays where it was
    }
    if (kind.includes("b")) bodyH = Math.min(bodyH + dy, scr.h - WIN.bottom - WIN.header - y);
    return fitLayout({ mode: "floating", x, y, w, bodyH }, scr);
}

/** The panel's own style for a layout. */
function panelStyle(lay) {
    if (lay.mode !== "floating") return { ...C.panel, width: PANEL_W + "rem" };
    const s = { ...C.panel, left: lay.x + "rem", top: lay.y + "rem", width: lay.w + "rem" };
    delete s.right;
    return s;
}

/** The edges and corners a floating window is resized from, with a grip in the bottom corners. */
function ResizeHandles(props) {
    const start = props.onStart;
    const e = WIN.edge;
    const grip = (kind) => h("div", { style: { ...C.grip, ...(kind === "br"
        ? { right: "9rem", borderRight: "2rem solid rgba(255,255,255,0.65)" }
        : { left: "9rem", borderLeft: "2rem solid rgba(255,255,255,0.65)" }) } });
    const handle = (kind, style, corner) => h("div", { key: kind, style: { position: "absolute", ...style },
        onMouseDown: (ev) => start(kind, ev) }, corner ? grip(kind) : null);
    return [
        handle("l", { left: -e / 2 + "rem", top: "30rem", bottom: "20rem", width: e + "rem" }),
        handle("r", { right: -e / 2 + "rem", top: "30rem", bottom: "20rem", width: e + "rem" }),
        handle("b", { left: "20rem", right: "20rem", bottom: -e / 2 + "rem", height: e + "rem" }),
        handle("bl", { left: -e / 2 + "rem", bottom: -e / 2 + "rem", width: "22rem", height: "22rem" }, true),
        handle("br", { right: -e / 2 + "rem", bottom: -e / 2 + "rem", width: "22rem", height: "22rem" }, true),
    ];
}

// The panel stays mounted while closed (it keeps its tab and open project) and draws nothing then; the tab's contents
// unmount, so the Wrap-up tab saves unsaved answers when the panel closes.
function Panel() {
    textK = fontScale();   // read on every draw: the player may have changed it in Options since
    const open = api.useValue(open$);
    const journalStr = api.useValue(journal$), mayorStr = api.useValue(mayor$), infoStr = api.useValue(info$);
    const j = React.useMemo(() => obj(parse(journalStr, null)), [journalStr]);
    const mayor = React.useMemo(() => obj(parse(mayorStr, null)) || {}, [mayorStr]);
    const info = React.useMemo(() => obj(parse(infoStr, null)) || {}, [infoStr]);
    const [tab, setTab] = React.useState(0);
    const [projectId, setProjectId] = React.useState(null);
    const [image, setImage] = React.useState(null);
    const [choosing, setChoosing] = React.useState(false);
    const [saved, setSaved] = React.useState(null);   // the Mayor's layouts as just changed, until the mod's copy catches up
    const [drag, setDrag] = React.useState(null);     // { kind, x0, y0, start, now } while the mouse is down

    // Opening the panel counts as reading the manager's latest update.
    const updated = j ? str(j.updated) : "";
    React.useEffect(() => { if (open && updated && mayor.seen !== updated) trigger("markSeen", updated); }, [open, updated, mayor.seen]);
    if (!open) return null;

    // Where the window is: remembered per screen shape, always fitted to the screen as it is now.
    const scr = screenSize();
    const key = screenKey(scr);
    const layouts = obj(saved) || obj(info.layout) || {};
    const lay = drag ? drag.now : fitLayout(own(layouts, key), scr);
    const size = lay.mode === "floating" ? lay : { w: PANEL_W, bodyH: BODY_H };   // docked: the usual size, whatever was saved
    bodyW = size.w - 42;
    const remember = (next) => {
        const all = { ...layouts, [key]: next };
        setSaved(all);
        trigger("saveLayout", JSON.stringify(all));
    };
    const startDrag = (kind, ev) => {
        if (lay.mode !== "floating" || (ev && ev.button > 0)) return;
        if (ev && ev.stopPropagation) ev.stopPropagation();
        setDrag({ kind, x0: fin(ev && ev.screenX, 0), y0: fin(ev && ev.screenY, 0), start: lay, now: lay });
    };
    const moveDrag = (ev) => {
        if (!drag) return;
        const dx = (fin(ev.screenX, drag.x0) - drag.x0) / scr.k, dy = (fin(ev.screenY, drag.y0) - drag.y0) / scr.k;
        setDrag({ ...drag, now: dragged(drag.start, drag.kind, dx, dy, scr) });
    };
    const endDrag = () => {
        if (!drag) return;
        const moved = Math.abs(drag.now.x - drag.start.x) + Math.abs(drag.now.y - drag.start.y) + Math.abs(drag.now.w - drag.start.w) + Math.abs(drag.now.bodyH - drag.start.bodyH);
        if (moved >= WIN.still) remember(drag.now);
        setDrag(null);
    };
    const toggleDock = () => remember({ ...lay, mode: lay.mode === "floating" ? "docked" : "floating" });
    const style = panelStyle(lay);

    const hb = budget();
    const header = h("div", { style: C.header },
        h("div", { style: C.titleBox },
            h("div", { style: lay.mode === "floating" ? { ...C.title, cursor: "move" } : C.title, onMouseDown: (ev) => startDrag("move", ev) },
                "City Manager" + (j && j.city ? " · " + take(hb, j.city, 80) : info.city ? " · " + take(hb, info.city, 80) : "")),
            h("div", { style: C.sub }, j ? `From ${take(hb, j.manager, 80) || "the City Manager"} · updated ${when(take(hb, j.updated, 40)) || str(info.fileTime) || "?"}` : ""),
            j ? h("div", { style: { ...C.sub, ...C.link }, onClick: () => setChoosing(!choosing) }, choosing ? "‹ Back to the journal" : "Change journal") : null),
        h("div", { style: C.dockButton, onClick: toggleDock }, lay.mode === "floating" ? "Dock" : "Float"),
        h("div", { style: C.close, onClick: () => trigger("close") }, "×"));
    const warnings = [info.error, info.mayorProblem].filter((x) => x).map((x, i) => h("div", { key: "w" + i, style: C.warn }, take(hb, x, 400)));

    const handles = lay.mode === "floating" ? h(ResizeHandles, { onStart: startDrag }) : null;
    const dragLayer = drag ? h("div", { style: C.dragLayer, onMouseMove: moveDrag, onMouseUp: endDrag, onMouseLeave: endDrag }) : null;
    const frame = (...children) => h("div", { style: { position: "absolute", left: 0, top: 0, width: "100%", height: "100%", pointerEvents: "none" } },
        h("div", { style }, ...children, handles), dragLayer);
    if (!j || choosing) return frame(header, warnings, h(Chooser, { info, onDone: j ? () => setChoosing(false) : null }));

    const ctx = { base: str(info.host) + encodeURIComponent(str(info.folder)) + "/images/", sizes: obj(info.pictures) || {}, zoom: setImage };
    const openProject = (id) => { setTab(1); setProjectId(id); };
    const counts = ["", objs(j.projects).length, objs(mayor.notes, Infinity).length, "", ""].map((n) => (n ? ` (${n})` : ""));
    const Scroll = ui.Scrollable || "div";
    return h("div", { style: { position: "absolute", left: 0, top: 0, width: "100%", height: "100%", pointerEvents: "none" } },
        h("div", { style },
            header,
            warnings,
            h("div", { style: C.tabs }, TABS.map((t, i) => h("div", { key: t, style: { ...(tab === i ? C.tabOn : C.tab), ...(i === TABS.length - 1 ? { marginRight: 0 } : null) },
                onClick: () => { setTab(i); if (i === 1) setProjectId(null); } }, t + counts[i]))),
            h(Scroll, { vertical: true, trackVisibility: "scrollable", style: { height: size.bodyH + "rem", width: (size.w - 28) + "rem" }, key: tab + ":" + (projectId || "") },
                h("div", { style: { ...C.inner, width: bodyW + "rem" } }, tabPage(tab, { j, mayor, info, ctx, projectId, setProjectId, openProject }))),
            handles),
        dragLayer,
        h(Viewer, { image, onClose: () => setImage(null) }));
}

function JournalButton() {
    const open = api.useValue(open$);
    const fresh = api.useValue(fresh$);
    return h(ui.Button, {
        variant: "floating", selected: open, src: fresh ? ICON_NEW : ICON,
        tooltipLabel: fresh ? "City Manager: new update from the City Manager (Ctrl+J)" : "City Manager: today's briefing, projects, notes, wrap-up and city notes (Ctrl+J)",
        onSelect: () => trigger("toggle"),
    });
}

// A new journal, or closing and reopening the panel, clears an error and tries again.
const GuardedPanel = () => h(Guard, { resetKeys: [api.useValue(journal$), api.useValue(open$)] }, h(Panel));
const GuardedButton = () => h(Guard, { quiet: true }, h(JournalButton));

const register = (moduleRegistry) => {
    moduleRegistry.append("GameTopLeft", GuardedButton);
    moduleRegistry.append("Game", GuardedPanel);
};

const hasCSS = false;
// For the offline tests (tests/ui.test.mjs); the game only uses the default export.
const __test = { markup, take, budget, Markdown, Table, Picture, stepDone, projectStatus, newer, parse, arr, objs, own, when, wrapUpId, tabPage,
    TodayTab, ProjectList, ProjectDetail, NotesTab, WrapUpTab, CityTab, SnapshotRow, SessionSummary, sessionLines, digits, ReportsTab,
    WIN, fitLayout, dragged, panelStyle, screenKey, ResizeHandles, Panel, LIMIT, PICTURE_NAME, Guard, Chooser, textScaled, fontScale, StepTools };
export { hasCSS, __test, register as default };
