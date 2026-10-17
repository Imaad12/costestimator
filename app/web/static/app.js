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
