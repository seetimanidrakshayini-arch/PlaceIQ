/* PlaceIQ – application shell: session, hash routing, auth screens, notifications, theme. */
var PAGES = {};          // filled by student.js / officer.js (+ public pages below)
var sess = null;         // logged-in user {id,name,email,role}
var unread = 0, cur = (location.hash || "#").slice(1), routeToken = 0;
var oc = 1, ocData = {}; // officer-account wizard state
var selJob = +(sessionStorage.getItem("placeiq_job") || 0);

var NAV = {
  student: [["dash", "🏠 Dashboard"], ["profile", "👤 Academic Profile"], ["resume", "📄 Resume Analyzer"], ["skills", "🎯 Skill Gap"],
    ["recs", "⭐ Recommendations"], ["jobs", "💼 Job Opportunities"], ["elig", "✅ Eligibility"], ["apps", "📋 My Applications"],
    ["intv", "🗓 Interviews"], ["results", "🏆 Placement Results"]],
  officer: [["odash", "🏠 Dashboard"], ["ostud", "🎓 Students"], ["orev", "🤖 AI Resume Review"], ["ocomp", "🏢 Companies"],
    ["ojobs", "💼 Job Management"], ["oapps", "📋 Applications"], ["ointer", "🗓 Interview Rounds"], ["oplace", "🏆 Placement Results"],
    ["orep", "📊 Reports"], ["oset", "⚙️ Settings"]]
};
var PUBLIC = ["", "login", "register", "ologin", "ocreate"];

function go(r) { cur = r; try { location.hash = r; } catch (e) { } route(); window.scrollTo(0, 0); }

async function route() {
  var tk = ++routeToken, r = cur;
  if (!sess && PUBLIC.indexOf(r) < 0) { go("login"); return; }
  if (sess && PUBLIC.indexOf(r) >= 0 && r != "") { go(NAV[sess.role][0][0]); return; }
  var P = PAGES[r];
  if (!P) { go(sess ? NAV[sess.role][0][0] : ""); return; }
  if (PUBLIC.indexOf(r) < 0 && r != "jdet" && !NAV[sess.role].some(function (n) { return n[0] == r; })) { go(NAV[sess.role][0][0]); return; }
  if (r == "jdet" && sess.role != "student") { go(NAV[sess.role][0][0]); return; }
  if (PUBLIC.indexOf(r) >= 0) {
    try { var h = await P(); if (tk == routeToken) $("#root").innerHTML = h; }
    catch (e) { $("#root").innerHTML = '<div class="auth"><div class="card"><h2>Cannot load page</h2><p class="mut">' + esc(e.message) + '</p><button class="btn" onclick="route()">Retry</button></div></div>'; }
    return;
  }
  var nav = NAV[sess.role].map(function (n) {
    return '<a class="' + (n[0] == r || (r == "jdet" && n[0] == "jobs") ? "on" : "") + '" onclick="go(\'' + n[0] + '\');$(\'#side\').classList.remove(\'open\')">' + n[1] + "</a>";
  }).join("");
  $("#root").innerHTML = '<div class="app"><aside class="side" id="side"><div class="logo">🎓 PlaceIQ</div><div class="nav">' + nav +
    '</div></aside><div class="main"><div class="top"><button class="btn s menu" onclick="$(\'#side\').classList.toggle(\'open\')">☰</button><b>' +
    esc(sess.role.toUpperCase()) + ' PORTAL</b><span class="sp"></span><button class="btn s sm" onclick="notif()" title="Notifications">🔔 <span id="bell">' + unread +
    '</span></button><button class="btn s sm" onclick="toggleTheme()" title="Switch light/dark theme">🌓</button><span class="mut">' + esc(sess.name) +
    '</span><button class="btn s sm" onclick="logout()">Logout</button></div><div class="pg" id="pg">' + loading() + "</div></div></div>";
  try {
    var html = await P();
    if (tk != routeToken) return;
    $("#pg").innerHTML = html;
    var after = PAGES["_after_" + r]; if (after) after();
    refreshBell();
  } catch (e) {
    if (tk != routeToken) return;
    $("#pg").innerHTML = '<div class="card"><h3>Could not load this page</h3><p class="bad">' + esc(e.message) + '</p><button class="btn" onclick="route()">Retry</button></div>';
  }
}

