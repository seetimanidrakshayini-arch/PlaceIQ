/* PlaceIQ – placement officer portal pages. All data comes from /api/officer/* (MySQL via Flask). */
var oStud = [], oAppFilter = { st: "", q: "" };

async function loadDepts() { return (await GET("/api/departments")).items; }

/* ---------------------------------------------------------------- dashboard */
PAGES.odash = async function () {
  var s = (await GET("/api/officer/dashboard")).summary;
  var up = s.upcoming.length ? tbl(["Student", "Company", "Round", "Date", "Time"], s.upcoming.map(function (i) {
    return [esc(i.student), esc(i.company), esc(i.round), fmtDate(i.date), esc(i.time || "—")];
  })) : '<p class="mut">No upcoming interviews.</p>';
  return "<h1>Placement Officer Dashboard</h1><div class=\"grid\">" + stat(s.students, "Registered students") + stat(s.companies, "Companies") + stat(s.jobs, "Active jobs") + stat(s.applications, "Applications") +
    stat(s.placed, "Placed students") + stat(s.pending_reviews, "Resumes pending review") + '</div><div class="grid g2"><div class="card"><h2>Applications by status</h2>' +
    bars(s.by_status.map(function (x) { return [x[0].split(" ")[0].slice(0, 6), x[1]]; }), Math.max(3, Math.max.apply(0, s.by_status.map(function (x) { return x[1]; })))) +
    '</div><div class="card"><h2>Students by department</h2>' + bars(s.by_dept.map(function (d) { return [d.dept, d.students]; })) + '</div></div><div class="card"><h2>Upcoming interviews</h2>' + up + "</div>";
};

/* ---------------------------------------------------------------- students */
function stRows(q) {
  q = (q || "").toLowerCase();
  return tbl(["USN", "Name", "Dept", "CGPA", "Backlogs", "Resume", "Pool", ""], oStud.filter(function (s) { return (s.name + s.usn + s.dept + s.email).toLowerCase().indexOf(q) > -1; }).map(function (s) {
    return [esc(s.usn), esc(s.name) + (s.placed ? ' <span class="tag g">Placed</span>' : ""), esc(s.dept), s.cgpa, s.bl,
      s.has_resume ? '<a class="btn s sm" target="_blank" href="/api/officer/students/' + s.id + '/resume-file">View PDF</a>' : '<span class="mut">None</span>',
      s.pool ? '<span class="tag g">Eligible pool</span>' : '<span class="tag a">Review</span>',
      '<button class="btn s sm" onclick="editStu(' + s.id + ')">Edit</button> <button class="btn s sm" onclick="resetPw(' + s.id + ')">Reset password</button> <button class="btn r sm" onclick="delStu(' + s.id + ')">Remove</button>'];
  }));
}
PAGES.ostud = async function () {
  oStud = (await GET("/api/officer/students")).items; var depts = await loadDepts();
  return '<div class="hdr-row"><h1>Student Management</h1><span class="sp"></span><a class="btn s sm" href="/api/officer/reports/export.csv?type=students">⬇ Export CSV</a></div><div class="card"><h2>Add student</h2><div class="grid">' +
    field("sn", "Full name") + field("su", "USN") + field("se", "Email", "", "email") + select("sd", "Department", depts) + field("sc", "CGPA", "", "number", 'step="0.01" min="0" max="10"') + field("sb", "Backlogs", "0", "number", 'min="0"') +
    '</div><p><button class="btn g" onclick="addStu()">Add student</button> <span class="mut mini">A temporary password is generated and shown once.</span></p></div><div class="card"><input id="sq" placeholder="Search name, USN, email or department" oninput="sfilter()"><div id="st">' + stRows("") + "</div></div>";
};
function sfilter() { $("#st").innerHTML = stRows($("#sq").value); }
function tempPwModal(title, email, pw) {
  modal("<h2>" + esc(title) + "</h2><p>Login: <b>" + esc(email) + "</b></p><p>Temporary password: <code style=\"font-size:16px\"><b>" + esc(pw) + "</b></code></p><p class=\"mut\">Share it with the student securely. It is not stored in readable form and will not be shown again.</p>");
}
async function addStu() {
  try {
    var email = val("se");
    var r = await POST("/api/officer/students", { name: val("sn"), usn: val("su"), email: email, dept: val("sd"), cgpa: val("sc"), backlogs: val("sb") });
    route(); tempPwModal("Student added", email, r.temp_password);
  } catch (e) { toast(e.message); }
}
async function resetPw(id) {
  var s = oStud.find(function (x) { return x.id == id; });
  if (!confirm("Issue a new temporary password for " + s.name + "?")) return;
  try { var r = await POST("/api/officer/students/" + id + "/reset-password"); tempPwModal("Password reset", s.email, r.temp_password); } catch (e) { toast(e.message); }
}
async function editStu(id) {
  var s = oStud.find(function (x) { return x.id == id; }), depts = await loadDepts();
  modal("<h2>Edit " + esc(s.name) + "</h2><p class=\"mut\">" + esc(s.usn) + " · verified academic record</p>" + select("m_dept", "Department", depts, s.dept) + field("m_cgpa", "CGPA", s.cgpa, "number", 'step="0.01"') + field("m_bl", "Backlogs", s.bl, "number") +
    '<p><button class="btn g" onclick="saveStu(' + id + ')">Save</button></p>');
}
function saveStu(id) { act(function () { return PUT("/api/officer/students/" + id, { dept: val("m_dept"), cgpa: val("m_cgpa"), backlogs: val("m_bl") }); }, "Student updated").then(function (r) { if (r) closeModal(); }); }
function delStu(id) {
  var s = oStud.find(function (x) { return x.id == id; });
  if (confirm("Remove " + s.name + " and all their applications and resume? This cannot be undone.")) act(function () { return DEL("/api/officer/students/" + id); }, "Student removed");
}

