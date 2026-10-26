"""Resume export: tailored PDF + DOCX + LaTeX (single-column, ATS-safe).

Section order (frozen by user): name, details, summary, education,
experience, projects, skills, certifications, co-curricular activities.

Readability rules (why this file parses instead of joining lists):
- The resume's own Skills block is kept as labelled lines ("Languages: …")
  and rendered one group per line instead of one comma soup paragraph.
- Education lines are grouped per institution (institution + detail line)
  instead of one bullet per fragment.
- Experience/projects keep an entry title + its bullets; leading bullet
  glyphs from parsed PDFs are stripped so documents never show "• - …".

Honesty rule (§§10 validator): only profile facts + LLM summary + upskill
list. Never fabricate — High gaps are listed under "Areas to Upskill",
never as fake bullets. PDF prefers the LaTeX toolchain (same template as
.tex); reportlab below is the fallback with the identical section order.
"""
from __future__ import annotations

import io
import re

from app.tools import contact_extract

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")
# Bullet glyphs seen in pasted text and in PDF-extracted text. PDF tools map
# bullets to many symbols — including en/em dashes and private-use glyphs —
# so include those or a "– Built …" line is misread as a project title.
_BULLET_CHARS = ("\u2022\u25aa\u25e6\u00b7\u2023\u2043\u2219\u25cf\u25cb"
                 "\u2010-\u2015\u2212\ufffd\uf000-\uf8ff")
_BULLET = re.compile(
    rf"^\s*(?:[{_BULLET_CHARS}]|[-*+](?=\s))\s*")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_INSTITUTIONS = ("university", "college", "institute", "school", "academy",
                 "polytechnic", "vidyalaya", "convent", "iit", "nit", "iiit")
_LINKS = {"github", "gitlab", "live", "demo", "live demo", "website", "link"}

_MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_YEAR = r"(?:19|20)\d{2}"
_DATE_TOKEN = rf"(?:{_MONTHS}\s*{_YEAR}|{_YEAR}|present|current|ongoing)"
_DASH = r"[-\u2010-\u2015\u2212\ufffd]"
_DATE_RANGE = re.compile(
    rf"^\s*({_DATE_TOKEN})\s*(?:{_DASH}|to)\s*({_DATE_TOKEN})\s*$", re.I)
_DATE_SINGLE = re.compile(
    rf"^\s*(?:expected\s+(?:graduation|completion)\s*:?\s*)?({_DATE_TOKEN})\s*$", re.I)


def _strip_bullet(line: str) -> str:
    """Remove every leading bullet glyph (handles doubled markers like '• - ')."""
    for _ in range(4):
        stripped = _BULLET.sub("", line).strip()
        if stripped == line:
            break
        line = stripped
    return line


def _clean(line: str) -> str:
    """Strip bullet glyphs/mojibake and collapse whitespace. Never drops text."""
    line = _CTRL.sub("", line or "")
    line = re.sub(r"\s+", " ", line).strip()
    return _strip_bullet(line)


def _is_date(line: str) -> bool:
    return bool(_DATE_RANGE.match(line or "") or _DATE_SINGLE.match(line or ""))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = (item or "").strip()
        if key and key.lower() not in seen:
            seen.add(key.lower())
            out.append(key)
    return out


def _is_bullet(raw: str) -> bool:
    return bool(_BULLET.match(raw or ""))


def _is_inst(line: str) -> bool:
    lowered = line.lower()
    return any(word in lowered for word in _INSTITUTIONS)


def _is_linkish(line: str) -> bool:
    lowered = line.lower().strip(" .:")
    return (lowered in _LINKS or lowered.startswith("http")
            or "github.com/" in lowered or "github" == lowered)


def _new_entry(title: str = "") -> dict:
    return {"title": title, "date": "", "link": "", "bullets": [], "details": []}


