// Offline tests for the panel (Markdown, pictures, the page budget, merging the Mayor's ticks with the manager's, and
// every tab drawn from a hostile journal). Run: node --test tests/ui.test.mjs (Node 18+). React and the game's cs2/*
// modules are stubbed: elements become plain objects and hooks return their first value, so the tests look at what the
// panel would draw without a browser.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const h = (type, props, ...children) => ({ type, props: props || {}, children: children.flat(Infinity).filter((c) => c !== null && c !== undefined && c !== false) });
class Component { constructor(props) { this.props = props; } setState(s) { Object.assign(this.state, s); } }
globalThis.window = {
    React: { createElement: h, useState: (v) => [v, () => {}], useEffect: () => {}, useRef: () => ({ current: null }), useMemo: (f) => f(), Component },
    "cs2/api": { bindValue: () => ({}), trigger: () => {}, useValue: () => null },
    "cs2/ui": {},
};
const { __test: T } = await import("../ui/CityManager.mjs");
const CASES = JSON.parse(readFileSync(new URL("../../format/merge_cases.json", import.meta.url), "utf8"));

/** Expands components (function element types) into what they draw, like React would. */
const render = (n) => {
    if (!n || typeof n !== "object") return n;
    if (typeof n.type === "function") {
        const props = { ...n.props, children: n.children };
        const t = n.type;
        return render(t.prototype && t.prototype.render ? new t(props).render() : t(props));
    }
    return { ...n, children: (n.children || []).map(render) };
};
/** All text drawn under an element, as one string. */
const text = (n) => (n == null ? "" : typeof n === "string" || typeof n === "number" ? String(n) : (render(n).children || []).map(text).join(""));
/** Every element of a type (a tag name or a component function) under n, before expanding components. */
const find = (n, type, out = []) => {
    if (n && typeof n === "object") {
        if (n.type === type) out.push(n);
        (n.children || []).forEach((c) => find(c, type, out));
    }
    return out;
};
/** How much an expanded tree draws. */
const stats = (n, s = { elements: 0, chars: 0 }) => {
    if (n == null) return s;
    if (typeof n === "string" || typeof n === "number") { s.chars += String(n).length; return s; }
    s.elements++;
    (n.children || []).forEach((c) => stats(c, s));
    return s;
};
const plain = (s) => s.replace(/\u00a0/g, " ");
const CTX = { base: "coui://citymanager/j/images/", sizes: {}, zoom: () => {} };
const md = (src, ctx = CTX) => T.Markdown({ text: src, ctx, b: T.budget() });

test("plain text stays a single string (Gameface wraps it natively)", () => {
    assert.equal(T.markup("just words here"), "just words here");
});

test("marked-up text becomes one flex item per word, spaces kept as hard spaces", () => {
    const flow = T.markup("Take **Depot Avenue**, then `B2`.");
    const words = flow.children.map(text);
    assert.deepEqual(words, ["Take ", "Depot ", "Avenue", ", ", "then ", "B2", "."]);
    assert.equal(flow.children[1].props.style, T.markup("**x** y").children[0].props.style);
});

test("links show their text only (nothing is clickable)", () => {
    const flow = T.markup("see [the doc](https://example.com/x) now");
    assert.equal(plain(text(flow)), "see the doc now");
    assert.equal(JSON.stringify(flow).includes("https://"), false);
});

test("Markdown blocks: headings, lists, nested lists, check items, tables, quotes, rules, paragraphs", () => {
    const out = md(["# Title", "", "Para one", "continues.", "", "- a", "  - nested", "- [x] done", "1. first", "", "| A | B |", "|---|---|", "| 1 | 2 |", "", "> callout", "", "---", "tail"].join("\n"));
    const all = text(out);
    for (const s of ["Title", "Para one continues.", "a", "nested", "☑", "done", "1.", "first", "A", "B", "1", "2", "callout", "tail"]) assert.ok(all.includes(s), s);
    assert.equal(all.includes("|---|"), false);
    assert.equal(find(out, T.Table).length, 1);
});

test("table rows that start with dashes are kept; only a dashes-only second row is the separator", () => {
    const all = text(md("| Flag | Meaning |\n| :--- | ---: |\n| --all | everything |\n| -- | none |"));
    for (const s of ["Flag", "--all", "everything", "--", "none"]) assert.ok(all.includes(s), s);
    assert.equal(all.includes(":---"), false);
    assert.ok(text(md("| a | b |\n| -- | x |")).includes("x"));
});