/* ---------------------------------------------------------------- AI resume review */
PAGES.orev = async function () {
  oStud = (await GET("/api/officer/students")).items;
  return '<h1>AI Resume Review</h1><span class="tag a">Scores computed by the PlaceIQ NLP analyser from each student\'s uploaded PDF</span><div class="card">' +
    tbl(["Student", "Dept", "Score", "Skills found", "Review", ""], oStud.map(function (s) {
      return [esc(s.name), esc(s.dept), s.has_resume ? bar(s.score) + s.score + "/100" : '<span class="mut">No resume</span>', tags(s.skills, "g") || "—",
        s.review ? '<span class="tag ' + (s.review == "Approved" ? "g" : s.review == "Pending" ? "" : "a") + '">' + esc(s.review) + "</span>" : '<span class="tag">—</span>',
        s.has_resume ? '<button class="btn s sm" onclick="rev(' + s.id + ')">Review</button>' : ""];
    })) + "</div>";
};
async function rev(id) {
  try {
    var r = await GET("/api/officer/students/" + id + "/resume"), s = r.student, a = r.resume && r.resume.analysis;
    if (!r.resume) { toast("This student has not uploaded a resume"); return; }
    modal("<h2>" + esc(s.name) + " – Resume review</h2><p><b>" + esc(s.usn) + "</b> · " + esc(s.dept) + " · CGPA " + esc(s.cgpa) + '</p><div class="score">' + (a ? a.score : "—") + '<small class="mut">/100</small></div>' +
      (a ? "<p><b>Skills found:</b> " + (tags(a.skills_found, "g") || "none") + "</p><p><b>Missing sections:</b> " + (tags(a.sections_missing, "r") || "none") + "</p><p><b>Suggestions:</b></p>" + a.recommendations.slice(0, 5).map(function (t) { return "<p class=\"mini\">• " + esc(t) + "</p>"; }).join("") : "") +
      '<p><a class="btn s sm" target="_blank" href="/api/officer/students/' + id + '/resume-file">Open PDF</a></p><label>Note to student (optional)</label><textarea id="rv_note" rows="2">' + esc(r.resume.note) + '</textarea><p><button class="btn g sm" onclick="revSet(' + id + ',\'Approved\')">Approve</button> <button class="btn s sm" onclick="revSet(' + id + ',\'Changes requested\')">Request changes</button></p>');
  } catch (e) { toast(e.message); }
}
function revSet(id, v) {
  act(function () { return POST("/api/officer/students/" + id + "/review", { status: v, note: val("rv_note") }); }, "Resume review: " + v).then(function (r) { if (r) closeModal(); });
}

