// Unit tests for the inline UI JavaScript (Tarea 2, 3, 4, 5).
//
// The inline <script> blocks are extracted verbatim from the Jinja templates
// and executed inside a Node `vm` context with a minimal DOM / localStorage
// stub. This exercises the REAL production code (no duplication) without a
// browser. New task assertions are appended as their tasks are implemented.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import vm from "node:vm";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..", "..");
const TEMPLATE_FILES = [
  "app/templates/base.html",
  "app/templates/index.html",
  "app/templates/partials/search_bar.html",
];

// ── Minimal DOM / localStorage stubs ───────────────────────────────────────

function makeEl() {
  const classes = new Set();
  return {
    textContent: "",
    _classes: classes,
    classList: {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      toggle: (c) => {
        if (classes.has(c)) {
          classes.delete(c);
          return false;
        }
        classes.add(c);
        return true;
      },
      contains: (c) => classes.has(c),
    },
    setAttribute: function (k, v) {
      this["__attr_" + k] = v;
    },
    getAttribute: function (k) {
      return this["__attr_" + k];
    },
  };
}

function extractScripts() {
  let combined = "";
  for (const rel of TEMPLATE_FILES) {
    const file = resolve(ROOT, rel);
    let html;
    try {
      html = readFileSync(file, "utf-8");
    } catch {
      continue; // file not present/modified yet in this slice
    }
    const re = /<script[^>]*>([\s\S]*?)<\/script>/g;
    let m;
    while ((m = re.exec(html)) !== null) {
      if (m[1].trim() !== "") combined += m[1] + "\n";
    }
  }
  return combined;
}

function buildContext() {
  const store = new Map();
  const els = {};
  const qels = {};
  const documentElement = makeEl();

  const sandbox = {
    console,
    setTimeout,
    URLSearchParams,
    localStorage: {
      getItem: (k) => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, String(v)),
      removeItem: (k) => store.delete(k),
    },
    window: { location: { search: "" } },
    document: {
      documentElement,
      getElementById: (id) => {
        if (!els[id]) els[id] = makeEl();
        return els[id];
      },
      querySelector: (sel) => {
        if (!qels[sel]) qels[sel] = makeEl();
        return qels[sel];
      },
    },
  };
  return { sandbox, els, qels, documentElement, store };
}

// Build a context, optionally pre-seed the search-bar-wrapper as hidden,
// then evaluate the production inline scripts with the given ?search string.
function loadUI(search = "", seedHidden = false) {
  const ctx = buildContext();
  ctx.sandbox.window.location.search = search;
  if (seedHidden) {
    ctx.sandbox.document.getElementById("search-bar-wrapper").classList.add("hidden");
  }
  vm.createContext(ctx.sandbox);
  vm.runInContext(extractScripts(), ctx.sandbox, { filename: "inline-ui.js" });
  return ctx;
}

// ── Tiny test framework ─────────────────────────────────────────────────────

const failures = [];
function check(name, cond) {
  if (cond) {
    console.log("  ok  - " + name);
  } else {
    console.error("  FAIL- " + name);
    failures.push(name);
  }
}

// ── Tarea 2: dark-theme toggle logic ────────────────────────────────────────

const ctx = loadUI();

console.log("Tarea 2: theme toggle");
check(
  "initial data-theme is light (no localStorage)",
  ctx.documentElement.getAttribute("data-theme") === "light"
);
check(
  "theme-toggle icon initialised to moon for light",
  ctx.els["theme-toggle"].textContent === "🌙"
);

ctx.sandbox.toggleTheme();
check(
  "toggleTheme switches document to dark",
  ctx.documentElement.getAttribute("data-theme") === "dark"
);
check(
  "toggleTheme persists 'dark' to localStorage",
  ctx.store.get("xarchive-theme") === "dark"
);
check(
  "theme-toggle icon switches to sun in dark",
  ctx.els["theme-toggle"].textContent === "☀️"
);

ctx.sandbox.toggleTheme();
check(
  "toggleTheme switches back to light",
  ctx.documentElement.getAttribute("data-theme") === "light"
);
check(
  "toggleTheme persists 'light' to localStorage",
  ctx.store.get("xarchive-theme") === "light"
);

// ── Tarea 3: search-bar toggle ──────────────────────────────────────────────

console.log("Tarea 3: search bar toggle");
const wrapper = ctx.sandbox.document.getElementById("search-bar-wrapper");
wrapper.classList.add("hidden");
ctx.sandbox.toggleSearchBar();
check(
  "first toggle reveals the search bar (hidden removed)",
  ctx.els["search-bar-wrapper"].classList.contains("hidden") === false
);
ctx.sandbox.toggleSearchBar();
check(
  "second toggle hides the search bar again",
  ctx.els["search-bar-wrapper"].classList.contains("hidden") === true
);

// ── Tarea 4: search-bar visibility + hasSearchParams ────────────────────────

console.log("Tarea 4: search bar visibility");
ctx.sandbox.window.location.search = "?q=test";
check("hasSearchParams true when q present", ctx.sandbox.hasSearchParams() === true);
ctx.sandbox.window.location.search = "?date_from=2025-01-01";
check("hasSearchParams true when date_from present", ctx.sandbox.hasSearchParams() === true);
ctx.sandbox.window.location.search = "?source=all";
check("hasSearchParams false when only source=all", ctx.sandbox.hasSearchParams() === false);
ctx.sandbox.window.location.search = "";
check("hasSearchParams false with no params", ctx.sandbox.hasSearchParams() === false);

const shown = loadUI("?q=test", true);
check(
  "auto-show reveals wrapper when search params present",
  shown.els["search-bar-wrapper"].classList.contains("hidden") === false
);
const hiddenEmpty = loadUI("", true);
check(
  "wrapper stays hidden with no params",
  hiddenEmpty.els["search-bar-wrapper"].classList.contains("hidden") === true
);
const hiddenAll = loadUI("?source=all", true);
check(
  "wrapper stays hidden when only source=all",
  hiddenAll.els["search-bar-wrapper"].classList.contains("hidden") === true
);

// ── Report ──────────────────────────────────────────────────────────────────

if (failures.length > 0) {
  console.error(`\n${failures.length} assertion(s) failed.`);
  process.exit(1);
}
console.log("\nAll UI logic assertions passed.");
