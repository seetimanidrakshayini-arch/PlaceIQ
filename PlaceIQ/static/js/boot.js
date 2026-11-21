/* PlaceIQ – startup. Loaded last so every page module is registered before the first route. */
window.addEventListener("hashchange", function () { var h = (location.hash || "#").slice(1); if (h != cur) { cur = h; route(); } });
(async function boot() {
  try { var t = localStorage.getItem("placeiq-theme"); if (t) document.documentElement.dataset.theme = t; } catch (e) { }
  try {
    var r = await GET("/api/auth/me");
    if (r.user) { sess = r.user; unread = r.unread || 0; }
  } catch (e) { toast(e.message); }
  route();
})();