test("a table row of spaces stays fast (no backtracking)", () => {
    const t0 = performance.now();
    md("|" + " ".repeat(29990) + "|\n" + "| " + " ".repeat(29990));
    assert.ok(performance.now() - t0 < 100);
});

test("a picture line becomes a Picture; half-written picture syntax stays text (no hang, no extra pictures)", () => {
    const out = md("![Map](city-map.png)\n![broken\n!\n![a](b) trailing words");
    assert.equal(find(out, T.Picture).length, 1);
    assert.ok(plain(text(out)).includes("trailing words"));
});

test("pathological Markdown renders quickly and stays bounded", () => {
    const nasty = ["*".repeat(20000), "_".repeat(20000), "|".repeat(5000), "- ".repeat(5000), "[".repeat(5000) + "](", "**a".repeat(3000)].join("\n");
    const t0 = performance.now();
    const out = md(nasty);
    assert.ok(performance.now() - t0 < 1500);
    assert.ok(text(out).includes("cut off"));
});

test("very long pages are cut with a visible notice", () => {
    const out = md("word ".repeat(T.LIMIT.body));
    assert.ok(text(out).endsWith("the rest is cut off."));
});

test("italic needs word boundaries (snake_case and arithmetic stay as written)", () => {
    for (const s of ["city_layout_py", "Wide_Road_Big", "2*3*4", "a_b_ c"]) assert.equal(plain(text(T.markup(s))), s, s);
    assert.ok(T.markup("see _this_ now").children.some((c) => plain(text(c)).trim() === "this"));
});

test("inline markup matching stays linear on hostile input", () => {
    for (const nasty of ["[".repeat(1_000_000), "[a](".repeat(200_000), "![".repeat(500_000), "_a ".repeat(300_000), "**a ".repeat(250_000)]) {
        const t0 = performance.now();
        T.markup(nasty);
        const ms = performance.now() - t0;
        assert.ok(ms < 1500, `${nasty.slice(0, 4)}…: ${ms} ms`);
    }
});

test("the page budget cuts text past the page's share and says so", () => {
    const b = T.budget();
    assert.equal(T.take(b, "x".repeat(5000)).length, T.LIMIT.line);
    let total = 0;
    for (let i = 0; i < 100; i++) total += T.take(b, "y".repeat(T.LIMIT.line)).length;
    assert.equal(total + T.LIMIT.line, T.LIMIT.page);
    assert.equal(b.cut, true);
    assert.equal(T.take(b, "more"), "");
});

test("pictures: only plain PNG names the mod checked are shown, at most four times as tall as wide", () => {
    const ctx = { ...CTX, sizes: { "map.ab12cd34.png": [1600, 800], "tall.png": [1, 4096] } };
    const img = find(T.Picture({ b: T.budget(), ctx, file: "map.ab12cd34.png", caption: "Map" }), "img")[0];
    assert.equal(img.props.src, "coui://citymanager/j/images/map.ab12cd34.png");
    const w = parseFloat(img.props.style.width), hgt = parseFloat(img.props.style.height);
    assert.equal(hgt, Math.round(w / 2));
    const tall = find(T.Picture({ b: T.budget(), ctx, file: "tall.png", caption: "" }), "img")[0];
    assert.ok(parseFloat(tall.props.style.height) <= w * 4, tall.props.style.height);
    for (const bad of ["../mayor.json", "../../Saves/x.png", "a/b.png", "a\\b.png", "x.jpg", "coui://ui-mods/x.png", ".hidden.png", "", "x.png?y", "%2e%2e/x.png",
        "..%5C..%5Cx.png", "unchecked.png", "constructor", "__proto__"]) {
        assert.equal(find(T.Picture({ b: T.budget(), ctx, file: bad, caption: "" }), "img").length, 0, bad);
    }
});

test("a page draws pictures only up to its pixel budget", () => {
    const ctx = { ...CTX, sizes: { "big.png": [2000, 4000] } };
    const out = render(md(Array(20).fill("![p](big.png)").join("\n\n"), ctx));
    const fits = Math.floor(T.LIMIT.pixels / 8e6);
    assert.equal(find(out, "img").length, fits);
    assert.equal((text(out).match(/picture not shown/g) || []).length, 20 - fits);
});

