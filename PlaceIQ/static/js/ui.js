/* PlaceIQ – UI helpers (same look & helpers as the original prototype, now with HTML escaping). */
var COL = ["#1d4ed8", "#16a34a", "#0891b2", "#7c3aed", "#d97706", "#db2777"];
var ST = ["Applied", "Under Review", "Shortlisted", "Technical Interview", "HR Interview", "Selected", "Rejected"];
var $ = function (s) { return document.querySelector(s); };

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}
var toastTimer;
function toast(m) {
  var t = $("#toast"); t.textContent = m; t.style.display = "block";
  clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.style.display = "none"; }, 3200);
}
function modal(h) {
  var m = document.createElement("div"); m.className = "modal";
  m.onclick = function (e) { if (e.target == m) m.remove(); };
  m.innerHTML = "<div>" + h + '<p><button class="btn s" onclick="this.closest(\'.modal\').remove()">Close</button></p></div>';
  document.body.appendChild(m); return m;
}
function closeModal() { var m = document.querySelector(".modal"); if (m) m.remove(); }
function logo(id, name) { return '<div class="logo2" style="background:' + COL[(id || 0) % 6] + '">' + esc((name || "?")[0]) + "</div>"; }
function tags(a, c) { return (a || []).map(function (s) { return '<span class="tag ' + (c || "") + '">' + esc(s) + "</span>"; }).join(""); }
function stTag(s) { return '<span class="tag ' + (s == "Selected" ? "g" : s == "Rejected" ? "r" : s == "Applied" || s == "Under Review" ? "" : "a") + '">' + esc(s) + "</span>"; }
/* tbl: cells are trusted HTML – call esc() on user data before passing it in. */
function tbl(h, rows) {
  if (!rows.length) return '<div class="empty">Nothing to show yet.</div>';
  return '<div class="tw"><table><tr>' + h.map(function (x) { return "<th>" + x + "</th>"; }).join("") + "</tr>" +
    rows.map(function (r) { return "<tr>" + r.map(function (x) { return "<td>" + x + "</td>"; }).join("") + "</tr>"; }).join("") + "</table></div>";
}
function stat(n, l) { return '<div class="card stat"><b>' + esc(n) + "</b><span>" + esc(l) + "</span></div>"; }
function bars(d, mx) {
  mx = mx || Math.max.apply(0, d.map(function (x) { return x[1]; })) || 1;
  return '<svg viewBox="0 0 300 140" width="100%">' + d.map(function (x, i) {
    var h = x[1] / mx * 90, w = 300 / d.length;
    return '<rect x="' + (i * w + 10) + '" y="' + (110 - h) + '" width="' + (w - 20) + '" height="' + h + '" rx="4" fill="' + COL[i % 6] + '"/>' +
      '<text x="' + (i * w + w / 2) + '" y="126" font-size="10" text-anchor="middle" fill="currentColor">' + esc(x[0]) + "</text>" +
      '<text x="' + (i * w + w / 2) + '" y="' + (104 - h) + '" font-size="11" text-anchor="middle" fill="currentColor">' + esc(x[1]) + "</text>";
  }).join("") + "</svg>";
}
function donut(p, l) {
  var c = 2 * Math.PI * 40; p = Math.max(0, Math.min(100, p));
  return '<svg viewBox="0 0 120 120" width="130"><circle cx="60" cy="60" r="40" fill="none" stroke="var(--bd)" stroke-width="12"/><circle cx="60" cy="60" r="40" fill="none" stroke="var(--gr)" stroke-width="12" stroke-dasharray="' + (c * p / 100) + " " + c + '" transform="rotate(-90 60 60)" stroke-linecap="round"/><text x="60" y="65" text-anchor="middle" font-size="20" font-weight="700" fill="currentColor">' + p + '%</text></svg><div class="mut" style="text-align:center">' + esc(l) + "</div>";
}
function field(id, l, v, t, extra) {
  return "<div><label>" + l + '</label><input id="' + id + '" type="' + (t || "text") + '" value="' + esc(v) + '" ' + (extra || "") + "></div>";
}
function select(id, l, opts, selected, extra) {
  return "<div><label>" + l + '</label><select id="' + id + '" ' + (extra || "") + ">" + opts.map(function (o) {
    var v = Array.isArray(o) ? o[0] : o, t = Array.isArray(o) ? o[1] : o;
    return '<option value="' + esc(v) + '"' + (String(v) == String(selected) ? " selected" : "") + ">" + esc(t) + "</option>";
  }).join("") + "</select></div>";
}
function val(id) { var e = $("#" + id); return e ? e.value.trim() : ""; }
function bar(p) { return '<div class="bar" style="width:90px"><i style="width:' + Math.max(0, Math.min(100, p)) + '%"></i></div>'; }
function loading() { return '<div class="card mut"><span class="spin"></span>Loading…</div>'; }
function fmtDate(d) { if (!d) return "—"; var p = d.split("-"); return p.length == 3 ? p[2] + "/" + p[1] + "/" + p[0] : d; }
