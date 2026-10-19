// Confirmation prompts for forms that carry data-confirm (kept out of inline attributes so the Content-Security-Policy can forbid inline scripts).
document.addEventListener("submit", function (e) {
  var f = e.target;
  if (f && f.dataset && f.dataset.confirm && !window.confirm(f.dataset.confirm)) { e.preventDefault(); }
});

// Row editors for the workforce forms. Rows are plain inputs; on submit they are serialised to JSON in a hidden field (data-json-map = {key: value}, data-json-list = [{...}]).
// Kept in this file (not inline) so the Content-Security-Policy can forbid inline scripts.
document.addEventListener("click", function (e) {
  var add = e.target.closest && e.target.closest("[data-add-row]");
  if (add) {
    e.preventDefault();
    var box = document.getElementById(add.dataset.addRow), tpl = box && box.querySelector("template");
    if (tpl) { box.querySelector(".rowlist").appendChild(tpl.content.cloneNode(true)); }
    return;
  }
  var del = e.target.closest && e.target.closest("[data-del-row]");
  if (del) { e.preventDefault(); var row = del.closest(".row"); if (row) { row.remove(); } }
});
function toNum(v, asInt) { if (v === "" || v == null) { return v; } var n = asInt ? parseInt(v, 10) : v; return (asInt && isNaN(n)) ? v : n; }
document.addEventListener("submit", function (e) {
  var f = e.target;
  if (!f || !f.querySelectorAll) { return; }
  f.querySelectorAll("[data-json-map]").forEach(function (box) {
    var out = {}, asInt = box.dataset.int === "1";
    box.querySelectorAll(".row").forEach(function (r) {
      var k = (r.querySelector(".k") || {}).value, v = (r.querySelector(".v") || {}).value;
      if (k && k.trim() && v !== "" && v != null) { out[k.trim()] = toNum(v.trim(), asInt); }
    });
    var h = f.querySelector('input[type=hidden][name="' + box.dataset.jsonMap + '"]');
    if (h) { h.value = Object.keys(out).length ? JSON.stringify(out) : ""; }
  });
  f.querySelectorAll("[data-json-list]").forEach(function (box) {
    var list = [], ints = (box.dataset.ints || "").split(",");
    box.querySelectorAll(".row").forEach(function (r) {
      var o = {}, fx = {}, any = false;
      r.querySelectorAll("[data-f]").forEach(function (inp) {
        var name = inp.dataset.f, val = inp.type === "checkbox" ? (inp.checked ? true : "") : inp.value.trim();
        if (val === "" || val === false) { return; }
        any = true;
        if (name.indexOf("fx.") === 0) { fx[name.slice(3)] = inp.type === "checkbox" ? true : toNum(val, true); }
        else { o[name] = ints.indexOf(name) >= 0 ? toNum(val, true) : val; }
      });
      if (any) { if (Object.keys(fx).length) { o.fixed_days = fx; } list.push(o); }
    });
    var h = f.querySelector('input[type=hidden][name="' + box.dataset.jsonList + '"]');
    if (h) { h.value = JSON.stringify(list); }
  });
});