test("the Mayor's tick and status merge by the shared cases (the same ones journal.py runs)", () => {
    for (const c of CASES.ticks) assert.equal(T.stepDone({ ticks: { k: c.tick } }, "k", c.item), c.done, c.why);
    for (const c of CASES.status) assert.deepEqual(T.projectStatus({ status: { [c.project.id]: c.mine } }, c.project), { status: c.status, byMayor: c.byMayor }, c.why);
    assert.equal(T.stepDone({ ticks: null }, "k", { done: true }), true);
    assert.equal(T.stepDone({}, "constructor", { done: false }), false);
});

test("lists from a journal lose null and non-object holes", () => {
    assert.deepEqual(T.objs([null, 1, "x", { a: 1 }, undefined, [2]]), [{ a: 1 }, [2]]);
    assert.deepEqual(T.arr([null, "a", undefined, "b"]), ["a", "b"]);
    assert.equal(T.own({}, "constructor"), undefined);
    assert.equal(T.own(JSON.parse('{"__proto__": 5}'), "__proto__"), 5);
});

test("the error boundary turns a drawing error into a message, and tries again when the journal or panel changes", () => {
    const err = new Error("bad title");
    assert.deepEqual(T.Guard.getDerivedStateFromError(err), { error: err });
    const g = new T.Guard({ children: "ok", resetKeys: ["j1", true] });
    assert.equal(g.render(), "ok");
    g.state = { error: err };
    assert.ok(text(g.render()).includes("bad title"));
    g.componentDidUpdate({ resetKeys: ["j1", true] });
    assert.ok(g.state.error);
    g.props = { children: "ok", resetKeys: ["j2", true] };
    g.componentDidUpdate({ resetKeys: ["j1", true] });
    assert.equal(g.state.error, null);
    const quiet = new T.Guard({ quiet: true });
    quiet.state = { error: err };
    assert.equal(quiet.render(), null);
});

test("times show in local time; other strings as written", () => {
    assert.match(T.when("2026-11-24T19:05:00Z"), /^\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d\d:\d\d$/);
    assert.equal(T.when("2026-11-24 19:00"), "2026-11-24 19:00");
    assert.equal(T.when(null), "");
});

test("the journal chooser lists journals and offers a new one", () => {
    const all = text(T.Chooser({ info: { city: "Testville", journals: ["a", null, "b"], folder: "a" }, onDone: () => {} }));
    for (const s of ["a", "b", "Start a new journal for this city", "Use the automatic choice", "Back"]) assert.ok(all.includes(s), s);
});

test("the wrap-up belongs to the briefing, or to the session in a journal without a manager", () => {
    const info = { sessionStart: "2026-11-24T18:00:00Z" };
    assert.equal(T.wrapUpId({ briefing: { id: "2026-11-24" } }, info), "2026-11-24");
    assert.equal(T.wrapUpId({}, info), "session-2026-11-24T18:00:00Z");
    assert.equal(T.wrapUpId({ briefing: "junk" }, info), "session-2026-11-24T18:00:00Z");
    // A new briefing is a new Wrap-up tab (React remounts on a new key), so typing never moves to the new briefing.
    const page = (j) => T.tabPage(3, { j, mayor: {}, info, ctx: CTX });
    assert.equal(page({ briefing: { id: "a" } }).props.key, "a");
    assert.equal(page({ briefing: { id: "b" } }).props.key, "b");
});

// ---- every tab, drawn from a hostile journal ----