def _group_education(lines: list[str]) -> list[dict]:
    """One entry per institution; date lines right-align, rest are details.

    Institution detection is the anchor: a new school/college starts a new
    block even when its name has no generic keyword (e.g. "Tip Top Convent").
    Dates never overwrite an existing date, so a following qualification
    cannot silently steal the college's year.
    """
    entries: list[dict] = []
    for raw in lines:
        line = _clean(raw)
        if not line:
            continue
        if _is_date(line):
            if not entries:
                entries.append(_new_entry(""))
            if not entries[-1]["date"]:
                entries[-1]["date"] = line
            continue
        if _is_inst(line):
            if entries and not entries[-1]["title"]:
                entries[-1]["title"] = line
            else:
                entries.append(_new_entry(line))
            continue
        if not entries:
            entries.append(_new_entry(""))
        entries[-1]["details"].append(line)
    return entries


def _joins(previous: str, line: str) -> bool:
    """A wrapped PDF line continues the previous bullet when it starts
    lowercase or the previous bullet has no terminal punctuation."""
    if not previous:
        return False
    if line[:1].islower():
        return True
    return previous.rstrip()[-1:] not in ".!?;:"


def _group_entries(lines: list[str]) -> list[dict]:
    """Parse title / right-aligned date / link / details / bullets into entries.

    PDF text wraps bullets across lines and often uses an en dash as the
    bullet glyph. Both are folded back into one clean bullet so a project
    renders as a heading plus bullets, never a pile of stray lines. Lines
    after a date (issuer, location, tech stack) are details, capped at two
    so a following entry title is not swallowed.
    """
    entries: list[dict] = []
    for raw in lines:
        line = _clean(raw)
        if not line:
            continue
        if _is_bullet(raw):
            text = _strip_bullet(line)
            if not text:
                continue
            if entries:
                entries[-1]["bullets"].append(text)
            else:
                entries.append(_new_entry(text))
            continue
        if entries and _is_date(line):
            if not entries[-1]["date"]:
                entries[-1]["date"] = line
            continue
        if entries and _is_linkish(line):
            entries[-1]["link"] = line
            continue
        if entries and line.startswith("|"):
            # "IIT Roorkee ..." + "| Certificate" is a badge label, not part
            # of the role; keep real pipe metadata (e.g. "| GitHub") though.
            extra = line.lstrip("|").strip()
            if extra.lower() not in {"certificate", "certification", "credential"}:
                entries[-1]["title"] = f"{entries[-1]['title']} | {extra}".strip()
            continue
        if entries and entries[-1]["bullets"]:
            previous = entries[-1]["bullets"][-1]
            if _joins(previous, line):
                entries[-1]["bullets"][-1] = previous + " " + line
                continue
        elif (entries and entries[-1]["date"] and not entries[-1]["bullets"]
              and len(entries[-1]["details"]) < 2):
            entries[-1]["details"].append(line)
            continue
        entries.append(_new_entry(line))
    return entries


def _group_certifications(lines: list[str]) -> list[dict]:
    """One entry per credential; a following date attaches to it.

    PDFs often wrap the issuer onto the next line ("AICTE NEAT – ..."). That
    is kept as a detail, while a line that names another credential starts a
    new entry instead of being merged into the previous one.
    """
    hints = re.compile(
        r"(?i)\b(?:certificat\w*|certified|nanodegree|speciali[sz]ation|"
        r"job simulation|internship|training|award|course|program)\b")
    entries: list[dict] = []
    for raw in lines:
        line = _clean(raw)
        if not line:
            continue
        if _is_date(line):
            if not entries:
                entries.append(_new_entry(""))
            if not entries[-1]["date"]:
                entries[-1]["date"] = line
            else:
                entries.append(_new_entry(""))
                entries[-1]["date"] = line
            continue
        if not entries:
            entries.append(_new_entry(line))
            continue
        current = entries[-1]
        if (current["details"]
                or (current["date"] and (hints.search(line)))
                or (not current["date"] and hints.search(line)
                    and current["title"])):
            entries.append(_new_entry(line))
        else:
            current["details"].append(line)
    return [e for e in entries if e["title"] or e["date"] or e["details"]]


