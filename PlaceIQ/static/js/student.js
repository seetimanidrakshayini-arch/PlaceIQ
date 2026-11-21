/* PlaceIQ – student portal pages. All data comes from /api/student/* (MySQL via Flask). */
var flt = { q: "", co: "", cg: "", el: "" };
var pendingFile = null, pendingURL = "";
var RES_MAX = { "Contact details": 10, "Summary": 5, "Education": 15, "Skills": 25, "Projects": 20, "Experience": 5, "Certifications": 5, "Links": 5, "Impact (verbs/metrics)": 6, "Length": 4 };

function eligTags(j) {
  return j.eligible ? '<span class="tag g">Eligible</span>' : '<span class="tag r">Not eligible</span>';
}
function applyBtn(j) {
  if (j.applied) return '<span class="tag a">Applied · ' + esc(j.applied) + "</span>";
  if (j.expired) return '<span class="tag r">Deadline passed</span>';
  if (!j.eligible) return "";
  return '<button class="btn sm" onclick="applyJob(' + j.id + ')">Apply Now</button>';
}
function jobCard(j) {
  var m = j.match;
  return '<div class="card"><div class="row">' + logo(j.company_id, j.company) + '<div class="f"><h3>' + esc(j.role) + '</h3><span class="mut">' + esc(j.company) +
    "</span></div><b>₹" + esc(j.pkg) + " LPA</b></div><p class=\"mut\">Min CGPA " + esc(j.cgpa) + " · Max backlogs " + esc(j.bl) +
    (j.depts.length ? " · " + esc(j.depts.join("/")) : "") + " · Deadline " + fmtDate(j.dl) + "</p>" + tags(j.sk) + "<p>" + eligTags(j) +
    '<span class="tag">Skills ' + m.pct + '%</span></p><button class="btn s sm" onclick="viewJob(' + j.id + ')">View Details</button> ' + applyBtn(j) + "</div>";
}
function viewJob(id) { selJob = id; try { sessionStorage.setItem("placeiq_job", id); } catch (e) { } go("jdet"); }
function applyJob(id) { act(function () { return POST("/api/student/apply/" + id); }, "Application submitted"); }

/* ---------------------------------------------------------------- dashboard */
PAGES.dash = async function () {
  var d = await GET("/api/student/dashboard"), p = d.profile, s = d.stats, r = d.resume;
  var resumeCard = r
    ? '<div class="card"><h2>Resume analysis</h2><div class="row"><div class="score">' + r.score + '<small class="mut">/100</small></div><div class="f"><div class="bar"><i style="width:' + r.score + '%"></i></div><p class="mut mini">' + esc(r.name) + ' · Officer review: ' + esc(r.review) + "</p></div></div>" +
    tags(r.skills, "g") + "<h3>Top suggestions</h3>" + r.tips.map(function (t) { return "<p>• " + esc(t) + "</p>"; }).join("") + '<button class="btn s sm" onclick="go(\'resume\')">Full analysis</button></div>'
    : '<div class="card"><h2>Resume analysis</h2><p class="mut">Upload your PDF resume to get an AI score, detected skills and improvement tips.</p><button class="btn" onclick="go(\'resume\')">Upload resume</button></div>';
  var upc = d.upcoming.length ? tbl(["Company", "Round", "Date", "Time", "Venue"], d.upcoming.map(function (i) {
    return [esc(i.company), esc(i.round), fmtDate(i.date), esc(i.time || "—"), esc(i.venue || "—")];
  })) : '<p class="mut">No upcoming interviews.</p>';
  return "<h1>Welcome back, " + esc(p.name.split(" ")[0]) + " 👋</h1><p class=\"mut\">" + esc(p.usn) + " · " + esc(p.dept) + " · Sem " + esc(p.sem) + '</p><div class="grid">' +
    stat(p.cgpa, "CGPA") + stat(s.jobs, "Open jobs") + stat(s.eligible, "Eligible jobs") + stat(s.applied, "Jobs applied") + stat(s.shortlisted, "Shortlisted") + stat(s.placed ? "Placed" : "In progress", "Placement status") +
    '</div><div class="card"><div class="row"><b class="f">Profile completeness</b><span>' + d.completeness + '%</span></div><div class="bar"><i style="width:' + d.completeness + '%"></i></div>' +
    (d.completeness < 100 ? '<p class="mut mini">Complete your <a href="#" onclick="go(\'profile\');return false">academic profile</a> for better recommendations.</p>' : "") + "</div>" +
    '<div class="grid g2">' + resumeCard + '<div class="card"><h2>Upcoming interviews</h2>' + upc + "</div></div>" +
    '<div class="grid g2"><div class="card"><h2>Placement progress</h2>' + bars(d.status_counts.map(function (x) { return [x[0].split(" ")[0].slice(0, 6), x[1]]; }), Math.max(3, Math.max.apply(0, d.status_counts.map(function (x) { return x[1]; })))) +
    '</div><div class="card"><h2>Recent activity</h2>' + (d.notes.length ? d.notes.map(function (n) { return "<p>• " + esc(n) + "</p>"; }).join("") : '<p class="mut">No activity yet.</p>') + "</div></div>" +
    "<h2>Recent opportunities</h2><div class=\"grid\">" + (d.recent_jobs.map(jobCard).join("") || '<p class="mut">No open jobs right now.</p>') + "</div>";
};

