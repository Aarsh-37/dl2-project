"""LaTeX resume: user-approved Jake-style template -> .tex -> PDF.

Section order (frozen by user): name, details, summary, education,
experience, projects, skills, certifications, co-curricular activities.
Only profile facts are rendered — High gaps stay in "Areas to Upskill",
never as fake bullets. compile_latex() uses a local toolchain
(pdflatex/xelatex/tectonic); None when absent so the endpoint can fall
back to the reportlab renderer with the same section order.

Readability: education entries are institution + detail line (not one
bullet per fragment), experience/projects keep title + bullets, and the
resume's labelled Skills groups render one group per line.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

_LATEX_SPECIALS = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%",
                   "$": r"\$", "#": r"\#", "_": r"\_",
                   "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
                   "^": r"\textasciicircum{}"}

_UNICODE_FIX = {"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "--",
                "\u2014": "---", "\u2018": "'", "\u2019": "'",
                "\u201c": '"', "\u201d": '"', "\u2026": "...",
                "\u00a0": " ", "\u2022": "-", "\u2192": "->", "\u2713": "v"}


def _ascii(text: str) -> str:
    """pdflatex (OT1) handles ASCII only — normalize LLM/resume unicode first."""
    for src, dst in _UNICODE_FIX.items():
        text = (text or "").replace(src, dst)
    text = text.replace("\ufffd", "-")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def escape(text: str) -> str:
    return "".join(_LATEX_SPECIALS.get(ch, ch) for ch in _ascii(text or ""))


def escape_url(url: str) -> str:
    url = (url or "").strip()
    if not re.match(r"(https?://|mailto:)", url, re.I):
        url = "https://" + url
    return url.replace("%", r"\%").replace("#", r"\#")


def _link(url: str, label: str) -> str:
    if not url:
        return escape(label)
    return r"\href{%s}{%s}" % (escape_url(url), escape(label or url))


def _contact_line(contact: dict) -> str:
    email, phone = contact.get("email", ""), contact.get("phone", "")
    gh, li = contact.get("github", ""), contact.get("linkedin", "")
    bits = []
    if email:
        bits.append(_link(f"mailto:{email}", email))
    if phone:
        bits.append(escape(phone))
    if li:
        bits.append(_link(f"https://{li}", "LinkedIn"))
    elif contact.get("linkedin_label"):
        bits.append(escape(contact["linkedin_label"]))
    if gh:
        bits.append(_link(f"https://{gh}", "GitHub"))
    elif contact.get("github_label"):
        bits.append(escape(contact["github_label"]))
    return (" $|$ ".join(bits) or escape("Contact details in original resume"))


def _bullets(lines: list[str]) -> str:
    items = "\n".join(f"\\resumeItemWithoutTitle{{{escape(l)}}}" for l in lines if l.strip())
    if not items:
        return ""
    return ("\\resumeBulletListStart\n" + items +
            "\n\\resumeBulletListEnd\n\\vspace{-5pt}\n")


# CGPA/GPA labels, bare percentages, and "8.7/10" style scores.
_SCORE = re.compile(
    r"^\s*(?:(?:cgpa|gpa|percentage|score)\b.*|(?:\d+(?:\.\d+)?\s*%)|"
    r"(?:\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?))\s*$", re.I)


_PREAMBLE = r"""\documentclass[a4paper,10pt]{article}
\usepackage[hidelinks]{hyperref}
\pdfstringdefDisableCommands{\def\color#1{}}
\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\addtolength{\oddsidemargin}{-0.530in}
\addtolength{\evensidemargin}{-0.375in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.45in}
\addtolength{\textheight}{1in}
\urlstyle{rm}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}
\titleformat{\section}{
  \vspace{-9pt}\scshape\raggedright\large\bfseries
}{}{0em}{}[\vspace{2pt}\titlerule \vspace{-4pt}]
\newcommand{\resumeItem}[2]{
  \item\small{
    \textbf{#1}{: #2 \vspace{-2pt}}
  }
}
\newcommand{\resumeItemWithoutTitle}[1]{
  \item\small{
    #1 \vspace{-2pt}
  }
}
\newcommand{\resumeDetailLine}[1]{
  \item[]\small{\textit{#1} \vspace{-2pt}}
}
\newcommand{\resumeSubheading}[4]{
  \vspace{-1pt}\item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{#3} & \textit{#4} \\
    \end{tabular*}\vspace{-5pt}
}
\newcommand{\resumeSubItem}[2]{\resumeItem{#1}{#2}\vspace{-3pt}}
\newcommand{\resumeProjectHeading}[2]{
  \vspace{-1pt}\item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
    \end{tabular*}\vspace{-6pt}
}
\renewcommand{\labelitemi}{}
\renewcommand{\labelitemii}{--}
\renewcommand{\labelitemiii}{$\circ$}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=*]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}
\newcommand{\resumeBulletListStart}{\begin{itemize}[leftmargin=*, label=--]}
\newcommand{\resumeBulletListEnd}{\end{itemize}\vspace{-5pt}}
\newcommand{\resumeSkillListStart}{\begin{itemize}[leftmargin=*, topsep=0pt, itemsep=0pt, parsep=0pt]}
\newcommand{\resumeSkillListEnd}{\end{itemize}}
\begin{document}
"""


def _mentions_required(line: str, required: list[str]) -> bool:
    lowered = (line or "").lower()
    return any(r.lower() in lowered for r in (required or []))


def prioritize_lines(lines: list[str], required: list[str]) -> list[str]:
    """Stable JD-first ordering: bullets evidencing required skills float up.

    Same facts in original relative order — nothing added, nothing dropped here.
    """
    if not required:
        return list(lines)
    return sorted(lines, key=lambda l: not _mentions_required(l, required))


def _prioritize_entries(entries: list[dict], required: list[str]) -> list[dict]:
    if not required:
        return list(entries)

    def text(entry: dict) -> str:
        return " ".join([entry.get("title", ""), entry.get("link", ""),
                         entry.get("date", "")] + entry.get("details", [])
                        + entry.get("bullets", []))

    return sorted(entries, key=lambda e: not _mentions_required(text(e), required))


def _entry_tex(entries: list[dict], required: list[str], cap: int) -> str:
    """Entry heading with a right-aligned date, then its bullets.

    Title/date share one row (like the reference templates); bullets are a
    nested list so PDF wrap artefacts never leak into the layout.
    """
    out = ["\\resumeSubHeadingListStart\n"]
    for entry in _prioritize_entries(entries, required)[:cap]:
        title = escape(entry.get("title", ""))
        link = entry.get("link", "")
        if link:
            title += " $|$ \\emph{%s}" % escape(link)
        date = escape(entry.get("date", ""))
        details = " | ".join(escape(d) for d in entry.get("details", [])
                             if (d or "").strip())
        bullets = [b for b in entry.get("bullets", []) if (b or "").strip()][:5]
        if bullets:
            out.append("\\resumeProjectHeading{%s}{%s}\n" % (title, date))
            out.append("\\resumeItemListStart\n")
            if details:
                out.append("\\resumeDetailLine{%s}\n" % details)
            out.extend("\\resumeItemWithoutTitle{%s}\n" % escape(b) for b in bullets)
            out.append("\\resumeItemListEnd\n")
        elif details:
            out.append("\\resumeSubheading{%s}{%s}{%s}{}\n" % (title, date, details))
        elif date:
            out.append("\\resumeItemWithoutTitle{\\textbf{%s} \\hfill %s}\n"
                       % (title, date))
        else:
            out.append("\\resumeItemWithoutTitle{\\textbf{%s}}\n" % title)
    out.append("\\resumeSubHeadingListEnd\n\\vspace{-2pt}\n")
    return "".join(out)


def _education_tex(entries: list[dict], cap: int = 6) -> str:
    out = ["\\resumeSubHeadingListStart\n"]
    for entry in entries[:cap]:
        title = escape(entry.get("title", ""))
        date = escape(entry.get("date", ""))
        details = [escape(d) for d in entry.get("details", []) if (d or "").strip()]
        right = ""
        if details and _SCORE.match(_ascii(details[-1])):
            right = details.pop()
        if details:
            out.append("\\resumeSubheading{%s}{%s}{%s}{%s}\n"
                       % (title, date, " | ".join(details), right))
        elif right:
            out.append("\\resumeSubheading{%s}{%s}{}{%s}\n"
                       % (title, date, right))
        else:
            out.append("\\resumeProjectHeading{%s}{%s}\n" % (title, date))
    out.append("\\resumeSubHeadingListEnd\n\\vspace{-2pt}\n")
    return "".join(out)


def _skills_tex(groups: list[dict], matched: set[str]) -> str:
    out = ["\\resumeSkillListStart\n"]
    for group in groups:
        label = ("\\textbf{%s:} " % escape(group["label"])) if group.get("label") else ""
        items = []
        for item in group.get("items", []):
            esc = escape(item)
            if (item or "").strip().lower() in matched:
                esc = "\\textbf{%s}" % esc
            items.append(esc)
        out.append("\\item\\small{%s%s}\n" % (label, ", ".join(items)))
    out.append("\\resumeSkillListEnd\n\\vspace{-2pt}\n")
    return "".join(out)


def build_latex(data: dict, max_bullets: int = 6) -> str:
    """Render the full .tex source in the user's section order.

    Resume facts ONLY (verbatim original lines + LLM summary built from the
    resume). No upskill section, no outside content — gaps live in the
    roadmap, never on the resume. max_bullets caps each entry block so the
    document stays on one page.
    """
    contact, summary = data.get("contact", {}), (data.get("summary") or "").strip()
    sections: dict = data.get("sections", {}) or {}
    blocks: dict = data.get("blocks", {}) or {}
    groups: list[dict] = data.get("skill_groups", []) or []
    skills = data.get("skills", []) or []
    matched = {s.lower() for s in (data.get("skills_matched", []) or [])}
    required = data.get("required", []) or []

    parts = [_PREAMBLE]
    name = escape(data.get("name", "Candidate"))
    title = escape((data.get("title") or "").strip())
    header_tex = "\\begin{center}\n" \
                 "{\\LARGE \\textsc{" + name + "}}\\\\\n"
    if title:
        header_tex += "{\\large \\textsc{" + title + "}}\\\\\n"
    header_tex += _contact_line(contact) + "\n\\end{center}\n\\vspace{-8pt}\n"
    parts.append(header_tex)
    if summary:
        parts.append("\\section{Professional Summary}\n" + escape(summary)
                     + "\n\\vspace{-2pt}\n")

    def _items(key: str) -> tuple[list, bool]:
        value = sections.get(key)
        if isinstance(value, list) and (value or key in sections):
            return value, bool(value and isinstance(value[0], dict))
        value = blocks.get(key) or []
        return list(value), bool(value and isinstance(value[0], dict))

    if blocks or sections:
        edu, edu_struct = _items("education")
        if edu:
            if edu_struct:
                parts.append("\\section{Education}\n" + _education_tex(edu) + "\n")
            else:
                parts.append("\\section{Education}\n"
                             + _bullets(prioritize_lines(edu, required)[:max_bullets])
                             + "\\vspace{-2pt}\n")
        for key, title in (("experience", "Experience"), ("projects", "Projects")):
            entries, structured = _items(key)
            if not entries:
                continue
            if structured:
                parts.append(f"\\section{{{title}}}\n"
                             + _entry_tex(entries, required, max_bullets) + "\n")
            else:
                parts.append(f"\\section{{{title}}}\n"
                             + _bullets(prioritize_lines(entries, required)[:max_bullets])
                             + "\\vspace{-2pt}\n")
    else:
        for key, title in (("education", "Education"),
                           ("experience", "Experience"), ("projects", "Projects")):
            lines = prioritize_lines(sections.get(key, []) or [], required)[:max_bullets]
            if lines:
                parts.append(f"\\section{{{title}}}\n{_bullets(lines)}\\vspace{{-2pt}}\n")

    if groups:
        parts.append("\\section{Skills Summary}\n" + _skills_tex(groups, matched)
                     + "\\vspace{-2pt}\n")
    elif skills:
        parts.append("\\section{Skills Summary}\n"
                     "\\resumeSubHeadingListStart\n"
                     f"\\resumeSubItem{{\\textbf{{Technical Skills}}}}"
                     f"{{{', '.join(escape(s) for s in skills)}}}\n"
                     "\\resumeSubHeadingListEnd\n\\vspace{-2pt}\n")
    for key, title in (("certifications", "Certifications"),
                       ("activities", "Co-Curricular Activities")):
        entries, structured = _items(key)
        if not entries:
            continue
        if key == "activities":
            lines = ([b for e in entries for b in e.get("bullets", [])]
                     if structured else list(entries))
            lines = [l for l in lines if (l or "").strip()][:max_bullets]
            if lines:
                parts.append(f"\\section{{{title}}}\n{_bullets(lines)}\\vspace{{-2pt}}\n")
            continue
        if structured:
            parts.append(f"\\section{{{title}}}\n"
                         + _entry_tex(entries, required, max_bullets) + "\n")
        else:
            lines = prioritize_lines(entries, required)[:max_bullets]
            parts.append(f"\\section{{{title}}}\n{_bullets(lines)}\\vspace{{-2pt}}\n")
    parts.append("\\end{document}\n")
    return "".join(parts)


def _pdf_pages(pdf_bytes: bytes) -> int | None:
    try:
        import fitz
        return len(fitz.open(stream=pdf_bytes, filetype="pdf"))
    except Exception:
        return None


def build_one_page_pdf(data: dict) -> tuple[bytes | None, str, str]:
    """Compile the resume, enforcing max 1 page: build -> count pages ->
    tighten bullet caps and rebuild (up to 3 attempts).

    Returns (pdf_bytes|None, engine|"", tex_used). None when no toolchain.
    """
    tex_used = ""
    for max_bullets in (7, 5, 4):
        tex_used = build_latex(data, max_bullets=max_bullets)
        pdf, log = compile_latex(tex_used)
        if pdf is None:
            return None, "", tex_used
        pages = _pdf_pages(pdf)
        if pages is None or pages <= 1:
            return pdf, "latex", tex_used
    return pdf, "latex-tight", tex_used


def toolchain() -> str | None:
    for exe in ("pdflatex", "xelatex", "tectonic"):
        path = shutil.which(exe)
        if path:
            return path
    return None


def compile_latex(tex: str, timeout: int = 90) -> tuple[bytes | None, str]:
    """Compile .tex source to PDF bytes. (None, log) when no toolchain/failure."""
    exe = toolchain()
    if not exe:
        return None, "no LaTeX toolchain (pdflatex/xelatex/tectonic) on PATH"
    name = Path(exe).stem.lower()
    with tempfile.TemporaryDirectory(prefix="careerpilot-tex-") as tmp:
        src = Path(tmp) / "resume.tex"
        src.write_text(tex, encoding="utf-8")
        try:
            if name == "tectonic":
                cmd = [exe, "-X", "compile", str(src), "--outdir", tmp]
            else:
                cmd = [exe, "-interaction=nonstopmode", "-halt-on-error", str(src)]
            proc = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, "LaTeX compile timed out"
        pdf = Path(tmp) / "resume.pdf"
        if proc.returncode == 0 and pdf.exists():
            return pdf.read_bytes(), ""
        log = (proc.stdout or "") + (proc.stderr or "")
        return None, log[-1500:]