// Governed-parameter form: built from the kind's field skeleton (names and shapes only, never values) and serialised to JSON in the hidden "data" field.
(function () {
  var form = document.getElementById("paramform");
  if (!form) { return; }
  var kinds = JSON.parse(form.dataset.kinds || "[]"), box = document.getElementById("kindfields"), info = document.getElementById("kindinfo"), sel = document.getElementById("kind");
  function el(tag, attrs, text) { var e = document.createElement(tag); Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); }); if (text) { e.textContent = text; } return e; }
  function label(name) { return name.replace(/_/g, " "); }
  function scalar(name, v, sub) {                       // one input for a string / bool skeleton value
    var inp;
    if (typeof v === "boolean") { inp = el("input", { type: "checkbox" }); inp.dataset.kind = "bool"; }
    else if (typeof v === "string" && v.indexOf(" | ") > 0) { inp = el("select"); inp.appendChild(el("option", { value: "" }, "")); v.split(" | ").forEach(function (o) { inp.appendChild(el("option", { value: o.trim() }, o.trim())); }); inp.dataset.kind = "text"; }
    else if (v === "YYYY-MM-DD") { inp = el("input", { type: "date" }); inp.dataset.kind = "text"; }
    else { inp = el("input", { type: "text" }); inp.dataset.kind = "text"; if (typeof v === "string" && v && v.charAt(0) === "<") { inp.placeholder = v; } else if (typeof v === "string" && v) { inp.value = v; } }
    inp.dataset.name = name;
    return inp;
  }
  function field(name, v) {
    var wrap = el("div", { "class": "pfield" }), lab = el("label", {}, label(name)); wrap.appendChild(lab); wrap.dataset.name = name;
    if (Array.isArray(v) && v.length && typeof v[0] === "object") {           // list of objects -> row editor
      wrap.dataset.type = "rows"; var tpl = v[0], list = el("div", { "class": "rowlist" });
      function addRow() { var r = el("div", { "class": "row" }); Object.keys(tpl).forEach(function (k) { var i = scalar(k, tpl[k]); i.title = label(k); if (i.tagName === "INPUT" && i.type === "text" && !i.value) { i.placeholder = label(k); } r.appendChild(i); if (i.type === "checkbox") { r.appendChild(el("span", { "class": "muted" }, label(k))); } }); var d = el("button", { "class": "sm alt", type: "button" }, "×"); d.addEventListener("click", function () { r.remove(); }); r.appendChild(d); list.appendChild(r); }
      var add = el("button", { "class": "sm alt", type: "button" }, "+ row"); add.addEventListener("click", addRow); wrap.appendChild(list); wrap.appendChild(add); addRow(); wrap._tpl = tpl;
    } else if (Array.isArray(v)) { wrap.dataset.type = "list"; var i = el("input", { type: "text", placeholder: v.length ? String(v[0]) : "comma-separated" }); i.dataset.kind = "list"; wrap.appendChild(i); wrap.appendChild(el("div", { "class": "hint" }, "comma-separated" + (name.indexOf("weekday") >= 0 ? " (0 = Monday … 6 = Sunday)" : "")));
    } else if (v && typeof v === "object") {                                    // key -> value rows
      wrap.dataset.type = "map"; var keys = Object.keys(v), kph = keys.length ? keys[0] : "key", vph = keys.length ? String(v[keys[0]]) : "value", list2 = el("div", { "class": "rowlist" });
      function addKv() { var r = el("div", { "class": "row" }), k = el("input", { type: "text", placeholder: kph }), val = el("input", { type: "text", placeholder: vph }); k.className = "k"; val.className = "v"; var d = el("button", { "class": "sm alt", type: "button" }, "×"); d.addEventListener("click", function () { r.remove(); }); r.appendChild(k); r.appendChild(val); r.appendChild(d); list2.appendChild(r); }
      var add2 = el("button", { "class": "sm alt", type: "button" }, "+ row"); add2.addEventListener("click", addKv); wrap.appendChild(list2); wrap.appendChild(add2); addKv();
    } else { wrap.dataset.type = "scalar"; wrap.appendChild(scalar(name, v)); }
    return wrap;
  }
  function render() {
    var k = kinds.filter(function (x) { return x.kind === sel.value; })[0]; box.textContent = ""; info.textContent = "";
    if (!k) { return; }
    info.textContent = k.description + "  Approvers: " + k.approvers.join(", ") + ".";
    var grid = el("div", { "class": "grid" }); Object.keys(k.fields).forEach(function (n) { grid.appendChild(field(n, k.fields[n])); }); box.appendChild(grid);
  }
  function val(inp) { return inp.dataset.kind === "bool" ? inp.checked : inp.value.trim(); }
  function numify(items) { return items.every(function (x) { return /^-?\d+$/.test(x); }) ? items.map(Number) : items; }
  function serialise() {
    var raw = form.querySelector("[name=data_raw]"), hidden = form.querySelector("input[type=hidden][name=data]");
    if (raw && raw.value.trim()) { hidden.value = raw.value; return; }
    var out = {};
    box.querySelectorAll(".pfield").forEach(function (w) {
      var n = w.dataset.name, t = w.dataset.type;
      if (t === "scalar") { var i = w.querySelector("input,select"), v = val(i); if (i.dataset.kind === "bool") { out[n] = v; } else if (v !== "") { out[n] = v; } }
      else if (t === "list") { var items = w.querySelector("input").value.split(",").map(function (x) { return x.trim(); }).filter(Boolean); if (items.length) { out[n] = numify(items); } }
      else if (t === "map") { var m = {}; w.querySelectorAll(".row").forEach(function (r) { var k = r.querySelector(".k").value.trim(), v2 = r.querySelector(".v").value.trim(); if (k && v2) { m[k] = v2; } }); if (Object.keys(m).length) { out[n] = m; } }
      else if (t === "rows") { var rows = []; w.querySelectorAll(".row").forEach(function (r) { var o = {}, any = false; r.querySelectorAll("[data-name]").forEach(function (i) { var v3 = val(i); if (i.dataset.kind === "bool") { if (v3) { o[i.dataset.name] = true; any = true; } } else if (v3 !== "") { o[i.dataset.name] = v3; any = true; } }); if (any) { rows.push(o); } }); if (rows.length) { out[n] = rows; } }
    });
    hidden.value = JSON.stringify(out);
  }
  sel.addEventListener("change", render); form.addEventListener("submit", serialise); render();
})();
/* wide tables scroll inside their own box instead of stretching the page */
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("main table").forEach(function (t) {
    if (t.parentElement && t.parentElement.classList.contains("tw")) return;
    var w = document.createElement("div"); w.className = "tw";
    t.parentNode.insertBefore(w, t); w.appendChild(t);
  });
});
/* sentence-case what people read: placeholders, dropdown options, buttons, labels, headers (display only - submitted values are untouched) */
document.addEventListener("DOMContentLoaded", function () {
  function cap(s) { return /^[a-z]/.test(s) ? s.charAt(0).toUpperCase() + s.slice(1) : s; }
  document.querySelectorAll("input[placeholder],textarea[placeholder]").forEach(function (e) { e.setAttribute("placeholder", cap(e.getAttribute("placeholder"))); });
  document.querySelectorAll("option").forEach(function (o) {
    var t = o.textContent; if (!t || !/^[a-z]/.test(t.trim())) return;
    if (!o.hasAttribute("value")) o.setAttribute("value", o.value);          // an option without a value submits its text: pin the real value BEFORE changing what is displayed
    o.textContent = cap(t.trim()).replace(/_/g, " ");
  });
  document.querySelectorAll("button,summary,label,th").forEach(function (e) {
    var n = e.firstChild; while (n && n.nodeType === 3 ? !n.nodeValue.trim() : (n && n.nodeType === 1 && /^(INPUT|SELECT)$/.test(n.tagName))) n = n.nextSibling;   // skip a leading checkbox/field
    if (n && n.nodeType === 3 && /^\s*[a-z]/.test(n.nodeValue)) n.nodeValue = n.nodeValue.replace(/^(\s*)([a-z])/, function (_, a, b) { return a + b.toUpperCase(); });
  });
});
/* rates workbook column mapping: turn the per-column "this column is" selects into map_<field>=<column index> form fields */
document.addEventListener("DOMContentLoaded", function () {
  var f = document.getElementById("mapform"); if (!f) return;
  function sync() {
    var box = document.getElementById("mapvals"); if (!box) return; box.innerHTML = "";
    var used = {};
    f.querySelectorAll("select.mapsel").forEach(function (s) {
      if (!s.value || used[s.value]) return; used[s.value] = 1;
      var i = document.createElement("input"); i.type = "hidden"; i.name = "map_" + s.value; i.value = s.getAttribute("data-col"); box.appendChild(i);
    });
  }
  f.querySelectorAll("select.mapsel").forEach(function (s) { s.addEventListener("change", sync); }); f.addEventListener("submit", sync); sync();
});
/* "Go back" links (no javascript: URLs - the CSP forbids them) */
document.addEventListener("click", function (e) { var a = e.target.closest && e.target.closest("a[data-back]"); if (a) { e.preventDefault(); history.back(); } });
/* a Viewer is read-only: switch off every form that would change data (the server refuses them anyway) */
document.addEventListener("DOMContentLoaded", function () {
  if (document.body.getAttribute("data-role") !== "Viewer") return;
  document.querySelectorAll("main form[method=post], main form[method=POST]").forEach(function (f) {
    f.querySelectorAll("button,input,select,textarea").forEach(function (e) { e.disabled = true; });
    f.title = "Read-only: a Viewer cannot change data";
  });
});
/* approvals: select-all, live count, confirm before a bulk decision */
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("form[data-bulk]").forEach(function (f) {
    var id = f.id, all = document.querySelector('[data-selectall="' + id + '"]'), cnt = document.querySelector('[data-count="' + id + '"]');
    function boxes() { return Array.prototype.slice.call(document.querySelectorAll('input[name=sel][form="' + id + '"]:not(:disabled)')); }
    function upd() { var n = boxes().filter(function (b) { return b.checked; }).length; if (cnt) cnt.textContent = n + " selected"; }
    if (all) all.addEventListener("change", function () { boxes().forEach(function (b) { b.checked = all.checked; }); upd(); });
    boxes().forEach(function (b) { b.addEventListener("change", upd); });
    f.querySelectorAll("button[data-confirm-text]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        var n = boxes().filter(function (b) { return b.checked; }).length;
        if (!n) { e.preventDefault(); alert("Select at least one item first."); return; }
        if (!confirm(btn.getAttribute("data-confirm-text") + "\n\n" + n + " item(s).")) e.preventDefault();
      });
    });
  });
});
/* appearance: light / dark / follow the system. theme.js applies the saved choice before first paint. */
(function () {
  var root = document.documentElement;
  function effective() { var t = root.getAttribute("data-theme"); return t || (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"); }
  function set(mode) {
    try { if (mode === "system") { localStorage.removeItem("ksa-theme"); } else { localStorage.setItem("ksa-theme", mode); } } catch (e) {}
    if (mode === "system") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", mode);
    mark();
  }
  function mark() {
    var saved = null; try { saved = localStorage.getItem("ksa-theme"); } catch (e) {}
    document.querySelectorAll("[data-theme-set]").forEach(function (b) { var on = b.getAttribute("data-theme-set") === (saved || "system"); b.classList.toggle("on", on); b.setAttribute("aria-pressed", on ? "true" : "false"); });
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-theme-toggle]"); if (b) { set(effective() === "dark" ? "light" : "dark"); return; }
    var s = e.target.closest && e.target.closest("[data-theme-set]"); if (s) set(s.getAttribute("data-theme-set"));
  });
  document.addEventListener("DOMContentLoaded", mark);
})();
/* accessibility: every control gets a name a screen reader (and a tooltip) can use, taken from its label, column heading or field name */
(function () {
  function clean(el) { var c = el.cloneNode(true); c.querySelectorAll(".info,.sr-only,script").forEach(function (x) { x.remove(); }); return (c.textContent || "").replace(/\s+/g, " ").trim(); }
  function human(n) { n = (n || "").replace(/[_\-.]+/g, " ").trim(); return n ? n.charAt(0).toUpperCase() + n.slice(1) : ""; }
  function named(el) {
    if (el.getAttribute("aria-label") || el.getAttribute("aria-labelledby")) return true;
    if (el.id && document.querySelector('label[for="' + el.id.replace(/"/g, '\\"') + '"]')) return true;
    var l = el.closest("label"); return !!(l && clean(l).length > 1);
  }
  function nameFor(el) {
    var td = el.closest("td"), tr = el.closest("tr");
    if (td && tr) {
      var table = td.closest("table"), idx = Array.prototype.indexOf.call(tr.children, td), th = table && table.tHead && table.tHead.rows[0] && table.tHead.rows[0].cells[idx];
      var h = th ? clean(th) : "";
      if (el.type === "checkbox") { var first = tr.querySelector("td:not(:first-child)"); return "Select " + (first ? clean(first).slice(0, 50) : "row"); }
      if (h) return h;
    }
    if (el.type === "checkbox") return "Select";
    var p = el.previousElementSibling;
    if (p && /^(LABEL|B|SPAN|STRONG)$/.test(p.tagName) && clean(p) && clean(p).length < 60) return clean(p);
    var t = el.getAttribute("title"); if (t && !/^e\.g\./i.test(t)) return t;
    return human(el.getAttribute("name") || el.getAttribute("data-f") || el.getAttribute("placeholder"));
  }
  function run(root) {
    (root || document).querySelectorAll("input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=image]),select,textarea").forEach(function (el) {
      if (named(el)) return; var n = nameFor(el); if (n) el.setAttribute("aria-label", n);
    });
    (root || document).querySelectorAll("th").forEach(function (th) {
      if (clean(th) || th.querySelector("input,button")) return;
      var tr = th.parentElement, idx = Array.prototype.indexOf.call(tr.children, th), t = th.closest("table"), body = t && t.tBodies[0] && t.tBodies[0].rows[0], c = body && body.cells[idx];
      var s = document.createElement("span"); s.className = "sr-only"; s.textContent = c && c.querySelector("input[type=checkbox]") ? "Select" : "Actions"; th.appendChild(s);
    });
  }
  window.nameControls = run;
  document.addEventListener("DOMContentLoaded", function () { run(); setTimeout(run, 300); });
})();
