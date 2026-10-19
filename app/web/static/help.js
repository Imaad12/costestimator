/* (i) help: adds a hover / focus / tap explanation to labels, column headings, status chips and section titles.
   The wording lives in app/web/helptext.py and is fetched from /help/glossary.json. Nothing here changes what a form submits. */
(function () {
  var tip = null;
  function norm(t) {            // identical to helptext.norm in Python
    t = t.toLowerCase().replace(/\([^)]*\)/g, " ").replace(/[*:·]/g, " ").replace(/\d[\d,.]*/g, " ").replace(/[^a-z0-9%&\/+ -]/g, " ");
    return t.replace(/\s+/g, " ").trim();
  }
  function ensureTip() {
    if (!tip) { tip = document.createElement("div"); tip.className = "tip"; tip.setAttribute("role", "tooltip"); tip.hidden = true; document.body.appendChild(tip); }
    return tip;
  }
  function show(el) {
    var t = ensureTip(); t.textContent = el.getAttribute("data-tip"); t.hidden = false;
    var r = el.getBoundingClientRect(), w = t.offsetWidth, h = t.offsetHeight;
    var x = Math.max(8, Math.min(r.left + r.width / 2 - w / 2, window.innerWidth - w - 8));
    var y = r.bottom + 8; if (y + h > window.innerHeight - 8) y = r.top - h - 8;
    t.style.left = x + "px"; t.style.top = Math.max(8, y) + "px";
  }
  function hide() { if (tip) tip.hidden = true; }
  function mk(text) {
    var s = document.createElement("span"); s.className = "info"; s.tabIndex = 0; s.setAttribute("role", "img");
    s.setAttribute("aria-label", "More information: " + text); s.setAttribute("data-tip", text); s.textContent = "i"; return s;
  }
  document.addEventListener("mouseover", function (e) { var i = e.target.closest && e.target.closest(".info"); if (i) show(i); });
  document.addEventListener("mouseout", function (e) { if (e.target.closest && e.target.closest(".info")) hide(); });
  document.addEventListener("focusin", function (e) { if (e.target.classList && e.target.classList.contains("info")) show(e.target); });
  document.addEventListener("focusout", hide);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") hide(); });
  document.addEventListener("click", function (e) {                    // touch: tap to show, tap elsewhere to hide
    var i = e.target.closest && e.target.closest(".info");
    if (i) { e.preventDefault(); e.stopPropagation(); show(i); } else hide();
  });
  function ownText(el) {                                              // the element's text without any (i) icons or form controls inside it
    var out = "";
    el.childNodes.forEach(function (n) {
      if (n.nodeType === 3) out += n.nodeValue;
      else if (n.nodeType === 1 && !n.classList.contains("info") && !/^(INPUT|SELECT|TEXTAREA|BUTTON|SMALL)$/.test(n.tagName)) out += n.textContent;
    });
    return out;
  }
  function humanise(el) {                                             // register_field style identifiers -> readable words
    el.childNodes.forEach(function (n) {
      if (n.nodeType !== 3) return;
      var m = n.nodeValue.match(/^(\s*)([A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+)(.*)$/);
      if (m) { var w = m[2].replace(/_/g, " "); w = w.charAt(0).toUpperCase() + w.slice(1).toLowerCase(); n.nodeValue = m[1] + w + m[3]; }
    });
  }
  function attach(glossary, placeholders) {
    var seenTag = {};                                                  // a status chip is explained once per page, not on every row
    document.querySelectorAll("main th, main h1, main h2, main h3, main summary, main label, main .kpi span, main .tag, main .stchip, main .stage h3").forEach(function (el) {
      if (el.querySelector(":scope > .info") || el.hasAttribute("data-noinfo")) return;
      humanise(el);
      var raw = ownText(el).trim(), key = norm(raw), text = glossary[key];
      if (el.tagName === "LABEL") {                                   // an explanation inside a label's brackets moves into the (i)
        var nodes = Array.prototype.filter.call(el.childNodes, function (n) { return n.nodeType === 3 && /\((?!\.)[^)]*[A-Za-z]{3,} [A-Za-z]{2,} [A-Za-z]{2,}[^)]*\)/.test(n.nodeValue); });
        if (nodes.length) {
          var m = nodes[0].nodeValue.match(/^(.*?)\s*\(([^)]+)\)(.*)$/);
          if (m && !/^(optional|required)/i.test(m[2])) {
            var expl = m[2].charAt(0).toUpperCase() + m[2].slice(1) + (/[.!?]$/.test(m[2]) ? "" : "."); nodes[0].nodeValue = m[1] + m[3];
            if (!text) text = expl;
          }
        }
      }
      if (text && el.matches(".tag, .stchip, label")) { if (seenTag[key]) text = ""; else seenTag[key] = 1; }
      if (text && el.tagName === "TH") {                                 // once per table
        var tb = el.closest("table"); tb._seen = tb._seen || {}; if (tb._seen[key]) text = ""; else tb._seen[key] = 1;
      }
      if (text) el.appendChild(mk(text));
    });
    document.querySelectorAll("main [placeholder]").forEach(function (inp) {
      var p = inp.getAttribute("placeholder"), r = placeholders[p];
      if (!r || inp.nextElementSibling && inp.nextElementSibling.classList.contains("info")) return;
      inp.setAttribute("placeholder", r[0]);
      if (!seenTag["ph:" + p]) { seenTag["ph:" + p] = 1; inp.insertAdjacentElement("afterend", mk(r[1])); }   // the clearer placeholder is applied everywhere; the (i) once per page
    });
  }
  document.addEventListener("DOMContentLoaded", function () {
    humaniseAll();
    fetch("/glossary.json", { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (g) { if (g) attach(g.terms, g.placeholders); }).catch(function () {});
  });
  function humaniseAll() { document.querySelectorAll("main th, main summary, main h2, main h3, main .tag").forEach(humanise); }
})();
