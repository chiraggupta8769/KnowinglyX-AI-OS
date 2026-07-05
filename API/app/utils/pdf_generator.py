"""
ATS-friendly PDF generator using reportlab.
Produces clean, single-column, parseable PDFs.
"""
from __future__ import annotations

import io
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER


# ATS-safe colors
COLOR_BLACK = HexColor("#000000")
COLOR_DARK = HexColor("#1a1a1a")
COLOR_MID = HexColor("#333333")
COLOR_LINE = HexColor("#cccccc")


def generate_resume_pdf(resume_text: str, candidate_name: str = "") -> bytes:
    """
    Convert plain resume text into an ATS-friendly PDF.
    Returns PDF as bytes.
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()

    name_style = ParagraphStyle(
        "Name",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=COLOR_BLACK,
        alignment=TA_CENTER,
        spaceAfter=4,
    )

    contact_style = ParagraphStyle(
        "Contact",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=COLOR_MID,
        alignment=TA_CENTER,
        spaceAfter=8,
    )

    section_style = ParagraphStyle(
        "Section",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=COLOR_BLACK,
        spaceBefore=10,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=COLOR_DARK,
        spaceAfter=2,
        leftIndent=0,
    )

    bullet_style = ParagraphStyle(
        "Bullet",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=COLOR_DARK,
        spaceAfter=2,
        leftIndent=12,
        bulletIndent=0,
    )

    job_title_style = ParagraphStyle(
        "JobTitle",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=COLOR_DARK,
        spaceAfter=1,
    )

    story = []
    lines = resume_text.strip().split("\n")

    # Section headers (all caps lines)
    SECTION_KEYWORDS = {
        "SUMMARY", "EXPERIENCE", "WORK EXPERIENCE", "SKILLS", "TECHNICAL SKILLS",
        "EDUCATION", "CERTIFICATIONS", "PROJECTS", "ACHIEVEMENTS", "AWARDS",
        "PUBLICATIONS", "LANGUAGES", "INTERESTS", "OBJECTIVE", "PROFILE",
        "PROFESSIONAL EXPERIENCE", "CORE COMPETENCIES", "VOLUNTEER",
    }

    # Try to detect name from first non-empty line
    name_detected = False
    contact_lines = []

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # Check if it's a section header
        upper = line.upper().rstrip(":").strip()
        is_section = (
            upper in SECTION_KEYWORDS
            or (line.isupper() and len(line) > 3 and len(line) < 50)
        )

        # Name detection (first real line, not email/phone)
        is_contact = bool(re.search(r'[@|]|\d{3}|\+\d|linkedin\.com|github\.com', line, re.I))

        if not name_detected and not is_contact and not is_section and i < 5:
            # Likely the candidate name
            story.append(Paragraph(escape_xml(line), name_style))
            name_detected = True
            continue

        if not name_detected and is_contact and i < 5:
            contact_lines.append(escape_xml(line))
            continue

        if contact_lines and not name_detected:
            # Flush contact lines
            for cl in contact_lines:
                story.append(Paragraph(cl, contact_style))
            contact_lines = []

        if is_section:
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_LINE))
            story.append(Paragraph(line.rstrip(":").upper(), section_style))

        elif line.startswith("•") or line.startswith("-") or line.startswith("*"):
            bullet_text = line.lstrip("•-* ").strip()
            story.append(Paragraph(f"• {escape_xml(bullet_text)}", bullet_style))

        elif re.search(r'\d{4}', line) and ("–" in line or "-" in line or "Present" in line or "Current" in line):
            # Date line — treat as job title/date
            story.append(Paragraph(escape_xml(line), job_title_style))

        elif line:
            story.append(Paragraph(escape_xml(line), body_style))

    # Flush any remaining contact lines
    for cl in contact_lines:
        story.append(Paragraph(cl, contact_style))

    doc.build(story)
    return buffer.getvalue()


def escape_xml(text: str) -> str:
    """Escape characters that break ReportLab XML parsing."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