/* ---------------------------------------------------------------- companies */
PAGES.ocomp = async function () {
  var d = (await GET("/api/officer/companies")).items; window._comps = d;
  return '<h1>Company Management</h1><div class="card"><h2>Add company</h2><div class="row"><div class="f">' + field("cn", "Name") + '</div><div class="f">' + field("ci", "Industry") + '</div><div class="f">' + field("cw", "Website") +
    '</div></div><p><button class="btn g" onclick="addCo()">Add company</button></p></div><div class="card">' +
    tbl(["Company", "Industry", "Website", "Jobs", ""], d.map(function (c) {
      return [logo(c.id, c.name) + " " + esc(c.name), esc(c.ind), esc(c.site), c.jobs, '<button class="btn s sm" onclick="editCo(' + c.id + ')">Edit</button> <button class="btn r sm" onclick="delCo(' + c.id + ')">Remove</button>'];
    })) + "</div>";
};
function addCo() { act(function () { return POST("/api/officer/companies", { name: val("cn"), ind: val("ci"), site: val("cw") }); }, "Company added"); }
function editCo(id) {
  var c = window._comps.find(function (x) { return x.id == id; });
  modal("<h2>Edit company</h2>" + field("m_cn", "Name", c.name) + field("m_ci", "Industry", c.ind) + field("m_cw", "Website", c.site) + '<p><button class="btn g" onclick="saveCo(' + id + ')">Save</button></p>');
}
function saveCo(id) { act(function () { return PUT("/api/officer/companies/" + id, { name: val("m_cn"), ind: val("m_ci"), site: val("m_cw") }); }, "Company updated").then(function (r) { if (r) closeModal(); }); }
function delCo(id) { if (confirm("Remove this company and its jobs?")) act(function () { return DEL("/api/officer/companies/" + id); }, "Company removed"); }

/* ---------------------------------------------------------------- jobs */
function jobForm(p, j, comps, depts) {
  j = j || {};
  return '<div class="grid">' + select(p + "c", "Company", comps.map(function (c) { return [c.id, c.name]; }), j.company_id) + field(p + "r", "Role", j.role) + field(p + "p", "Package (LPA)", j.pkg, "number", 'step="0.1" min="0"') +
    field(p + "g", "Min CGPA", j.cgpa, "number", 'step="0.01" min="0" max="10"') + field(p + "b", "Max backlogs", j.bl, "number", 'min="0"') + field(p + "d", "Deadline", j.dl, "date") + "</div>" +
    field(p + "s", "Required skills (comma separated)", (j.sk || []).join(", ")) + field(p + "e", "Eligible departments (comma separated, blank = all). Available: " + depts.join(", "), (j.depts || []).join(", ")) +
    "<div><label>Description</label><textarea id=\"" + p + 'x" rows="2">' + esc(j.description) + "</textarea></div>";
}
function readJob(p) {
  return { company_id: val(p + "c"), role: val(p + "r"), pkg: val(p + "p"), cgpa: val(p + "g"), bl: val(p + "b"), dl: val(p + "d"), sk: val(p + "s"), depts: val(p + "e"), description: val(p + "x") };
}
PAGES.ojobs = async function () {
  var jobs = (await GET("/api/officer/jobs")).items, comps = (await GET("/api/officer/companies")).items, depts = await loadDepts();
  window._jobs = jobs; window._jobComps = comps; window._jobDepts = depts;
  if (!comps.length) return '<h1>Job Management</h1><div class="card"><p class="mut">Add a company first (Companies page), then post jobs.</p><button class="btn" onclick="go(\'ocomp\')">Go to Companies</button></div>';
  return '<h1>Job Management</h1><div class="card"><h2>Post job &amp; set eligibility</h2>' + jobForm("j", null, comps, depts) + '<p><button class="btn g" onclick="addJob()">Post job</button></p></div><div class="card">' +
    tbl(["Company", "Role", "LPA", "CGPA", "Backlogs", "Depts", "Deadline", "Apps", "Status", ""], jobs.map(function (j) {
      return [esc(j.company), esc(j.role), j.pkg, j.cgpa, j.bl, esc(j.depts.length ? j.depts.join("/") : "All"), fmtDate(j.dl), j.applications,
        j.active ? (j.expired ? '<span class="tag a">Expired</span>' : '<span class="tag g">Open</span>') : '<span class="tag r">Closed</span>',
        '<button class="btn s sm" onclick="editJob(' + j.id + ')">Edit</button> <button class="btn s sm" onclick="toggleJob(' + j.id + ',' + (j.active ? "false" : "true") + ')">' + (j.active ? "Close" : "Reopen") + '</button> <button class="btn r sm" onclick="delJob(' + j.id + ')">Remove</button>'];
    })) + "</div>";
};
function addJob() { act(function () { return POST("/api/officer/jobs", readJob("j")); }, "Job posted"); }
function editJob(id) {
  var j = window._jobs.find(function (x) { return x.id == id; });
  modal("<h2>Edit job</h2>" + jobForm("m", j, window._jobComps, window._jobDepts) + '<p><button class="btn g" onclick="saveJob(' + id + ')">Save</button></p>');
}
function saveJob(id) { act(function () { return PUT("/api/officer/jobs/" + id, readJob("m")); }, "Job updated").then(function (r) { if (r) closeModal(); }); }
function toggleJob(id, active) { act(function () { return PUT("/api/officer/jobs/" + id, { active: active }); }); }
function delJob(id) { if (confirm("Remove this job?")) act(function () { return DEL("/api/officer/jobs/" + id); }, "Job removed"); }

