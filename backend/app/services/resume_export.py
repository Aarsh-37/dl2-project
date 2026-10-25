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
# Bullet glyphs seen in pasted text and in PDF-extracted text (incl. the
# U+FFFD mojibake PDF tools emit for bullet/em-dash glyphs).
_BULLET = re.compile(
    r"^\s*(?:[\u2022\u25aa\u25e6\u00b7\u2023\u2043\u2219\u25cf\u25cb*>]"
    r"|[\-*+]\s|\ufffd+\??\ufffd*)\s*")
_MOJIBAKE = re.compile(r"\ufffd\??\ufffd?")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_INSTITUTIONS = ("university", "college", "institute", "school", "academy",
                 "polytechnic", "vidyalaya", "iit", "nit", "iiit")
_LINKS = {"github", "gitlab", "live", "demo", "live demo", "website", "link"}


def _clean(line: str) -> str:
    """Strip bullet glyphs/mojibake and collapse whitespace. Never drops text."""
    line = _CTRL.sub("", line or "")
    line = _MOJIBAKE.sub("-", line)
    line = re.sub(r"\s+", " ", line).strip()
    line = _BULLET.sub("", line).strip()
    return line


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


def _group_education(lines: list[str]) -> list[dict]:
    """One entry per institution; the following lines become its details."""
    entries: list[dict] = []
    for raw in lines:
        line = _clean(raw)
        if not line:
            continue
        if not entries or _is_inst(line):
            entries.append({"title": line, "details": []})
        else:
            entries[-1]["details"].append(line)
    return entries


def _group_entries(lines: list[str]) -> list[dict]:
    """Entry title (non-bullet) + link line + bullets, in original order."""
    entries: list[dict] = []
    for raw in lines:
        line = _clean(raw)
        if not line:
            continue
        if entries and _is_linkish(line):
            entries[-1]["link"] = line
        elif entries and (_is_bullet(raw) or line[:1].islower()):
            entries[-1]["bullets"].append(line)
        else:
            entries.append({"title": line, "link": "", "bullets": []})
    return entries


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


def build_export_data(result: dict, resume_text: str = "") -> dict:
    """Assemble export content from a stored pipeline/graph result."""
    resume_text = resume_text or result.get("_resume_text", "")
    sections = contact_extract.split_sections(resume_text)
    contact = contact_extract.extract_contact(resume_text)
    if not contact["email"]:
        contact["email"] = (_EMAIL.findall(resume_text) or [""])[0]
    if not contact["phone"]:
        phones = _PHONE.findall(resume_text)
        contact["phone"] = re.sub(r"\s+", " ", phones[0]).strip() if phones else ""
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
    }
    if not any(blocks.values()) and not picked["certifications"] and not picked["activities"]:
        # No headings detected: keep every body line so export is never empty.
        blocks["experience"] = _group_entries(
            [l for l in (resume_text or "").split("\n") if l.strip()])
    skills = _dedupe(candidate)
    groups = _skill_groups(sections.get("skills", []), candidate)
    ordered_skills = [item for group in groups for item in group["items"]] or skills
    summary = (optimized.get("summary") or "").strip() or _fallback_summary(
        role, ordered_skills, sorted(required))
    return {
        "name": contact_extract.extract_name(sections.get("header", [])),
        "contact": contact,
        "summary": summary,
        "skills": skills,
        "skills_matched": sorted(set(candidate) & required),
        "skill_groups": groups,
        "required": sorted(required),
        # Structured entries (one dict per institution/role/project) are the
        # source of truth; callers that pass plain strings still get rendered.
        "sections": {
            **picked,
            "education": blocks["education"],
            "experience": blocks["experience"],
            "projects": blocks["projects"],
        },
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
            contact.get("linkedin", ""), contact.get("github", "")]
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
            return " ".join([entry.get("title", ""), entry.get("link", "")]
                            + entry.get("bullets", [])).lower()
        entries = sorted(entries,
                         key=lambda e: not any(r.lower() in text(e) for r in required))
    return entries[:cap]


def _xml(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
    story = [Paragraph(_xml(data["name"]), styles["Title"]),
             Paragraph(_xml(_contact_line(data.get("contact", {}))), styles["Normal"]),
             Spacer(1, 6)]
    blocks = data.get("blocks") or {}
    groups = data.get("skill_groups") or []
    body = {
        "summary": [data.get("summary", "")],
        "certifications": _ordered(data["sections"].get("certifications", []), data.get("required", [])),
        "activities": _ordered(data["sections"].get("activities", []), data.get("required", [])),
    }
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
        if key in {"education", "experience", "projects"}:
            cap = 7
            required = [] if key == "education" else data.get("required", [])
            entries = _entry_lines(blocks.get(key, []), required, cap)
            if not entries:
                continue
            story += [Paragraph(title, styles["Heading2"])]
            for entry in entries:
                head = f"<b>{_xml(entry.get('title', ''))}</b>"
                if entry.get("link"):
                    head += f"  <i>{_xml(entry['link'])}</i>"
                story.append(Paragraph(head, styles["Normal"]))
                details = entry.get("details") or []
                if details:
                    story.append(Paragraph(_xml(" | ".join(details)), styles["Normal"]))
                bullets = [b for b in entry.get("bullets", []) if (b or "").strip()]
                if bullets:
                    story.append(ListFlowable(
                        [ListItem(Paragraph(_xml(b), styles["Normal"]), leftIndent=12)
                         for b in bullets],
                        bulletType="bullet", leftIndent=12))
            story.append(Spacer(1, 4))
            continue
        lines = [l for l in body.get(key, []) if (l or "").strip()]
        if not lines:
            continue
        story += [Paragraph(title, styles["Heading2"])]
        if key == "summary":
            story += [Paragraph(_xml(lines[0]), styles["Normal"])]
        else:
            story += [ListFlowable([ListItem(Paragraph(_xml(l), styles["Normal"]), leftIndent=12)
                                    for l in lines],
                                   bulletType="bullet", leftIndent=12)]
        story += [Spacer(1, 4)]
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
        if key in {"education", "experience", "projects"}:
            cap = 7
            required = [] if key == "education" else data.get("required", [])
            entries = _entry_lines(blocks.get(key, []), required, cap)
            if not entries:
                continue
            doc.add_heading(title, level=1)
            for entry in entries:
                p = doc.add_paragraph()
                p.add_run(entry.get("title", "")).bold = True
                if entry.get("link"):
                    p.add_run(f"  {entry['link']}").italic = True
                details = [d for d in (entry.get("details") or []) if (d or "").strip()]
                if details:
                    doc.add_paragraph(" | ".join(details))
                for bullet in entry.get("bullets", [])[:5]:
                    doc.add_paragraph(bullet, style="List Bullet")
            continue
        lines = _ordered(data["sections"].get(key, []), data.get("required", []))
        if not lines:
            continue
        doc.add_heading(title, level=1)
        if key == "summary":
            doc.add_paragraph(data.get("summary", ""))
        else:
            for line in lines:
                doc.add_paragraph(line, style="List Bullet")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
