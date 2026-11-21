"""
Pure-Python NLP used by PlaceIQ (no model downloads needed):

* skill extraction with a canonical taxonomy + aliases (word-boundary aware)
* resume section / contact detection and a transparent 100-point score
* skill-gap analysis between a student and job requirements
* TF-IDF + cosine similarity to rank jobs for a student profile
"""
import math
import re
from collections import Counter

# ---------------------------------------------------------------- taxonomy
# canonical name -> list of aliases (all lowercase)
SKILLS = {
    "Python": ["python", "python3"],
    "Java": ["java", "core java"],
    "C": ["c programming", "c language", "embedded c"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "csharp"],
    "JavaScript": ["javascript", "js", "es6", "ecmascript"],
    "TypeScript": ["typescript"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "React": ["react", "reactjs", "react.js"],
    "Angular": ["angular", "angularjs"],
    "Node.js": ["node.js", "nodejs", "node js"],
    "Flask": ["flask"],
    "Django": ["django"],
    "Spring Boot": ["spring boot", "springboot", "spring"],
    "REST API": ["rest api", "restful", "rest apis", "restful api"],
    "SQL": ["sql", "t-sql", "pl/sql"],
    "MySQL": ["mysql"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MongoDB": ["mongodb", "mongo"],
    "Git": ["git", "github", "gitlab"],
    "Docker": ["docker", "containerization"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "Linux": ["linux", "ubuntu", "unix", "bash", "shell scripting"],
    "Data Structures": ["data structures", "data structure", "dsa"],
    "Algorithms": ["algorithms", "algorithm", "problem solving"],
    "OOP": ["oop", "oops", "object oriented", "object-oriented"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "neural network", "neural networks"],
    "NLP": ["nlp", "natural language processing"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "TensorFlow": ["tensorflow"],
    "PyTorch": ["pytorch"],
    "Excel": ["excel", "ms excel", "microsoft excel", "advanced excel"],
    "Statistics": ["statistics", "statistical analysis"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau"],
    "Data Analysis": ["data analysis", "data analytics"],
    "Networking": ["networking", "tcp/ip", "computer networks"],
    "Cyber Security": ["cyber security", "cybersecurity", "information security"],
    "Operating Systems": ["operating systems", "operating system"],
    "DBMS": ["dbms", "database management"],
    "Agile": ["agile", "scrum"],
    "Embedded Systems": ["embedded systems", "embedded", "microcontroller", "microcontrollers"],
    "Arduino": ["arduino"],
    "Raspberry Pi": ["raspberry pi"],
    "MATLAB": ["matlab"],
    "VHDL": ["vhdl"],
    "Verilog": ["verilog"],
    "AutoCAD": ["autocad"],
    "SolidWorks": ["solidworks"],
    "ANSYS": ["ansys"],
    "Communication": ["communication skills", "communication", "public speaking"],
    "Teamwork": ["teamwork", "team work", "collaboration"],
    "Leadership": ["leadership"],
}

# alias -> canonical
_ALIAS = {}
for _canon, _als in SKILLS.items():
    _ALIAS[_canon.lower()] = _canon
    for _a in _als:
        _ALIAS[_a] = _canon

# One compiled regex; longest aliases first so "spring boot" beats "spring".
# bare "c" is too ambiguous for free text; it stays valid for profile normalisation via canon()
_ALIASES_SORTED = sorted((a for a in _ALIAS if a != "c"), key=len, reverse=True)
_SKILL_RE = re.compile(
    r"(?<![A-Za-z0-9+#.])(" + "|".join(re.escape(a) for a in _ALIASES_SORTED) + r")(?![A-Za-z0-9+#]|\.[A-Za-z0-9])",
    re.IGNORECASE,
)


def canon(skill):
    """Normalise a single skill string to its canonical name (or tidy original)."""
    s = (skill or "").strip()
    if not s:
        return ""
    return _ALIAS.get(s.lower(), s)


def split_list(text):
    """Split 'a, b; c / d' style text into a clean list."""
    if not text:
        return []
    return [p.strip() for p in re.split(r"[,;\n|]+", text) if p.strip()]


def skill_set(*texts):
    """Canonical skill set (lowercase keys -> display) from comma lists."""
    out = {}
    for t in texts:
        for p in split_list(t):
            c = canon(p)
            out[c.lower()] = c
    return out


def extract_skills(text):
    """Find taxonomy skills mentioned in free text (resume)."""
    found = {}
    for m in _SKILL_RE.finditer(text or ""):
        c = _ALIAS[m.group(1).lower()]
        found[c] = found.get(c, 0) + 1
    # single-letter 'C' via aliases is only matched through explicit phrases (avoids false positives)
    return found


# ---------------------------------------------------------------- resume analysis
SECTION_PATTERNS = {
    "summary": r"^\s*(professional\s+)?(summary|objective|profile|about\s+me|career\s+objective)\s*:?\s*$",
    "education": r"^\s*(education|academic(s| background| details)?|qualifications?)\s*:?\s*$",
    "skills": r"^\s*(technical\s+)?(skills|skill\s*set|core\s+competencies|technologies)\s*:?\s*$",
    "projects": r"^\s*(academic\s+|personal\s+)?projects?\s*:?\s*$",
    "experience": r"^\s*(work\s+)?(experience|internships?|work\s+history|employment)\s*:?\s*$",
    "certifications": r"^\s*(certifications?|certificates?|courses?|licenses?)\s*:?\s*$",
    "achievements": r"^\s*(achievements?|awards?|honou?rs|extra[\s-]?curricular(s)?|activities)\s*:?\s*$",
}
ACTION_VERBS = {
    "built", "developed", "designed", "implemented", "created", "led", "managed", "optimized",
    "optimised", "improved", "reduced", "increased", "automated", "deployed", "engineered",
    "analyzed", "analysed", "integrated", "launched", "architected", "delivered", "collaborated",
    "migrated", "tested", "configured", "trained", "achieved",
}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s-]?)?(?:\d[\s-]?){9,11}\d")
LINK_RE = re.compile(r"(linkedin\.com/\S+|github\.com/\S+)", re.I)
METRIC_RE = re.compile(r"\d+\s*%|\b\d{2,}\+?\s*(users|students|records|requests|ms|seconds|customers|downloads)\b|\b\d+x\b", re.I)


def split_sections(text):
    """Return {section: text} using heading detection (line based)."""
    sections, cur = {}, "header"
    for line in (text or "").splitlines():
        stripped = line.strip()
        hit = None
        if 0 < len(stripped) <= 40:
            for name, pat in SECTION_PATTERNS.items():
                if re.match(pat, stripped, re.I):
                    hit = name
                    break
        rest = ""
        if not hit and ":" in stripped[:40]:          # inline heading, e.g. "Skills: Python, Flask"
            head, tail = stripped.split(":", 1)
            for name, pat in SECTION_PATTERNS.items():
                if re.match(pat, head.strip(), re.I):
                    hit, rest = name, tail.strip()
                    break
        if hit:
            cur = hit
            sections.setdefault(cur, "")
            if rest:
                sections[cur] += rest + "\n"
        else:
            sections[cur] = sections.get(cur, "") + line + "\n"
    return sections


def analyse_resume(text, profile=None, market_skills=None):
    """
    Score a resume out of 100 and produce suggestions.

    text           : extracted resume text
    profile        : dict(name, email, cgpa, skills, ...) – optional, used for consistency hints
    market_skills  : iterable of skills demanded by posted jobs – used for 'suggested skills'
    """
    profile = profile or {}
    text = text or ""
    words = re.findall(r"[A-Za-z][A-Za-z+#.\-]*", text)
    wc = len(words)
    sec = split_sections(text)
    lower = text.lower()

    emails = EMAIL_RE.findall(text)
    phones = PHONE_RE.findall(text)
    links = LINK_RE.findall(text)
    has_sec = {k: bool(sec.get(k, "").strip()) for k in SECTION_PATTERNS}
    skills_found = extract_skills(text)
    skill_names = sorted(skills_found, key=lambda s: (-skills_found[s], s))

    # ---- scoring (transparent; sums to 100)
    breakdown = {}
    breakdown["Contact details"] = (5 if emails else 0) + (5 if phones else 0)           # /10
    breakdown["Summary"] = 5 if has_sec["summary"] else 0                                # /5
    breakdown["Education"] = 15 if has_sec["education"] else (6 if re.search(r"b\.?\s?e\b|b\.?\s?tech|bachelor|cgpa|gpa", lower) else 0)
    breakdown["Skills"] = min(len(skill_names), 10) * 2 + (5 if has_sec["skills"] else 0)  # /25
    breakdown["Projects"] = (12 if has_sec["projects"] else 0) + (
        8 if has_sec["projects"] and len(sec["projects"].split()) >= 40 else (4 if has_sec["projects"] else 0))  # /20
    breakdown["Experience"] = 5 if has_sec["experience"] else 0
    breakdown["Certifications"] = 5 if has_sec["certifications"] else 0
    breakdown["Links"] = 5 if links else 0
    verbs = sum(1 for w in words if w.lower() in ACTION_VERBS)
    metrics = len(METRIC_RE.findall(text))
    breakdown["Impact (verbs/metrics)"] = min(verbs, 4) + (min(metrics, 2) * 1)           # /6
    ideal = 1 if 200 <= wc <= 900 else 0
    breakdown["Length"] = 4 if ideal else (2 if wc >= 100 else 0)                         # /4
    # maximum per component: 10+5+15+25+20+5+5+5+6+4 = 100
    score = min(100, sum(breakdown.values()))

    expected = ["education", "skills", "projects", "experience", "certifications", "summary"]
    completeness = round(100 * sum(1 for e in expected if has_sec[e]) / len(expected))

    # ---- suggestions
    tips = []
    if not emails:
        tips.append("Add a professional email address at the top of your resume.")
    if not phones:
        tips.append("Add a reachable phone number.")
    if not has_sec["summary"]:
        tips.append("Add a 2–3 line summary/objective stating your target role and strongest skills.")
    if not has_sec["skills"]:
        tips.append("Add a dedicated 'Skills' section and place it above projects.")
    if len(skill_names) < 6:
        tips.append("Only %d recognised technical skills found – list the tools, languages and frameworks you actually use." % len(skill_names))
    if not has_sec["projects"]:
        tips.append("Add a 'Projects' section with 2–3 projects, each with the tech stack and your role.")
    elif metrics == 0:
        tips.append("Add measurable results to projects (e.g. 'reduced search time by 40%', 'served 200+ users').")
    if verbs < 3:
        tips.append("Start bullet points with strong action verbs such as Built, Designed, Implemented, Optimised.")
    if not has_sec["experience"]:
        tips.append("Add an internship, open-source contribution or freelance work, even if short.")
    if not has_sec["certifications"]:
        tips.append("Add relevant certifications (NPTEL, Coursera, vendor certifications).")
    if not links:
        tips.append("Add your GitHub and LinkedIn links, plus deployed project URLs.")
    if wc < 150:
        tips.append("The resume looks very short (%d words). Expand projects and skills with specific details." % wc)
    elif wc > 900:
        tips.append("The resume is long (%d words). Aim for a focused one-page (two at most) document." % wc)
    if not tips:
        tips.append("Strong resume. Keep it updated and tailor the skills section to each job description.")

    # ---- consistency with profile
    notes = []
    prof_skills = skill_set(profile.get("skills"), profile.get("languages"))
    not_in_resume = [v for k, v in prof_skills.items() if v not in skills_found and k not in [s.lower() for s in skills_found]]
    if not_in_resume:
        notes.append("Skills in your profile but not in your resume: " + ", ".join(not_in_resume[:8]))
    new_for_profile = [s for s in skill_names if s.lower() not in prof_skills]
    if new_for_profile:
        notes.append("Skills found in your resume but missing from your profile: " + ", ".join(new_for_profile[:8]))

    # ---- suggested skills (market demand not on resume)
    suggested = []
    if market_skills:
        have = {s.lower() for s in skill_names} | set(prof_skills)
        cnt = Counter(canon(s) for s in market_skills if canon(s))
        suggested = [s for s, _ in cnt.most_common() if s.lower() not in have][:6]

    # ---- projects (best effort) from the projects section
    projects = []
    for ln in sec.get("projects", "").splitlines():
        ln = ln.strip(" \t•-–*·")
        if 3 < len(ln) <= 90 and not ln.endswith(".") and len(projects) < 6:
            projects.append(ln)

    # ---- education line
    edu = ""
    m = re.search(r"(b\.?\s?e\.?|b\.?\s?tech|bachelor[^\n]{0,40}|m\.?\s?tech)[^\n]{0,80}", text, re.I)
    if m:
        edu = m.group(0).strip()
    cg = re.search(r"(cgpa|gpa)\s*[:\-]?\s*(\d{1,2}(?:\.\d{1,2})?)", text, re.I)

    return {
        "score": int(score),
        "completeness": completeness,
        "word_count": wc,
        "breakdown": breakdown,
        "skills_found": skill_names,
        "suggested_skills": suggested,
        "projects_found": projects,
        "contact": {
            "email": emails[0] if emails else "",
            "phone": phones[0].strip() if phones else "",
            "links": [l if isinstance(l, str) else l[0] for l in links][:3],
        },
        "education": edu,
        "cgpa_in_resume": cg.group(2) if cg else "",
        "sections_present": [k for k, v in has_sec.items() if v],
        "sections_missing": [k for k in expected if not has_sec[k]],
        "recommendations": tips,
        "consistency_notes": notes,
    }


# ---------------------------------------------------------------- matching
def skill_match(student_skills, job_skills):
    """student_skills: dict lower->display ; job_skills: list[str]. Returns have/missing/pct."""
    req = []
    for s in job_skills:
        c = canon(s)
        if c and c not in req:
            req.append(c)
    have = [s for s in req if s.lower() in student_skills]
    miss = [s for s in req if s.lower() not in student_skills]
    pct = round(100 * len(have) / len(req)) if req else 100
    return {"have": have, "missing": miss, "pct": pct}


_STOP = set("a an the and or of to in for with on at by from as is are was were be been this that these those it its into using use used based".split())


def tokens(text):
    return [t for t in re.findall(r"[a-z][a-z0-9+#.]{1,}", (text or "").lower()) if t not in _STOP]


def tfidf_similarity(query_text, docs):
    """Cosine similarity between query_text and each doc (list[str]) using TF-IDF over the docs+query."""
    corpus = [tokens(d) for d in docs] + [tokens(query_text)]
    n = len(corpus)
    df = Counter()
    for toks in corpus:
        df.update(set(toks))
    idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}

    def vec(toks):
        tf = Counter(toks)
        return {t: (c / (len(toks) or 1)) * idf[t] for t, c in tf.items()}

    vecs = [vec(t) for t in corpus]
    q = vecs[-1]
    qn = math.sqrt(sum(v * v for v in q.values())) or 1.0
    sims = []
    for v in vecs[:-1]:
        dot = sum(w * v.get(t, 0.0) for t, w in q.items())
        vn = math.sqrt(sum(x * x for x in v.values())) or 1.0
        sims.append(dot / (qn * vn))
    return sims