/* ---------------------------------------------------------------- profile */
PAGES.profile = async function () {
  var r = await GET("/api/student/profile"), m = r.profile, depts = (await GET("/api/departments")).items;
  return "<h1>Academic Profile</h1><div class=\"card\"><div class=\"row\"><b class=\"f\">Profile completeness</b><span>" + r.completeness + '%</span></div><div class="bar"><i style="width:' + r.completeness + '%"></i></div></div>' +
    '<div class="card"><div class="grid">' + field("p_name", "Full name", m.name) + field("p_usn", "USN", m.usn) + select("p_dept", "Department", depts, m.dept) +
    field("p_sem", "Semester", m.sem, "number", 'min="1" max="10"') + field("p_cgpa", "CGPA", m.cgpa, "number", 'step="0.01" min="0" max="10"') +
    field("p_backlogs", "Backlogs", m.backlogs, "number", 'min="0"') + field("p_year", "Graduation year", m.year, "number") +
    field("p_tenth", "10th %", m.tenth, "number", 'step="0.01"') + field("p_twelfth", "12th / Diploma %", m.twelfth, "number", 'step="0.01"') + field("p_phone", "Phone", m.phone, "tel") + "</div>" +
    "<div>" + field("p_skills", "Technical skills (comma separated)", m.skills) + field("p_langs", "Programming languages", m.langs) +
    field("p_certs", "Certifications (separate with ;)", m.certs) + field("p_projects", "Projects (separate with ;)", m.projects) + "</div>" +
    '<p><button class="btn" onclick="saveProfile()">Save changes</button> <span class="mut mini">Email: ' + esc(m.email) + "</span></p></div>" +
    '<div class="card"><h2>Change password</h2><div class="grid">' + field("cp_old", "Current password", "", "password") + field("cp_new", "New password (min 6)", "", "password") +
    '</div><p><button class="btn s" onclick="changePw()">Update password</button></p></div>';
};
function saveProfile() {
  var g = function (k) { return val("p_" + k); };
  act(function () {
    return PUT("/api/student/profile", { name: g("name"), usn: g("usn"), dept: g("dept"), sem: g("sem"), year: g("year"), cgpa: g("cgpa"), backlogs: g("backlogs"), tenth: g("tenth"), twelfth: g("twelfth"), phone: g("phone"), skills: g("skills"), langs: g("langs"), certs: g("certs"), projects: g("projects") });
  }, "Profile saved");
}

