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
    o.textContent = cap(t.trim()).replace(/_/g, " ");
  });
  document.querySelectorAll("button,summary,label,th").forEach(function (e) {
    var n = e.firstChild; if (n && n.nodeType === 3 && /^\s*[a-z]/.test(n.nodeValue)) n.nodeValue = n.nodeValue.replace(/^(\s*)([a-z])/, function (_, a, b) { return a + b.toUpperCase(); });
  });
});