const long = (n) => ("**x** " + "word ".repeat(Math.ceil(n / 5))).slice(0, n);
const many = (n, f) => Array.from({ length: n }, (_, i) => f(i));
const HOSTILE = {
    city: long(1990), manager: long(1990), updated: "2026-11-24T10:00:00Z",
    briefing: { id: "2026-11-24", title: long(1990), summary: long(1990), body: long(29000),
        tasks: many(300, (i) => ({ id: "t" + i, text: long(1990), note: long(1990), project: "p0" })) },
    briefings: [{ id: "2026-11-23", title: long(1990), tasks: many(300, (i) => ({ id: "t" + i, text: long(1990) })) }],
    projects: many(300, (i) => ({ id: "p" + i, title: long(1990), status: "active", scale: "constructor", summary: long(1990), body: long(29000),
        steps: many(i < 2 ? 300 : 1, (k) => ({ id: "s" + k, text: long(1990), note: long(1990) })),
        log: i === 0 ? many(300, () => ({ date: "x", text: long(1990) })) : [], plans: many(i === 0 ? 300 : 0, () => ({ kind: "draft", name: long(1990), note: long(1990) })) })),
    reports: many(300, (i) => ({ id: "2026-01-" + i, title: long(1990), summary: long(1990) })),
    cityPage: { title: long(1990), summary: long(1990), body: long(29000), facts: many(300, () => ({ label: long(1990), value: long(1990), note: long(1990) })) },
    replies: Object.fromEntries(many(500, (i) => ["n" + i, { text: long(3990), date: "x" }])),
};
const HOSTILE_MAYOR = {
    notes: many(2000, (i) => ({ id: "n" + i, at: "2026-11-24T19:00:00Z", project: "p0", text: "x".repeat(2000) })),
    ticks: Object.fromEntries(many(300, (i) => ["b:2026-11-24/t" + i, { done: true, at: "2026-11-24T19:00:00Z" }])),
};

test("every tab draws a bounded page from a hostile journal, and says what it cut", () => {
    const info = { sessionStart: "2026-11-24T18:00:00Z" };
    const tabs = {
        Today: h(T.TodayTab, { j: HOSTILE, mayor: HOSTILE_MAYOR, ctx: CTX, onOpenProject: () => {} }),
        Projects: h(T.ProjectList, { j: HOSTILE, mayor: HOSTILE_MAYOR, onOpen: () => {} }),
        Project: h(T.ProjectDetail, { j: HOSTILE, mayor: HOSTILE_MAYOR, ctx: CTX, id: "p0", onBack: () => {} }),
        Notes: h(T.NotesTab, { j: HOSTILE, mayor: HOSTILE_MAYOR }),
        "Wrap-up": h(T.WrapUpTab, { j: HOSTILE, mayor: HOSTILE_MAYOR, info }),
        City: h(T.CityTab, { j: HOSTILE, ctx: CTX }),
    };
    for (const [name, el] of Object.entries(tabs)) {
        const t0 = performance.now();
        const drawn = render(el);
        const ms = performance.now() - t0;
        const s = stats(drawn);
        // The City tab holds the reports list, a page of its own. Labels ("You · 24 Nov 19:00" on each of 500 notes) come
        // on top of the journal's own text. Before the budget, the Today tab alone drew 600,000 characters of this journal.
        const pages = name === "City" ? 2 : 1;
        assert.ok(s.chars < pages * T.LIMIT.page * 1.6, `${name}: ${s.chars} characters`);
        assert.ok(s.elements < pages * 20000, `${name}: ${s.elements} elements`);
        assert.ok(ms < 2000, `${name}: ${ms} ms`);
        assert.ok(text(drawn).includes("cut off"), `${name}: no notice`);
    }
});

test("ids that match Object's built-ins draw as plain data", () => {
    const j = { projects: [{ id: "constructor", title: "C", status: "constructor", scale: "constructor", steps: [] }], replies: {} };
    const mayor = { notes: [{ id: "constructor", at: "2026-11-24T19:00:00Z", text: "my note" }], status: {}, ticks: {} };
    const list = text(render(h(T.ProjectList, { j, mayor, onOpen: () => {} })));
    assert.ok(list.includes("In progress") && list.includes("constructor"), list);
    const notes = text(render(h(T.NotesTab, { j, mayor })));
    assert.ok(notes.includes("my note") && !notes.includes("City Manager ·"), notes);
});

test("helpers and tabs survive junk input", () => {
    assert.equal(T.parse("{bad", 7), 7);
    assert.equal(T.parse("", 7), 7);
    assert.deepEqual(T.arr("not a list"), []);
    assert.equal(T.arr(new Array(1000).fill(0)).length, T.LIMIT.items);
    assert.equal(T.arr(new Array(1000).fill(0), Infinity).length, 1000);
    assert.doesNotThrow(() => md(null));
    assert.doesNotThrow(() => T.markup(""));
    const junk = { projects: [null, { id: 5, title: { x: 1 }, steps: [null, { id: [1], text: 7 }] }], briefing: 3, briefings: "x", cityPage: [], reports: [{}] };
    for (const Tab of [T.TodayTab, T.ProjectList, T.NotesTab, T.CityTab, T.WrapUpTab]) {
        assert.doesNotThrow(() => render(h(Tab, { j: junk, mayor: { ticks: [], notes: {}, debriefs: 4 }, info: {}, ctx: CTX, onOpen: () => {}, onOpenProject: () => {} })), Tab.name);
    }
});