async function refreshBell() {
  try { var r = await GET("/api/auth/me"); unread = r.unread || 0; var b = $("#bell"); if (b) b.textContent = unread; } catch (e) { }
}
async function notif() {
  try {
    var r = await GET("/api/auth/notifications");
    modal("<h2>Notifications</h2>" + (r.items.length ? r.items.map(function (n) {
      return "<p>" + (n.read ? "• " : "🔵 ") + esc(n.message) + ' <span class="mut mini">' + esc(n.at) + "</span></p>";
    }).join("") : '<p class="mut">No notifications yet.</p>'));
    await POST("/api/auth/notifications/read"); unread = 0; var b = $("#bell"); if (b) b.textContent = 0;
  } catch (e) { toast(e.message); }
}
function toggleTheme() {
  var t = document.documentElement.dataset.theme == "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem("placeiq-theme", t); } catch (e) { }
}
async function logout() { try { await POST("/api/auth/logout"); } catch (e) { } sess = null; unread = 0; go(""); }

/* ---------------------------------------------------------------- auth actions */
async function doLogin(role) {
  var email = val("le"), pw = $("#lp").value;
  if (!email || !pw) { toast("Enter your email and password."); return; }
  try {
    var r = await POST("/api/auth/login", { email: email, password: pw, role: role });
    sess = r.user; unread = r.unread || 0; go(NAV[sess.role][0][0]);
  } catch (e) { toast(e.message); }
}
async function doReg() {
  var er = [];
  if (val("rn").length < 3) er.push("Name too short");
  if (!/^[0-9][A-Za-z]{2}\d{2}[A-Za-z]{2,3}\d{3}$/.test(val("ru"))) er.push("USN format e.g. 1XX22CS014");
  if (!/^\S+@\S+\.\S+$/.test(val("re"))) er.push("Invalid email");
  if ($("#rp").value.length < 6) er.push("Password min 6 characters");
  if ($("#rp").value != $("#rc").value) er.push("Passwords do not match");
  if (er.length) { toast(er[0]); return; }
  try {
    var r = await POST("/api/auth/register", { name: val("rn"), usn: val("ru"), email: val("re"), password: $("#rp").value, confirm: $("#rc").value, dept: val("rd"), year_of_study: val("ry") });
    toast(r.message); go("login");
  } catch (e) { toast(e.message); }
}
function forgot() {
  modal("<h2>Forgot password?</h2><p>PlaceIQ does not send emails. Please contact the Placement Officer – they can issue a temporary password from <b>Students → Reset password</b>. After logging in, change it under <b>Academic Profile → Change password</b>.</p>");
}
async function ocNext() {
  if (oc == 1) {
    if (!/^OP-\d{4}-\d{2}$/.test(val("oi"))) { toast("Operator ID format: OP-2026-01"); return; }
    if (!val("ot")) { toast("Enter the one-time code issued by your administrator"); return; }
    ocData.operator_id = val("oi"); ocData.code = val("ot");
  }
  if (oc == 2) {
    if (val("on").length < 3 || !/^\S+@\S+\.\S+$/.test(val("oe"))) { toast("Enter a valid name and work email"); return; }
    ocData.name = val("on"); ocData.email = val("oe"); ocData.designation = val("od");
  }
  if (oc == 3) {
    if ($("#op").value.length < 8 || $("#op").value != $("#oq").value) { toast("Password min 8 chars and must match"); return; }
    ocData.password = $("#op").value; ocData.confirm = $("#oq").value;
    try { await POST("/api/auth/officer-register", ocData); toast("Officer account created"); }
    catch (e) { toast(e.message); if (e.status == 403) { oc = 1; route(); } return; }
  }
  oc++; route();
}

function changePw() {
  act(function () { return POST("/api/auth/change-password", { current: $("#cp_old").value, new: $("#cp_new").value }); }, "Password updated");
}