/* ---------------------------------------------------------------- applications */
function oaf(k, v) { oAppFilter[k] = v; route(); }
PAGES.oapps = async function () {
  var r = await GET("/api/officer/applications"), q = oAppFilter.q.toLowerCase();
  var list = r.items.filter(function (a) {
    return (!oAppFilter.st || a.status == oAppFilter.st) && (!q || (a.student + a.usn + a.company + a.role).toLowerCase().indexOf(q) > -1);
  });
  return '<div class="hdr-row"><h1>Application Management</h1><span class="sp"></span><a class="btn s sm" href="/api/officer/reports/export.csv?type=applications">⬇ Export CSV</a></div><div class="card row"><div class="f"><input placeholder="Search student, USN, company or role" value="' + esc(oAppFilter.q) + '" onchange="oaf(\'q\',this.value)"></div><select class="f" onchange="oaf(\'st\',this.value)"><option value="">All statuses</option>' +
    r.statuses.map(function (s) { return "<option" + (oAppFilter.st == s ? " selected" : "") + ">" + esc(s) + "</option>"; }).join("") + '</select></div><div class="card">' +
    tbl(["Student", "Company", "Role", "Date", "Resume", "Status / update", ""], list.map(function (a) {
      return [esc(a.student) + '<br><span class="mut mini">' + esc(a.usn) + " · CGPA " + esc(a.cgpa) + "</span>", esc(a.company), esc(a.role), fmtDate(a.date), '<button class="btn s sm" onclick="rev(' + a.student_id + ')">Resume / AI</button>',
        '<select onchange="setSt(' + a.id + ',this.value)">' + r.statuses.map(function (x) { return "<option" + (x == a.status ? " selected" : "") + ">" + esc(x) + "</option>"; }).join("") + "</select>",
        '<button class="btn g sm" onclick="setSt(' + a.id + ',\'Shortlisted\')">Shortlist</button>'];
    })) + "</div>";
};
function setSt(id, s) { act(function () { return PUT("/api/officer/applications/" + id + "/status", { status: s }); }); }

/* ---------------------------------------------------------------- interviews */
PAGES.ointer = async function () {
  var r = await GET("/api/officer/interviews"), apps = r.items.filter(function (a) { return a.status != "Rejected" && a.status != "Selected"; });
  var rows = []; r.items.forEach(function (a) { a.interviews.forEach(function (i) { rows.push([a, i]); }); });
  rows.sort(function (x, y) { return x[1].date < y[1].date ? -1 : 1; });
  return '<h1>Interview Rounds</h1><div class="card"><h2>Schedule an interview</h2><div class="grid">' +
    select("iv_a", "Application", apps.map(function (a) { return [a.id, a.student + " – " + a.company + " (" + a.role + ") · " + a.status]; })) + select("iv_r", "Round", r.rounds) +
    field("iv_d", "Date", "", "date") + field("iv_t", "Time", "", "time") + field("iv_v", "Venue / link") + field("iv_n", "Notes") + "</div><p><button class=\"btn g\" onclick=\"schedule()\">Schedule</button> <span class=\"mut mini\">Scheduling a Technical/HR round updates the application status and notifies the student. Re-scheduling the same round updates it.</span></p></div><div class=\"card\"><h2>Scheduled rounds</h2>" +
    tbl(["Student", "Company", "Role", "Round", "Date", "Time", "Venue", "Status", ""], rows.map(function (x) {
      var a = x[0], i = x[1]; return [esc(a.student), esc(a.company), esc(a.role), esc(i.round), fmtDate(i.date), esc(i.time || "—"), esc(i.venue || "—"), stTag(a.status), '<button class="btn r sm" onclick="delIv(' + i.id + ')">Remove</button>'];
    })) + "</div>";
};
function schedule() {
  if (!val("iv_a")) { toast("No eligible application to schedule"); return; }
  act(function () { return POST("/api/officer/interviews", { application_id: val("iv_a"), round: val("iv_r"), date: val("iv_d"), time: val("iv_t"), venue: val("iv_v"), notes: val("iv_n") }); });
}
function delIv(id) { if (confirm("Remove this scheduled round?")) act(function () { return DEL("/api/officer/interviews/" + id); }, "Interview removed"); }