test("the City tab shows the snapshot's time, its problem, and a button that takes one", () => {
    const calls = [];
    const api = globalThis.window["cs2/api"];
    const before = api.trigger;
    api.trigger = (...args) => calls.push(args);
    try {
        const buttonOf = (tree) => {
            const all = [];
            const walk = (n) => { if (n && typeof n === "object") { if (n.props && n.props.onClick && text(n) === "Take a snapshot") all.push(n); (n.children || []).forEach(walk); } };
            walk(tree);
            return all[0];
        };
        const idle = render(h(T.SnapshotRow, { info: { snapshot: { time: "24 Nov 21:05", busy: false, problem: "" } } }));
        assert.match(text(idle), /Last taken 24 Nov 21:05\./);
        buttonOf(idle).props.onClick();
        assert.deepEqual(calls, [["cityManager", "snapshot"]]);

        const busy = render(h(T.SnapshotRow, { info: { snapshot: { time: "", busy: true, problem: "" } } }));
        assert.match(text(busy), /Taking a snapshot…/);
        assert.equal(buttonOf(busy), undefined);   // the button reads "Taking…" and does nothing

        const none = render(h(T.SnapshotRow, { info: { snapshot: { problem: "No journal is linked to this city" } } }));
        assert.match(text(none), /None taken yet\..*No journal is linked/s);
        assert.match(text(render(h(T.SnapshotRow, { info: { snapshot: { time: "<b>" + "x".repeat(500) } } }))), /Last taken <b>x+/);
        assert.match(text(render(h(T.CityTab, { j: { city: "X" }, ctx: CTX }))), /City snapshot/);   // drawn even without the info binding
    } finally {
        api.trigger = before;
    }
});

test("the Wrap-up says what changed since the city loaded", () => {
    assert.equal(T.digits(1234567), "1,234,567");
    assert.equal(T.digits(-42000.4), "42,000");
    assert.deepEqual(T.sessionLines({}), []);
    assert.deepEqual(T.sessionLines({ asOf: "19:20" }), ["No changes to the city yet."]);
    const lines = T.sessionLines({ asOf: "19:20", roadsAddedKm: 2.31, roadsRemovedKm: 0.4, railAddedKm: 0, railRemovedKm: 1.2,
        grew: 41, placed: 2, removed: 1, population: 312, money: -42000, tiles: 1 });
    assert.deepEqual(lines, ["2.3 km of new road, 0.4 km removed", "1.2 km of track removed", "41 new buildings grew, you placed 2, 1 removed",
        "+312 people", "money −$42,000", "1 more map tile"]);
    assert.deepEqual(T.sessionLines({ asOf: "x", grew: 1, population: -1, money: "junk" }), ["1 new building grew", "−1 people"]);
    const tab = text(render(h(T.WrapUpTab, { j: { briefing: { id: "b" } }, mayor: {}, info: { session: { asOf: "19:20", grew: 3 } } })));
    assert.match(tab, /Since you loaded the city.*3 new buildings grew.*As of 19:20/s);
    assert.match(text(render(h(T.WrapUpTab, { j: {}, mayor: {}, info: {} }))), /fills in after the game next saves/);
});

