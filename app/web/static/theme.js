/* Runs before the page paints (loaded synchronously in <head>) so there is no flash of the wrong theme. */
(function () {
  try {
    var t = localStorage.getItem("ksa-theme");
    if (t === "dark" || t === "light") document.documentElement.setAttribute("data-theme", t);
  } catch (e) { /* storage blocked: follow the system setting */ }
})();