def _group_activities(lines: list[str]) -> list[dict]:
    """Activities render as one flat bullet list (no bold pseudo-titles)."""
    bullets = [_clean(line) for line in lines if _clean(line)]
    if not bullets:
        return []
    return [{"title": "", "date": "", "link": "", "bullets": bullets,
             "details": []}]


def _skill_groups(lines: list[str], candidate: list[str]) -> list[dict]:
    """Keep labelled groups from the resume ("Cloud: AWS, S3"); else chunk."""
    groups: list[dict] = []
    for raw in lines:
        line = _clean(raw)
        if not line:
            continue
        if ":" in line:
            label, rest = line.split(":", 1)
            items = [i.strip() for i in rest.split(",") if i.strip()]
            groups.append({"label": label.strip()[:40], "items": items or [rest.strip()]})
        else:
            items = [i.strip() for i in line.split(",") if i.strip()]
            groups.append({"label": "", "items": items})
    if not groups and candidate:
        items = _dedupe(candidate)
        for i in range(0, len(items), 4):
            groups.append({"label": "", "items": items[i:i + 4]})
    return groups[:8]


def _fallback_summary(role: str, skills: list[str], required: list[str]) -> str:
    """No LLM summary? A short factual line beats boilerplate. Never gaps."""
    req = {r.lower() for r in (required or [])}
    matched = [s for s in skills if s.lower() in req]
    rest = [s for s in skills if s.lower() not in req]
    top = (matched + rest)[:5]
    if top and role:
        return f"{role} candidate with hands-on experience in {', '.join(top)}."
    if top:
        return f"Candidate with hands-on experience in {', '.join(top)}."
    return ""


def _infer_title(header: list[str], role: str) -> str:
    """Short role line from the header (e.g. 'Full Stack Developer')."""
    for raw in header[1:]:
        line = _clean(raw)
        if not line or _EMAIL.search(line) or _PHONE.search(line):
            continue
        if contact_extract.is_heading(raw):
            continue
        lowered = line.lower()
        if lowered.startswith(("http", "www.", "linkedin", "github")):
            continue
        if len(line) > 45 or len(line.split()) > 6 or line.endswith("."):
            continue
        return line
    return (role or "").strip()


