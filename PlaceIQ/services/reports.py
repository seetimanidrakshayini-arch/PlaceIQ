"""PDF placement report (ReportLab)."""
import io
from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def _table(rows, widths=None):
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def build_pdf(institution, season, s, placed):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="PlaceIQ Placement Report")
    st = getSampleStyleSheet()
    el = [Paragraph("PlaceIQ – Placement Report", st["Title"]),
          Paragraph("%s &nbsp;|&nbsp; Season %s &nbsp;|&nbsp; Generated %s" % (institution or "Institution", season or "-", date.today().strftime("%d %b %Y")), st["Normal"]),
          Spacer(1, 8)]
    el.append(_table([["Registered students", "Companies", "Active jobs", "Applications", "Students placed", "Placement rate"],
                      [s["students"], s["companies"], s["jobs"], s["applications"], s["placed"], "%d%%" % s["placement_rate"]]]))
    el.append(Spacer(1, 6))
    el.append(_table([["Average package", "Highest package", "Lowest package"],
                      ["%.2f LPA" % s["avg_pkg"], "%.2f LPA" % s["max_pkg"], "%.2f LPA" % s["min_pkg"]]]))
    el += [Spacer(1, 10), Paragraph("Applications by status", st["Heading2"]),
           _table([["Status", "Count"]] + [[a, b] for a, b in s["by_status"]], [90 * mm, 30 * mm])]
    el += [Spacer(1, 10), Paragraph("Department-wise placement", st["Heading2"]),
           _table([["Department", "Students", "Placed", "Rate"]] + [[d["dept"], d["students"], d["placed"], "%d%%" % d["rate"]] for d in s["by_dept"]])]
    el += [Spacer(1, 10), Paragraph("Company-wise applications", st["Heading2"]),
           _table([["Company", "Applications", "Selected"]] + [[c["name"], c["apps"], c["selected"]] for c in s["by_company"]])]
    el += [Spacer(1, 10), Paragraph("Placed students", st["Heading2"])]
    if placed:
        el.append(_table([["USN", "Name", "Dept", "Company", "Role", "LPA"]] +
                         [[p["usn"], p["name"], p["dept"], p["company"], p["role"], "%.2f" % float(p["package_lpa"])] for p in placed]))
    else:
        el.append(Paragraph("No placements declared yet.", st["Normal"]))
    doc.build(el)
    return buf.getvalue()