/* ---------------------------------------------------------------- resume analyzer */
function fileSel(e) {
  var f = e.target.files[0]; if (!f) return;
  if (!/\.pdf$/i.test(f.name) && f.type != "application/pdf") { toast("Please choose a PDF"); e.target.value = ""; return; }
  if (f.size > 5 * 1024 * 1024) { toast("File is larger than 5 MB"); e.target.value = ""; return; }
  if (pendingURL) URL.revokeObjectURL(pendingURL);
  pendingFile = f; pendingURL = URL.createObjectURL(f); route();
}
async function analyse() {
  if (!pendingFile) { toast("Choose a PDF resume first"); return; }
  var b = $("#ab"); b.disabled = true; b.innerHTML = '<span class="spin"></span>Analyzing…';
  var fd = new FormData(); fd.append("resume", pendingFile);
  try {
    await api("POST", "/api/student/resume", fd, true);
    pendingFile = null; if (pendingURL) URL.revokeObjectURL(pendingURL); pendingURL = "";
    toast("Resume analysed and saved"); route();
  } catch (e) { toast(e.message); b.disabled = false; b.textContent = "Upload & Analyze"; }
}
function addDetected() { act(function () { return POST("/api/student/resume/apply-skills"); }); }
function analysisView(a) {
  var bd = Object.keys(a.breakdown).map(function (k) {
    var mx = RES_MAX[k] || 10; return '<div class="bd-row"><span>' + esc(k) + '</span><div class="bar"><i style="width:' + Math.round(100 * a.breakdown[k] / mx) + '%"></i></div><b>' + a.breakdown[k] + "/" + mx + "</b></div>";
  }).join("");
  return '<div class="grid g2"><div class="card"><h3>Skills identified</h3>' + (tags(a.skills_found, "g") || '<span class="mut">None recognised</span>') +
    '<p><button class="btn s sm" onclick="addDetected()">Add detected skills to my profile</button></p><h3>Projects identified</h3>' +
    (a.projects_found.length ? a.projects_found.map(function (p) { return "<p>• " + esc(p) + "</p>"; }).join("") : '<p class="mut">No projects section detected.</p>') +
    "<h3>Missing / suggested skills (from open jobs)</h3>" + (tags(a.suggested_skills, "r") || '<span class="mut">None – your skills cover current demand.</span>') +
    "<h3>Sections</h3>" + tags(a.sections_present, "g") + tags(a.sections_missing, "r") + '</div><div class="card"><h3>Recommendations</h3>' +
    a.recommendations.map(function (t) { return "<p>• " + esc(t) + "</p>"; }).join("") +
    (a.consistency_notes.length ? "<h3>Profile consistency</h3>" + a.consistency_notes.map(function (t) { return "<p>• " + esc(t) + "</p>"; }).join("") : "") +
    '</div></div><div class="card"><h3>Score breakdown</h3>' + bd + "</div>";
}
PAGES.resume = async function () {
  var r = (await GET("/api/student/resume")).resume;
  var prev = pendingURL ? '<iframe class="pdfprev" src="' + esc(pendingURL) + '"></iframe><p class="mut mini">📄 ' + esc(pendingFile.name) + " (" + Math.round(pendingFile.size / 1024) + " KB) – not uploaded yet</p>"
    : r ? '<iframe class="pdfprev" src="/api/student/resume/file"></iframe><p class="mut mini">📄 ' + esc(r.name) + " (" + r.size_kb + " KB) · uploaded " + esc(r.uploaded) + "</p>"
      : '<div class="card" style="min-height:130px;background:var(--bg)"><b>Preview</b><p class="mut">No file selected</p></div>';
  var a = r && r.analysis;
  var right = a
    ? '<div class="card"><div class="score">' + a.score + '<small class="mut">/100</small></div><div class="bar"><i style="width:' + a.score + '%"></i></div><p class="mut">Completeness: ' + a.completeness + '% · ' + a.word_count + ' words</p>' +
    '<p><b>Contact:</b> ' + esc(a.contact.email || "not found") + " · " + esc(a.contact.phone || "no phone") + "</p><p><b>Education:</b> " + esc(a.education || "not detected") + "</p><p><b>Officer review:</b> " +
    '<span class="tag ' + (r.review == "Approved" ? "g" : r.review == "Pending" ? "" : "a") + '">' + esc(r.review) + "</span> " + esc(r.review_note) + "</p></div>"
    : '<div class="card mut">Upload your resume and click Upload &amp; Analyze to see your score, skills and suggestions.</div>';
  return "<h1>Resume Analyzer</h1><div class=\"grid g2\"><div class=\"card\"><h2>Upload resume (PDF, max 5 MB)</h2><input type=\"file\" accept=\"application/pdf\" onchange=\"fileSel(event)\"><div style=\"margin-top:12px\">" + prev +
    '</div><p><button class="btn" id="ab" onclick="analyse()">Upload &amp; Analyze</button> <span class="mut mini">Uploading again replaces your previous resume.</span></p></div>' + right + "</div>" + (a ? analysisView(a) : "");
};