test("the window: docked by default, floating windows stay on screen and clear of the game's bars", () => {
    const scr = { px: [1920, 1080], w: 1920, h: 1080, k: 1 };
    assert.equal(T.screenKey(scr), "1.78");
    assert.equal(T.screenKey({ px: [2048, 1536] }), "1.33");
    const docked = T.fitLayout(undefined, scr);
    assert.equal(docked.mode, "docked");
    assert.equal(docked.w, 590);
    const s = T.panelStyle(docked);
    assert.equal(s.right, "12rem");
    assert.equal(s.left, undefined);

    const far = T.fitLayout({ mode: "floating", x: 5000, y: -300, w: 99999, bodyH: 99999 }, scr);
    assert.equal(far.w, T.WIN.maxW);
    assert.equal(far.x, 1920 - T.WIN.maxW);               // pushed back on screen
    assert.equal(far.y, T.WIN.top);                        // below the game's buttons at the top
    assert.ok(far.y + T.WIN.header + far.bodyH <= 1080 - T.WIN.bottom);   // above the bottom toolbar
    const tiny = T.fitLayout({ mode: "floating", w: 10, bodyH: 10 }, scr);
    assert.equal(tiny.w, T.WIN.minW);
    assert.equal(tiny.bodyH, T.WIN.minBodyH);
    const junk = T.fitLayout({ mode: "floating", x: NaN, y: "top", w: null }, scr);
    assert.ok(Number.isFinite(junk.x) && Number.isFinite(junk.y) && junk.w === 590);
    const fs = T.panelStyle({ mode: "floating", x: 100, y: 200, w: 600, bodyH: 400 });
    assert.equal(fs.left, "100rem");
    assert.equal(fs.top, "200rem");
    assert.equal(fs.right, undefined);
    assert.equal(fs.width, "600rem");

    // A 4:3 screen (the iPad) is 1920 x 1440 rem: the same window fits lower down.
    const ipad = { px: [2048, 1536], w: 1920, h: 1440, k: 2048 / 1920 };
    const low = T.fitLayout({ mode: "floating", x: 0, y: 1200, w: 600, bodyH: 300 }, ipad);
    assert.equal(low.y, 1440 - T.WIN.bottom - T.WIN.header - 300);
});

test("dragging moves the window, and the edges and corners resize it", () => {
    const scr = { px: [1920, 1080], w: 1920, h: 1080, k: 1 };
    const start = T.fitLayout({ mode: "floating", x: 400, y: 200, w: 600, bodyH: 400 }, scr);
    const moved = T.dragged(start, "move", 150, 50, scr);
    assert.deepEqual([moved.x, moved.y, moved.w, moved.bodyH], [550, 250, 600, 400]);
    const right = T.dragged(start, "r", 100, 0, scr);
    assert.deepEqual([right.x, right.w], [400, 700]);
    const left = T.dragged(start, "l", -100, 0, scr);
    assert.deepEqual([left.x, left.w], [300, 700]);                 // the right edge stays put
    const narrow = T.dragged(start, "l", 1000, 0, scr);
    assert.deepEqual([narrow.x, narrow.w], [400 + 600 - T.WIN.minW, T.WIN.minW]);
    const corner = T.dragged(start, "br", 50, 80, scr);
    assert.deepEqual([corner.w, corner.bodyH], [650, 480]);
    const bl = T.dragged(start, "bl", -50, 80, scr);
    assert.deepEqual([bl.x, bl.w, bl.bodyH], [350, 650, 480]);
    assert.equal(T.dragged(start, "move", 5000, 5000, scr).x, 1920 - 600);   // never off screen
    const tall = T.dragged(start, "b", 5000, 5000, scr);
    assert.equal(tall.y, 200);                                        // growing stops at the toolbar; the window stays put
    assert.equal(tall.y + T.WIN.header + tall.bodyH, 1080 - T.WIN.bottom);
    const wide = T.dragged(start, "r", 5000, 0, scr);
    assert.deepEqual([wide.x, wide.w], [400, T.WIN.maxW]);          // as wide as allowed, from where it was
    const edge = T.dragged(T.fitLayout({ mode: "floating", x: 1000, y: 200, w: 600, bodyH: 400 }, scr), "r", 5000, 0, scr);
    assert.deepEqual([edge.x, edge.x + edge.w], [1000, 1920]);    // or to the screen's edge
});

test("the resize handles: two edges, the bottom, and two corners with grips, each starting its own drag", () => {
    const calls = [];
    const handles = T.ResizeHandles({ onStart: (kind, ev) => calls.push([kind, ev.screenX]) });
    assert.equal(handles.length, 5);
    handles.forEach((x, i) => x.props.onMouseDown({ screenX: i }));
    assert.deepEqual(calls, [["l", 0], ["r", 1], ["b", 2], ["bl", 3], ["br", 4]]);
    assert.deepEqual(handles.filter((x) => x.children.length).map((x) => x.props.key), ["bl", "br"]);   // grips in the bottom corners
    const saved = T.fitLayout({ mode: "floating", x: 300, y: 150, w: 650, bodyH: 500 }, { px: [1920, 1080], w: 1920, h: 1080, k: 1 });
    assert.equal(T.panelStyle(saved).left, "300rem");   // a saved window opens where the Mayor left it
});