def build_export_data(result: dict, resume_text: str = "") -> dict:
    """Assemble export content from a stored pipeline/graph result."""
    resume_text = (resume_text or result.get("_resume_text")
                   or result.get("resume_text") or "")
    sections = contact_extract.split_sections(resume_text)
    contact = contact_extract.extract_contact(resume_text)
    if not contact["email"]:
        contact["email"] = (_EMAIL.findall(resume_text) or [""])[0]
    if not contact["phone"]:
        phones = _PHONE.findall(resume_text)
        contact["phone"] = re.sub(r"\s+", " ", phones[0]).strip() if phones else ""
    # PDFs often keep the LinkedIn/GitHub handle in a hyperlink annotation,
    # so the plain text may only say "LinkedIn"/"GitHub". Show the label
    # rather than dropping the contact detail entirely.
    for raw in sections.get("header", []):
        lowered = (raw or "").lower()
        if "linkedin" in lowered and not contact["linkedin"]:
            contact["linkedin_label"] = "LinkedIn"
        if "github" in lowered and not contact["github"]:
            contact["github_label"] = "GitHub"
    optimized = result.get("optimized_resume") or {}
    gaps = result.get("skill_gap", {}) or {}
    candidate = result.get("_candidate", []) or (result.get("candidate_profile") or {}).get("technical", [])
    required = set(result.get("_required", []) or [])
    role = (result.get("jd_profile") or {}).get("role", "") or ""
    picked = {
        "education": sections.get("education", []),
        "experience": sections.get("experience", []),
        "projects": sections.get("projects", []),
        "certifications": [_clean(l) for l in sections.get("certifications", []) if _clean(l)],
        "activities": [_clean(l) for l in sections.get("activities", []) if _clean(l)],
    }
    blocks = {
        "education": _group_education(picked["education"]),
        "experience": _group_entries(picked["experience"]),
        "projects": _group_entries(picked["projects"]),
        "certifications": _group_certifications(picked["certifications"]),
        "activities": _group_activities(picked["activities"]),
    }
    if not any(blocks.values()) and not picked["certifications"] and not picked["activities"]:
        # No headings detected: keep every body line so export is never empty.
        blocks["experience"] = _group_entries(
            [l for l in (resume_text or "").split("\n") if l.strip()])
    skills = _dedupe(candidate)
    groups = _skill_groups(sections.get("skills", []), candidate)
    ordered_skills = [item for group in groups for item in group["items"]] or skills
    original_summary = " ".join(
        _clean(line) for line in sections.get("summary", []) if _clean(line))
    summary = (optimized.get("summary") or "").strip() or original_summary or _fallback_summary(
        role, ordered_skills, sorted(required))
    return {
        "name": contact_extract.extract_name(sections.get("header", [])),
        "title": _infer_title(sections.get("header", []), role),
        "contact": contact,
        "summary": summary,
        "skills": skills,
        "skills_matched": sorted(set(candidate) & required),
        "skill_groups": groups,
        "required": sorted(required),
        # Structured entries (one dict per institution/role/project) are the
        # source of truth; callers that pass plain strings still get rendered.
        "sections": {**picked, "summary": sections.get("summary", []), **blocks},
        "blocks": blocks,
        "upskill": [m["skill"] if isinstance(m, dict) else m
                    for m in (gaps.get("missing", []) or [])][:6],
        "experience_text": resume_text,
        "validation": result.get("validation_result") or {},
    }


_SECTION_ORDER = (
    ("summary", "Professional Summary"),
    ("education", "Education"),
    ("experience", "Experience"),
    ("projects", "Projects"),
    ("skills", "Skills Summary"),
    ("certifications", "Certifications"),
    ("activities", "Co-Curricular Activities"),
)


def _contact_line(contact: dict) -> str:
    bits = [contact.get("email", ""), contact.get("phone", ""),
            contact.get("linkedin") or contact.get("linkedin_label", ""),
            contact.get("github") or contact.get("github_label", "")]
    return " | ".join(b for b in bits if b) or "Contact details in original resume"


def _ordered(lines: list[str], required: list[str], cap: int = 7) -> list[str]:
    """JD-first stable ordering + cap (same facts, original order kept)."""
    if required:
        lines = sorted(lines,
                       key=lambda l: not any(r.lower() in (l or "").lower() for r in required))
    return [l for l in lines if (l or "").strip()][:cap]


def _entry_lines(entries: list[dict], required: list[str], cap: int) -> list[dict]:
    if required:
        def text(entry: dict) -> str:
            return " ".join([entry.get("title", ""), entry.get("link", ""),
                             entry.get("date", "")] + entry.get("details", [])
                            + entry.get("bullets", [])).lower()
        entries = sorted(entries,
                         key=lambda e: not any(r.lower() in text(e) for r in required))
    return entries[:cap]


def _xml(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pdf_entry_heading(entry: dict, styles, width: float) -> object:
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    head = f"<b>{_xml(entry.get('title', ''))}</b>"
    if entry.get("link"):
        head += f"  <i>{_xml(entry['link'])}</i>"
    date = _xml(entry.get("date", ""))
    if not date:
        return Paragraph(head, styles["Normal"])
    table = Table([[Paragraph(head, styles["Normal"]),
                    Paragraph(f'<para align="right">{date}</para>', styles["Normal"])]],
                  colWidths=[width - 90, 90])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LINEBELOW", (0, 0), (-1, -1), 0, colors.white),
    ]))
    return table