/* ---------------------------------------------------------------- skill gap */
PAGES.skills = async function () {
  var d = await GET("/api/student/skill-gap");
  var rows = d.jobs.map(function (j) { return [esc(j.company + " – " + j.role), tags(j.have, "g") || "—", tags(j.missing, "r") || "—", bar(j.pct) + j.pct + "%"]; });
  return '<h1>Skill Gap Analysis</h1><div class="card"><b>Your skills</b> <span class="mut mini">(profile + languages + latest resume)</span><br>' + (tags(d.skills) || '<span class="mut">No skills yet – update your profile or upload a resume.</span>') +
    '</div><div class="card">' + tbl(["Job", "Existing", "Missing", "Match"], rows) + '</div><div class="card"><h2>Recommended learning topics</h2>' +
    (d.topics.length ? d.topics.map(function (t) {
      return "<p>📚 <b>" + esc(t.skill) + '</b> <span class="mut">needed in ' + t.jobs + " open job(s), " + t.eligible_jobs + " of them you are eligible for</span></p>";
    }).join("") : '<p class="mut">No gaps found for open jobs. Great work!</p>') + "</div>";
};

/* ---------------------------------------------------------------- recommendations */
PAGES.recs = async function () {
  var d = await GET("/api/student/recommendations");
  return '<h1>Job Recommendations</h1><span class="tag a">NLP match: skill overlap (70%) + TF-IDF text similarity (30%)</span><p class="mut">Eligible roles are listed first, then ranked by match score. CGPA, backlog and department rules decide whether you can apply.</p>' +
    (d.items.length ? d.items.map(function (j) {
      return '<div class="card"><div class="row">' + logo(j.company_id, j.company) + '<div class="f"><h3>' + esc(j.role) + '</h3><span class="mut">' + esc(j.company) + " · ₹" + esc(j.pkg) + " LPA</span></div><b>" + j.score + '% match</b></div><div class="bar"><i style="width:' + j.score + '%"></i></div><p class="mut mini">Skills ' + j.match.pct + "% · Profile/resume text similarity " + j.text_sim + "%</p><p>" +
        tags(j.match.have, "g") + tags(j.match.missing, "r") + "</p><p>" + (j.eligible ? '<span class="tag g">Eligible</span> ' : '<span class="tag r">Not eligible: ' + esc(j.reasons[0]) + "</span> ") + applyBtn(j) + ' <button class="btn s sm" onclick="viewJob(' + j.id + ')">Details</button></p></div>';
    }).join("") : '<div class="card mut">No open jobs to recommend right now.</div>');
};

/* ---------------------------------------------------------------- jobs */
function fl(k, v) { flt[k] = v; route(); }
PAGES.jobs = async function () {
  var d = await GET("/api/student/jobs");
  var list = d.jobs.filter(function (j) {
    return j.active && !j.expired && (!flt.q || (j.role + " " + j.company + " " + j.sk.join(" ")).toLowerCase().indexOf(flt.q.toLowerCase()) > -1) &&
      (!flt.co || j.company_id == flt.co) && (!flt.cg || j.cgpa <= +flt.cg) && (!flt.el || (flt.el == "y") == j.eligible);
  });
  return '<h1>Job Opportunities</h1><div class="card row"><div class="f"><input placeholder="Search role, company or skill" value="' + esc(flt.q) + '" onchange="fl(\'q\',this.value)"></div><select class="f" onchange="fl(\'co\',this.value)"><option value="">All companies</option>' +
    d.companies.map(function (c) { return '<option value="' + c.id + '"' + (flt.co == c.id ? " selected" : "") + ">" + esc(c.name) + "</option>"; }).join("") +
    '</select><select class="f" onchange="fl(\'cg\',this.value)"><option value="">Any CGPA</option><option value="7"' + (flt.cg == "7" ? " selected" : "") + '>Min CGPA ≤ 7</option><option value="8"' + (flt.cg == "8" ? " selected" : "") + '>Min CGPA ≤ 8</option></select><select class="f" onchange="fl(\'el\',this.value)"><option value="">All eligibility</option><option value="y"' + (flt.el == "y" ? " selected" : "") + '>Eligible</option><option value="n"' + (flt.el == "n" ? " selected" : "") + '>Not eligible</option></select></div><div class="grid">' +
    (list.map(jobCard).join("") || '<p class="mut">No jobs match.</p>') + "</div>";
};
PAGES.jdet = async function () {
  if (!selJob) { go("jobs"); return ""; }
  var j = (await GET("/api/student/jobs/" + selJob)).job, m = j.match;
  return '<button class="btn s sm" onclick="go(\'jobs\')">← Back</button><div class="card" style="margin-top:12px"><div class="row">' + logo(j.company_id, j.company) + '<div class="f"><h1>' + esc(j.role) + '</h1><span class="mut">' + esc(j.company) + " · " + esc(j.industry || "") + (j.website ? " · " + esc(j.website) : "") + "</span></div><b>₹" + esc(j.pkg) + " LPA</b></div>" +
    (j.description ? "<p>" + esc(j.description) + "</p>" : "") + "<p>Minimum CGPA: <b>" + esc(j.cgpa) + "</b> · Max backlogs: <b>" + esc(j.bl) + "</b> · Departments: <b>" + esc(j.depts.length ? j.depts.join(", ") : "All") + "</b> · Deadline: <b>" + fmtDate(j.dl) + "</b></p><p><b>Required skills:</b> " + tags(j.sk) +
    "</p><p><b>Your match:</b> " + tags(m.have, "g") + tags(m.missing, "r") + " (" + m.pct + "%)</p><p>" + (j.eligible ? '<span class="tag g">You are eligible</span>' : j.reasons.map(function (x) { return '<span class="tag r">' + esc(x) + "</span>"; }).join("")) + "</p>" +
    (m.missing.length ? '<p class="mut">To improve your match, learn: ' + esc(m.missing.join(", ")) + ".</p>" : "") + applyBtn(j) + "</div>";
};

