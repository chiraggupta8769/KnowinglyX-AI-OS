"""
ATS-friendly PDF generator — professional, clean, single-column layout.
"""
from __future__ import annotations

import io
import re

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER

COLOR_BLACK = HexColor("#000000")
COLOR_HEADER = HexColor("#1a1a2e")
COLOR_SECTION = HexColor("#2d2d2d")
COLOR_BODY = HexColor("#333333")
COLOR_LINE = HexColor("#999999")
COLOR_CONTACT = HexColor("#555555")

SECTION_KEYWORDS = {
    "SUMMARY", "PROFESSIONAL SUMMARY", "OBJECTIVE", "PROFILE",
    "EXPERIENCE", "WORK EXPERIENCE", "PROFESSIONAL EXPERIENCE",
    "SKILLS", "TECHNICAL SKILLS", "CORE COMPETENCIES", "KEY SKILLS",
    "EDUCATION", "CERTIFICATIONS", "PROJECTS", "ACHIEVEMENTS", "AWARDS",
    "PUBLICATIONS", "LANGUAGES", "VOLUNTEER", "TARGET ROLES", "STRENGTHS",
}


def _is_section_header(line: str) -> bool:
    clean = line.strip().rstrip(":").upper()
    if clean in SECTION_KEYWORDS:
        return True
    # All-caps lines 3–40 chars, no numbers
    if line.isupper() and 3 <= len(line.strip()) <= 40 and not re.search(r'\d{4}', line):
        return True
    return False


def _is_date_line(line: str) -> bool:
    return bool(re.search(r'\d{4}', line) and re.search(r'–|-|Present|Current|Now', line))


def _is_bullet(line: str) -> bool:
    return line.strip().startswith(("•", "-", "*", "·", "–"))


def generate_resume_pdf(resume_text: str, candidate_name: str = "") -> bytes:
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    name_style = ParagraphStyle(
        "Name", fontName="Helvetica-Bold", fontSize=20, leading=24,
        textColor=COLOR_HEADER, alignment=TA_CENTER, spaceAfter=2,
    )
    contact_style = ParagraphStyle(
        "Contact", fontName="Helvetica", fontSize=10, leading=14,
        textColor=COLOR_CONTACT, alignment=TA_CENTER, spaceAfter=6,
    )
    section_style = ParagraphStyle(
        "Section", fontName="Helvetica-Bold", fontSize=11, leading=15,
        textColor=COLOR_SECTION, spaceBefore=12, spaceAfter=3,
    )
    job_header_style = ParagraphStyle(
        "JobHeader", fontName="Helvetica-Bold", fontSize=10, leading=14,
        textColor=COLOR_BLACK, spaceAfter=1,
    )
    date_style = ParagraphStyle(
        "Date", fontName="Helvetica-Oblique", fontSize=9, leading=12,
        textColor=COLOR_CONTACT, spaceAfter=3,
    )
    bullet_style = ParagraphStyle(
        "Bullet", fontName="Helvetica", fontSize=10, leading=14,
        textColor=COLOR_BODY, leftIndent=14, spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "Body", fontName="Helvetica", fontSize=10, leading=14,
        textColor=COLOR_BODY, spaceAfter=2,
    )

    story = []
    lines = resume_text.strip().split("\n")

    name_written = False
    contact_buffer = []
    i = 0

    # --- Detect name and contact lines at top ---
    while i < len(lines) and i < 6:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        is_contact = bool(re.search(r'[@|]|\+?\d[\d\s\-]{7,}|linkedin\.com|github\.com|http', line, re.I))
        is_section = _is_section_header(line)

        if not name_written and not is_contact and not is_section:
            story.append(Paragraph(x(line), name_style))
            name_written = True
            i += 1
            continue

        if is_contact or (name_written and not is_section and i < 5):
            contact_buffer.append(line)
            i += 1
            continue

        break

    if contact_buffer:
        story.append(Paragraph(x(" · ".join(contact_buffer)), contact_style))

    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_LINE, spaceAfter=6))

    # --- Body ---
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line:
            story.append(Spacer(1, 4))
            continue

        if _is_section_header(line):
            story.append(Paragraph(x(line.rstrip(":").upper()), section_style))
            story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#cccccc"), spaceAfter=4))

        elif _is_date_line(line):
            story.append(Paragraph(x(line), date_style))

        elif _is_bullet(line):
            text = line.lstrip("•-*·– ").strip()
            story.append(Paragraph(f"• {x(text)}", bullet_style))

        elif line.isupper() or (len(line) < 60 and not line.endswith(".")):
            # Likely a job title or company name
            story.append(Paragraph(x(line), job_header_style))

        else:
            story.append(Paragraph(x(line), body_style))

    doc.build(story)
    return buffer.getvalue()


def x(text: str) -> str:
    """Escape XML special chars for ReportLab."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
