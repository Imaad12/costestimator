// Confirmation prompts for forms that carry data-confirm (kept out of inline attributes so the Content-Security-Policy can forbid inline scripts).
document.addEventListener("submit", function (e) {
  var f = e.target;
  if (f && f.dataset && f.dataset.confirm && !window.confirm(f.dataset.confirm)) { e.preventDefault(); }
});
