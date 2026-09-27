"""
Turn report rows into files.

CSV: UTF-8 with a byte-order mark so Excel shows ₹/€ correctly. Cells that start with = + - @ (or a tab /
carriage return) are prefixed with ' so a spreadsheet shows them as text instead of running them as a
formula ("CSV injection": vendor names and descriptions come from users and imported files).

PDF: reportlab (pure Python, works on Windows). Landscape A4, a header with the filters used, a
table whose header repeats on every page, page numbers, and the "not a finding of fraud" note.
"""

import csv
import io
import json
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
DISCLAIMER = ("Risk scores and alerts are indicators for human review. They are not a determination of fraud. "
              "Bank accounts are shown masked (last 4 digits only).")


def cell_text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def csv_safe(value):
    text = cell_text(value)
    # A plain negative number is data, not a formula: keep it readable.
    if text.startswith(FORMULA_START) and not _is_number(text):
        return "'" + text
    return text


def _is_number(text):
    try:
        float(text)
        return True
    except ValueError:
        return False


def render_csv(report, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([column.header for column in report.columns])
    for row in rows:
        writer.writerow([csv_safe(column.value(row)) for column in report.columns])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


# ---------------------------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------------------------
INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
BRAND = colors.HexColor("#1e3a8a")
GRID = colors.HexColor("#e2e8f0")
STRIPE = colors.HexColor("#f8fafc")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontSize=16, leading=20, alignment=0, textColor=INK, spaceAfter=2),
        "meta": ParagraphStyle("meta", parent=base["Normal"], fontSize=8.5, leading=11, textColor=MUTED),
        "note": ParagraphStyle("note", parent=base["Normal"], fontSize=8, leading=10, textColor=MUTED),
        "head": ParagraphStyle("head", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9,
                               textColor=colors.white),
        "head_right": ParagraphStyle("head_right", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9,
                                     textColor=colors.white, alignment=2),
        "cell": ParagraphStyle("cell", parent=base["Normal"], fontSize=7.5, leading=9, textColor=INK),
        "cell_right": ParagraphStyle("cell_right", parent=base["Normal"], fontSize=7.5, leading=9, textColor=INK, alignment=2),
    }


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin, 8 * mm, "Corporate Expense Fraud & Duplicate Invoice Intelligence Engine")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def render_pdf(report, rows, meta):
    """meta: {"range": "...", "generated": "...", "by": "...", "rows": n, "truncated": bool}"""
    styles = _styles()
    columns = [column for column in report.columns if column.pdf]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=14 * mm, title=report.title,
                            author="Expense Intelligence Engine")
    width = doc.width
    total = sum(column.width for column in columns)
    widths = [width * column.width / total for column in columns]

    def para(value, column):
        return Paragraph(escape(cell_text(value)), styles["cell_right" if column.align == "RIGHT" else "cell"])

    data = [[Paragraph(escape(column.header), styles["head_right" if column.align == "RIGHT" else "head"]) for column in columns]]
    data += [[para(column.value(row), column) for column in columns] for row in rows]

    story = [
        Paragraph(escape(report.title), styles["title"]),
        Paragraph(escape(f"Period: {meta['range']} (by {report.date_basis}) · Generated {meta['generated']} by {meta['by']} "
                         f"· {meta['rows']} row(s) · Times in {meta.get('timezone', 'UTC')}"), styles["meta"]),
        Spacer(1, 3 * mm),
    ]
    if meta.get("truncated"):
        story += [Paragraph(escape(f"Only the first {meta['rows']} rows are shown. Export CSV for the complete data."),
                            styles["note"]), Spacer(1, 2 * mm)]
    if len(data) == 1:
        story.append(Paragraph("No records in this period.", styles["meta"]))
    else:
        table = LongTable(data, colWidths=widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, STRIPE]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, GRID),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)
    story += [Spacer(1, 4 * mm), Paragraph(escape(DISCLAIMER), styles["note"])]
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