/* ---------------------------------------------------------------- public pages */
PAGES[""] = function () {
  return '<div class="hero"><div class="logo">🎓 PlaceIQ</div><h1>AI-Powered Student Placement Tracking &amp; Resume Analysis</h1><p class="mut">One platform for students and placement officers: resume analysis, skill-gap insight, eligibility checks, applications and placement results.</p><p><button class="btn" onclick="go(\'login\')">Student Login</button> <button class="btn s" onclick="go(\'register\')">Student Register</button> <button class="btn g" onclick="go(\'ologin\')">Officer Login</button></p><div class="grid" style="text-align:left;margin-top:30px"><div class="card"><h3>📄 Resume analysis</h3><span class="mut">PDF parsing, NLP skill extraction, scoring and tips</span></div><div class="card"><h3>✅ Eligibility</h3><span class="mut">CGPA, backlog and department rules enforced</span></div><div class="card"><h3>📊 Tracking</h3><span class="mut">Applications to interviews to final result</span></div></div></div>';
};
PAGES.login = function () {
  return '<div class="auth"><div class="card"><h2>Student Login</h2>' + field("le", "Email", "", "email", 'autocomplete="username" onkeydown="if(event.key==\'Enter\')doLogin(\'student\')"') +
    field("lp", "Password", "", "password", 'autocomplete="current-password" onkeydown="if(event.key==\'Enter\')doLogin(\'student\')"') +
    '<p><button class="btn" onclick="doLogin(\'student\')">Login</button> <a href="#" onclick="forgot();return false">Forgot password?</a></p><p class="mut">New student? <a href="#" onclick="go(\'register\');return false">Register</a></p><p class="mut">Placement officer? <a href="#" onclick="go(\'ologin\');return false">Officer login</a></p><p class="mut"><a href="#" onclick="go(\'\');return false">← Home</a></p></div></div>';
};
PAGES.ologin = function () {
  return '<div class="auth"><div class="card"><h2>Placement Officer Login</h2>' + field("le", "Official email", "", "email", 'autocomplete="username" onkeydown="if(event.key==\'Enter\')doLogin(\'officer\')"') +
    field("lp", "Password", "", "password", 'autocomplete="current-password" onkeydown="if(event.key==\'Enter\')doLogin(\'officer\')"') +
    '<p><button class="btn" onclick="doLogin(\'officer\')">Login</button></p><p class="mut">Officer accounts cannot be self-registered. Authorized college operators: <a href="#" onclick="oc=1;ocData={};go(\'ocreate\');return false">create an officer account</a></p><p class="mut"><a href="#" onclick="go(\'login\');return false">Student login</a></p></div></div>';
};
PAGES.ocreate = function () {
  var S = ["Verify operator", "Officer details", "Credentials", "Done"];
  var st = "<p>" + S.map(function (x, i) { return '<span class="tag ' + (i + 1 == oc ? "" : i + 1 < oc ? "g" : "a") + '">' + (i + 1) + ". " + x + "</span>"; }).join("") + "</p>";
  var body = oc == 1 ? field("oi", "Operator ID (e.g. OP-2026-01)", ocData.operator_id) + field("ot", "One-time code (from your administrator)", "", "password")
    : oc == 2 ? field("on", "Officer full name", ocData.name) + field("oe", "Work email", ocData.email, "email") + field("od", "Designation", ocData.designation || "Placement Officer")
    : oc == 3 ? field("op", "Password (min 8)", "", "password") + field("oq", "Confirm password", "", "password")
    : '<div class="banner" style="background:var(--gr2);color:var(--gr)">✅ Officer account created.</div><p class="mut">The password is stored as a salted hash. You can now log in from the officer login page.</p>';
  return '<div class="auth"><div class="card"><h2>Create officer account</h2>' + st + body + "<p>" +
    (oc < 4 ? '<button class="btn" onclick="ocNext()">' + (oc == 3 ? "Create account" : "Continue") + "</button> " : "") +
    '<a href="#" onclick="oc=1;ocData={};go(\'ologin\');return false">Back to officer login</a></p></div></div>';
};
PAGES.register = async function () {
  var d = (await GET("/api/departments")).items;
  return '<div class="auth"><div class="card"><h2>Student Registration</h2><p class="mut">Placement officer accounts cannot be self-registered.</p>' +
    field("rn", "Full name") + field("ru", "USN") + field("re", "Email", "", "email") + field("rp", "Password", "", "password") + field("rc", "Confirm password", "", "password") +
    "<label>Department</label><select id=\"rd\">" + d.map(function (x) { return "<option>" + esc(x) + "</option>"; }).join("") +
    '</select><label>Year of study</label><select id="ry"><option>1</option><option>2</option><option>3</option><option selected>4</option></select><p><button class="btn" onclick="doReg()">Register</button> <a href="#" onclick="go(\'login\');return false">Back to login</a></p></div></div>';
};