/* ---------------------------------------------------------------- placement results */
PAGES.oplace = async function () {
  var r = await GET("/api/officer/results"), s = r.summary;
  return '<div class="hdr-row"><h1>Placement Results</h1><span class="sp"></span><a class="btn s sm" href="/api/officer/reports/export.csv?type=placements">⬇ Placed students CSV</a></div><div class="grid">' + stat(s.applications, "Applications") + stat(s.selected, "Selected") + stat(s.rejected, "Rejected") + stat(s.placed_students, "Students placed") + stat(s.avg_pkg, "Avg package (LPA)") + stat(s.max_pkg, "Highest (LPA)") +
    '</div><div class="card">' + tbl(["Student", "Company", "Role", "Package", "Status", "Final result"], r.items.map(function (a) {
      return [esc(a.student), esc(a.company), esc(a.role), "₹" + esc(a.pkg) + " LPA", stTag(a.status), '<button class="btn g sm" onclick="setSt(' + a.id + ',\'Selected\')">Select</button> <button class="btn s sm" onclick="setSt(' + a.id + ',\'Rejected\')">Reject</button>'];
    })) + "</div>";
};

/* ---------------------------------------------------------------- reports */
PAGES.orep = async function () {
  var s = (await GET("/api/officer/reports/summary")).summary;
  var dept = tbl(["Department", "Students", "Placed", "Rate"], s.by_dept.map(function (d) { return [esc(d.dept), d.students, d.placed, bar(d.rate) + d.rate + "%"]; }));
  return '<h1>Placement Reports</h1><div class="grid">' + stat(s.placed, "Students placed") + stat(s.placement_rate + "%", "Placement rate") + stat(s.avg_pkg, "Average LPA") + stat(s.max_pkg, "Highest LPA") + stat(s.min_pkg, "Lowest LPA") +
    '</div><div class="grid g2"><div class="card"><h2>Applications per company</h2>' + bars(s.by_company.map(function (c) { return [c.name.slice(0, 8), c.apps]; })) + '</div><div class="card"><h2>Placement rate</h2>' + donut(s.placement_rate, "of students placed") +
    '</div></div><div class="card"><h2>Department-wise placement</h2>' + dept + '</div><div class="card"><h2>Download</h2><a class="btn" href="/api/officer/reports/placement.pdf">⬇ Generate PDF report</a> <a class="btn s" href="/api/officer/reports/export.csv?type=applications">⬇ Applications CSV</a> <a class="btn s" href="/api/officer/reports/export.csv?type=students">⬇ Students CSV</a> <a class="btn s" href="/api/officer/reports/export.csv?type=placements">⬇ Placements CSV</a></div>';
};

/* ---------------------------------------------------------------- settings */
PAGES.oset = async function () {
  var s = await GET("/api/officer/settings");
  return '<h1>Settings</h1><div class="grid g2"><div class="card"><h2>General</h2>' + field("x", "Institution name", s.institution) + field("y", "Placement season", s.season) +
    '<label>Theme</label><select onchange="document.documentElement.dataset.theme=this.value;try{localStorage.setItem(\'placeiq-theme\',this.value)}catch(e){}"><option value="light"' + (document.documentElement.dataset.theme == "light" ? " selected" : "") + '>Light</option><option value="dark"' + (document.documentElement.dataset.theme != "light" ? " selected" : "") +
    '>Dark</option></select><p><button class="btn" onclick="saveSet()">Save</button></p></div><div class="card"><h2>Departments</h2><p>' +
    s.departments.map(function (d) { return '<span class="tag">' + esc(d) + ' <a href="#" title="Remove" style="text-decoration:none" onclick="delDept(decodeURIComponent(\'' + encodeURIComponent(d).replace(/'/g, "%27") + '\'));return false">✕</a></span>'; }).join("") +
    '</p><div class="row"><div class="f"><input id="nd" placeholder="New department"></div><button class="btn" onclick="addDept()">Add</button></div><p class="mut">Only two roles exist: student and officer. The officer manages all administration.</p></div></div>' +
    '<div class="card"><h2>Change password</h2><div class="grid">' + field("cp_old", "Current password", "", "password") + field("cp_new", "New password (min 8)", "", "password") + '</div><p><button class="btn s" onclick="changePw()">Update password</button></p></div>';
};
function saveSet() { act(function () { return PUT("/api/officer/settings", { institution: val("x"), season: val("y") }); }, "Settings saved"); }
function addDept() { act(function () { return POST("/api/officer/departments", { name: val("nd") }); }, "Department added"); }
function delDept(n) { if (confirm("Remove department " + n + "?")) act(function () { return DEL("/api/officer/departments/" + encodeURIComponent(n)); }, "Department removed"); }