/* ---------------------------------------------------------------- eligibility */
PAGES.elig = async function () {
  var d = (await GET("/api/student/jobs")).jobs.filter(function (j) { return j.active && !j.expired; });
  var E = d.filter(function (j) { return j.eligible; }), N = d.filter(function (j) { return !j.eligible; });
  return '<h1>Eligibility Checker</h1><p class="mut">Mandatory criteria (CGPA, backlogs, department) decide eligibility. Skill match is informational only.</p><div class="card"><h2>✅ Eligible (' + E.length + ")</h2>" +
    tbl(["Company", "Role", "Skill match", "Status"], E.map(function (j) { return [esc(j.company), esc(j.role), "Skills " + j.match.pct + "%", j.applied ? stTag(j.applied) : '<button class="btn sm" onclick="applyJob(' + j.id + ')">Apply</button>']; })) +
    '</div><div class="card"><h2>❌ Not eligible (' + N.length + ")</h2>" + tbl(["Company", "Role", "Reason", "Skill match"], N.map(function (j) { return [esc(j.company), esc(j.role), j.reasons.map(function (x) { return '<span class="tag r">' + esc(x) + "</span>"; }).join(""), "Skills " + j.match.pct + "%"]; })) + "</div>";
};

/* ---------------------------------------------------------------- applications / interviews / results */
PAGES.apps = async function () {
  var d = (await GET("/api/student/applications")).items;
  return '<h1>My Applications</h1><div class="card">' + tbl(["Company", "Role", "Applied", "Status", "Rounds", "Result"], d.map(function (a) {
    var rounds = a.interviews.length ? a.interviews.map(function (i) { return esc(i.round) + " · " + fmtDate(i.date) + (i.time ? " " + esc(i.time) : ""); }).join("<br>") : "—";
    return [esc(a.company), esc(a.role), fmtDate(a.date), stTag(a.status), rounds, a.status == "Selected" ? "🎉 Selected" : a.status == "Rejected" ? "Rejected" : "Pending"];
  })) + "</div>";
};
PAGES.intv = async function () {
  var d = (await GET("/api/student/interviews")).items;
  return '<h1>Interview Schedule</h1><div class="card">' + (d.length ? tbl(["Company", "Role", "Round", "Date", "Time", "Venue", "Status"], d.map(function (i) {
    return [esc(i.company), esc(i.role), esc(i.round), fmtDate(i.date), esc(i.time || "—"), esc(i.venue || "—"), stTag(i.status)];
  })) : '<p class="mut">No interviews scheduled yet.</p>') + "</div>";
};
PAGES.results = async function () {
  var d = await GET("/api/student/results");
  return '<h1>Placement Results</h1><div class="grid">' + stat(d.total, "Total applications") + stat(d.shortlisted, "Shortlisted") + stat(d.interviews_done, "Final-stage / offers") + stat(d.selected.length, "Selected") +
    '</div><div class="card"><h2>Final status: ' + (d.placed ? '<span class="tag g">Placed</span>' : '<span class="tag a">In progress</span>') + "</h2>" +
    d.selected.map(function (a) { return "<p>🎉 " + esc(a.company) + " – " + esc(a.role) + " (₹" + esc(a.pkg) + " LPA)</p>"; }).join("") +
    (d.placed ? "" : '<p class="mut">Your result will appear here when the placement officer declares an offer.</p>') + "</div>";
};
