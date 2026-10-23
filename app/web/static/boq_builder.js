(function () {
  var form = document.getElementById("builder");
  if (!form) return;
  var count = document.getElementById("bcount"), find = document.getElementById("bfind");
  function update() {
    var n = 0;
    form.querySelectorAll('input[name^="q_"]').forEach(function (i) { if (i.value.trim() !== "") n++; });
    count.textContent = n + (n === 1 ? " item selected" : " items selected");
  }
  form.addEventListener("input", update);
  find.addEventListener("input", function () {
    var q = find.value.trim().toLowerCase();
    form.querySelectorAll(".bdiv").forEach(function (d) {
      var shown = 0;
      d.querySelectorAll("tbody tr").forEach(function (tr) {
        var hit = !q || tr.getAttribute("data-text").indexOf(q) !== -1;
        tr.hidden = !hit; if (hit) shown++;
      });
      d.hidden = !!q && shown === 0;
      if (q && shown) d.open = true;
    });
  });
  find.addEventListener("keydown", function (e) { if (e.key === "Enter") e.preventDefault(); });
  form.addEventListener("submit", function () {      // send only the quantities that were filled in
    form.querySelectorAll('input[name^="q_"]').forEach(function (i) { if (i.value.trim() === "") i.disabled = true; });
  });
  window.addEventListener("pageshow", function () { form.querySelectorAll('input[name^="q_"]').forEach(function (i) { i.disabled = false; }); update(); });
  update();
})();