def to_pdf(data: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (ListFlowable, ListItem, Paragraph,
                                    SimpleDocTemplate, Spacer)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm,
                            title=f"Resume - {data['name']}")
    styles = getSampleStyleSheet()
    story = [Paragraph(_xml(data["name"]), styles["Title"])]
    if data.get("title"):
        story.append(Paragraph(_xml(data["title"]), styles["Heading3"]))
    story += [Paragraph(_xml(_contact_line(data.get("contact", {}))), styles["Normal"]),
              Spacer(1, 6)]
    blocks = data.get("blocks") or {}
    groups = data.get("skill_groups") or []
    for key, title in _SECTION_ORDER:
        if key == "summary":
            summary = (data.get("summary") or "").strip()
            if not summary:
                continue
            story += [Paragraph(title, styles["Heading2"]),
                      Paragraph(_xml(summary), styles["Normal"]), Spacer(1, 4)]
            continue
        if key == "skills":
            if not groups:
                continue
            story += [Paragraph(title, styles["Heading2"])]
            for group in groups:
                label = f"<b>{_xml(group['label'])}:</b> " if group["label"] else ""
                story.append(Paragraph(label + _xml(", ".join(group["items"])),
                                       styles["Normal"]))
            story.append(Spacer(1, 4))
            continue
        cap = 7
        required = [] if key in {"education", "certifications", "activities"} \
            else data.get("required", [])
        entries = _entry_lines(blocks.get(key, []), required, cap)
        if not entries:
            continue
        story += [Paragraph(title, styles["Heading2"])]
        for entry in entries:
            if entry.get("title") or entry.get("date"):
                story.append(_pdf_entry_heading(entry, styles, doc.width))
            details = [d for d in (entry.get("details") or []) if (d or "").strip()]
            if details:
                story.append(Paragraph("<i>%s</i>" % _xml(" | ".join(details)),
                                       styles["Normal"]))
            bullets = [b for b in entry.get("bullets", []) if (b or "").strip()]
            if bullets:
                story.append(ListFlowable(
                    [ListItem(Paragraph(_xml(b), styles["Normal"]), leftIndent=12)
                     for b in bullets],
                    bulletType="bullet", leftIndent=12))
        story.append(Spacer(1, 4))
    doc.build(story)
    return buf.getvalue()


def to_docx(data: dict) -> bytes:
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    doc.add_heading(data["name"], level=0)
    if data.get("title"):
        doc.add_paragraph(data["title"])
    doc.add_paragraph(_contact_line(data.get("contact", {})))
    blocks = data.get("blocks") or {}
    groups = data.get("skill_groups") or []
    for key, title in _SECTION_ORDER:
        if key == "summary":
            summary = (data.get("summary") or "").strip()
            if not summary:
                continue
            doc.add_heading(title, level=1)
            doc.add_paragraph(summary)
            continue
        if key == "skills":
            if not groups:
                continue
            doc.add_heading(title, level=1)
            for group in groups:
                p = doc.add_paragraph()
                if group["label"]:
                    p.add_run(f"{group['label']}: ").bold = True
                p.add_run(", ".join(group["items"]))
            continue
        cap = 7
        required = [] if key in {"education", "certifications", "activities"} \
            else data.get("required", [])
        entries = _entry_lines(blocks.get(key, []), required, cap)
        if not entries:
            continue
        doc.add_heading(title, level=1)
        for entry in entries:
            if entry.get("title") or entry.get("date"):
                p = doc.add_paragraph()
                p.add_run(entry.get("title", "")).bold = True
                if entry.get("link"):
                    p.add_run(f"  {entry['link']}").italic = True
                if entry.get("date"):
                    p.add_run(f"\t{entry['date']}")
            details = [d for d in (entry.get("details") or []) if (d or "").strip()]
            if details:
                doc.add_paragraph(" | ".join(details)).runs[0].italic = True
            for bullet in entry.get("bullets", [])[:5]:
                doc.add_paragraph(bullet, style="List Bullet")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
