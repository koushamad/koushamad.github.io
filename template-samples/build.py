#!/usr/bin/env python3
"""Render CV template samples from _config.yml and print each to PDF.

The YAML stays the single source of truth; every template is just a
different renderer over the same data. Chrome headless does the PDF pass so
the output carries a real text layer (what ATS parsers actually read).

Usage: python3 template-samples/build.py            (from the CV repo root)
"""

import html
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "template-samples"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

def esc(s):
    return html.escape(s or "", quote=False)


def parse_description(desc):
    """Split a sproogen description blob into bullets + optional tech line."""
    bullets, tech = [], None
    for raw in (desc or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"\*\*Tech stack:\*\*\s*(.+)", line)
        if m:
            tech = m.group(1).strip()
            continue
        bullets.append(line.lstrip("•").strip())
    return bullets, tech


def parse_caption(caption):
    """'Amsterdam, Netherlands · Jul 2023 — Present' -> (location, dates)."""
    if not caption:
        return "", ""
    parts = [p.strip() for p in caption.split("·")]
    if len(parts) == 2:
        return parts[0], parts[1]
    return "", caption.strip()


def load():
    cfg = yaml.safe_load((ROOT / "_config.yml").read_text())
    sections = {s["title"]: s for s in cfg["content"]}

    def entries(title):
        return sections.get(title, {}).get("content", []) or []

    jobs = []
    for e in entries("Professional Experience"):
        bullets, tech = parse_description(e.get("description"))
        loc, dates = parse_caption(e.get("caption"))
        jobs.append({
            "company": e["title"], "role": e.get("sub_title", ""),
            "loc": loc, "dates": dates, "quote": (e.get("quote") or "").strip(),
            "bullets": bullets, "tech": tech,
            "url": e.get("link_text") or "",
        })

    projects = []
    for e in entries("Selected Projects"):
        bullets, tech = parse_description(e.get("description"))
        projects.append({
            "name": e["title"], "stack": e.get("sub_title", ""),
            "tag": (e.get("caption") or "").strip(),
            "quote": (e.get("quote") or "").strip(),
            "bullets": bullets, "tech": tech,
        })

    skills = []
    for e in entries("Technologies"):
        skills.append({"group": e["title"],
                       "items": " ".join((e.get("description") or "").split()).rstrip(".")})

    expertise = []
    for e in entries("Core Expertise"):
        bullets, _ = parse_description(e.get("description"))
        expertise.append({"area": e["title"], "sub": e.get("sub_title", ""),
                          "bullets": bullets})

    education = []
    for e in entries("Education / Certifications"):
        education.append({"school": e["title"], "degree": e.get("sub_title", ""),
                          "years": (e.get("caption") or "").strip(),
                          "note": " ".join((e.get("description") or "").split())})

    recs = []
    for e in entries("LinkedIn Recommendations"):
        recs.append({"who": e["title"], "role": e.get("sub_title", ""),
                     "quote": " ".join((e.get("quote") or "").split())})

    summary = [p.strip() for p in cfg["about_content"].split("\n\n") if p.strip()]

    return {
        "name": cfg["name"], "title": cfg["title"],
        "email": cfg["email"], "phone": cfg["phone"],
        "website": cfg["website"], "location": "Amsterdam, Netherlands",
        "linkedin": f"linkedin.com/in/{cfg['linkedin_username']}",
        "github": f"github.com/{cfg['github_username']}",
        "summary": summary, "expertise": expertise, "jobs": jobs,
        "projects": projects, "skills": skills, "education": education,
        "recs": recs,
    }


# --------------------------------------------------------------------------
# Shared HTML plumbing
# --------------------------------------------------------------------------

def page(title, css, body):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{esc(title)}</title>
<style>
@page {{ size: A4; margin: 0; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
h2 {{ break-after: avoid-page; }}
{css}
</style></head><body>{body}</body></html>"""


def bullets_html(items, cls=""):
    lis = "".join(f"<li>{esc(b)}</li>" for b in items)
    return f'<ul class="{cls}">{lis}</ul>'


# --------------------------------------------------------------------------
# Template A — ATS Classic (maximum parseability, zero decoration)
# --------------------------------------------------------------------------

def template_a(d):
    css = """
body { font: 10.3pt/1.45 Georgia, 'Times New Roman', serif; color: #111;
       padding: 16mm 17mm; }
header { text-align: center; margin-bottom: 5mm; }
h1 { font-size: 19pt; letter-spacing: .5px; }
.role { font-size: 11.5pt; margin-top: 1mm; }
.contact { font-size: 9.3pt; margin-top: 1.5mm; }
h2 { font-size: 11pt; text-transform: uppercase; letter-spacing: .7px;
     border-bottom: 1pt solid #111; padding-bottom: 1mm; margin: 5.5mm 0 2.5mm; }
.job { margin-bottom: 3.6mm; break-inside: avoid-page; }
.jobline { display: flex; justify-content: space-between; align-items: baseline; }
.jobline b { font-size: 10.8pt; }
.dates { font-size: 9.3pt; white-space: nowrap; }
.subline { font-style: italic; font-size: 9.8pt; margin-bottom: 1mm; }
ul { margin: .8mm 0 0 4.5mm; }
li { margin-bottom: .7mm; }
.tech { font-size: 8.9pt; margin-top: .9mm; color: #222; }
.skillrow { margin-bottom: 1.1mm; }
p.sum { margin-bottom: 1.8mm; text-align: justify; }
.edu { margin-bottom: 1.6mm; }
/* Chrome print ignores break-after:avoid on headings, so each section binds
   its h2 to the first block instead — a heading can never strand alone. */
.keep { break-inside: avoid-page; }
"""

    def sec(title, blocks):
        if not blocks:
            return f"<h2>{title}</h2>"
        return (f'<div class="keep"><h2>{title}</h2>{blocks[0]}</div>'
                + "".join(blocks[1:]))
    b = [f"""<header>
<h1>{esc(d['name'])}</h1>
<div class="role">{esc(d['title'])}</div>
<div class="contact">{esc(d['location'])} &nbsp;|&nbsp; {esc(d['phone'])} &nbsp;|&nbsp; {esc(d['email'])}</div>
<div class="contact">{esc(d['website'])} &nbsp;|&nbsp; {esc(d['linkedin'])} &nbsp;|&nbsp; {esc(d['github'])}</div>
</header>"""]

    b.append(sec("Professional Summary",
                 [f'<p class="sum">{esc(p)}</p>' for p in d["summary"]]))

    b.append(sec("Core Competencies",
                 [f'<div class="skillrow"><b>{esc(e["area"])}:</b> {esc(e["sub"])}. '
                  f'{esc(" ".join(e["bullets"]))}</div>' for e in d["expertise"]]))

    b.append(sec("Professional Experience", [f"""<div class="job">
<div class="jobline"><b>{esc(j['role'])}</b><span class="dates">{esc(j['dates'])}</span></div>
<div class="subline">{esc(j['company'])} — {esc(j['loc'])}</div>
{bullets_html(j['bullets'])}
{f'<div class="tech"><b>Technologies:</b> {esc(j["tech"])}</div>' if j['tech'] else ''}
</div>""" for j in d["jobs"]]))

    b.append(sec("Selected Projects", [f"""<div class="job">
<div class="jobline"><b>{esc(p['name'])}</b><span class="dates">{esc(p['tag'])}</span></div>
<div class="subline">{esc(p['stack'])}</div>
{bullets_html(p['bullets'][:2])}
</div>""" for p in d["projects"]]))

    b.append(sec("Technical Skills",
                 [f'<div class="skillrow"><b>{esc(s["group"])}:</b> {esc(s["items"])}</div>'
                  for s in d["skills"]]))

    b.append(sec("Education",
                 [f'<div class="edu"><div class="jobline"><b>{esc(e["degree"])}</b>'
                  f'<span class="dates">{esc(e["years"])}</span></div>'
                  f'<div class="subline">{esc(e["school"])}</div></div>'
                  for e in d["education"]]))

    return page(f"{d['name']} — CV", css, "".join(b))


# --------------------------------------------------------------------------
# Template B — Modern Professional (single column, one accent, ATS-safe)
# --------------------------------------------------------------------------

def template_b(d):
    accent = "#14532d"
    css = f"""
body {{ font: 9.9pt/1.5 'Helvetica Neue', Helvetica, Arial, sans-serif;
       color: #1c1c1c; padding: 14mm 16mm; }}
header {{ border-bottom: 2.5pt solid {accent}; padding-bottom: 3.5mm; margin-bottom: 4.5mm; }}
h1 {{ font-size: 22pt; font-weight: 700; color: {accent}; letter-spacing: -.3px; }}
.role {{ font-size: 11.5pt; font-weight: 500; margin-top: .8mm; }}
.contact {{ font-size: 8.8pt; color: #444; margin-top: 2mm; }}
.contact span + span::before {{ content: "  ·  "; color: #999; }}
h2 {{ font-size: 10.2pt; font-weight: 700; text-transform: uppercase;
     letter-spacing: .7px; color: {accent}; margin: 5mm 0 2.2mm; }}
h2::after {{ content: ""; display: block; height: .6pt; background: #d9d9d9; margin-top: 1mm; }}
.job {{ margin-bottom: 3.4mm; break-inside: avoid-page; }}
.jobline {{ display: flex; justify-content: space-between; align-items: baseline; }}
.jobline .co {{ font-size: 10.6pt; font-weight: 700; }}
.jobline .co small {{ font-weight: 400; color: #555; font-size: 9.3pt; }}
.dates {{ font-size: 8.8pt; color: #555; white-space: nowrap; }}
.rolename {{ font-size: 9.8pt; font-weight: 600; color: #333; margin-bottom: .8mm; }}
ul {{ margin: 0 0 0 4mm; }}
li {{ margin-bottom: .6mm; }}
li::marker {{ color: {accent}; }}
.tech {{ font-size: 8.5pt; color: #555; margin-top: .8mm; }}
p.sum {{ margin-bottom: 1.8mm; }}
.skillrow {{ margin-bottom: 1mm; }}
.skillrow b {{ color: {accent}; }}
.edu {{ margin-bottom: 1.4mm; }}
"""
    b = [f"""<header>
<h1>{esc(d['name'])}</h1>
<div class="role">{esc(d['title'])}</div>
<div class="contact"><span>{esc(d['location'])}</span><span>{esc(d['phone'])}</span><span>{esc(d['email'])}</span><span>{esc(d['website'])}</span><span>{esc(d['linkedin'])}</span><span>{esc(d['github'])}</span></div>
</header>"""]

    b.append("<h2>Summary</h2>")
    for p in d["summary"]:
        b.append(f'<p class="sum">{esc(p)}</p>')

    b.append("<h2>Experience</h2>")
    for j in d["jobs"]:
        b.append(f"""<div class="job">
<div class="jobline"><span class="co">{esc(j['company'])} <small>— {esc(j['loc'])}</small></span><span class="dates">{esc(j['dates'])}</span></div>
<div class="rolename">{esc(j['role'])}</div>
{bullets_html(j['bullets'])}
{f'<div class="tech">{esc(j["tech"])}</div>' if j['tech'] else ''}
</div>""")

    b.append("<h2>Selected Projects</h2>")
    for p in d["projects"]:
        b.append(f"""<div class="job">
<div class="jobline"><span class="co">{esc(p['name'])} <small>— {esc(p['tag'])}</small></span></div>
<div class="rolename">{esc(p['stack'])}</div>
{bullets_html(p['bullets'][:2])}
</div>""")

    b.append("<h2>Technical Skills</h2>")
    for s in d["skills"]:
        b.append(f'<div class="skillrow"><b>{esc(s["group"])}</b> — {esc(s["items"])}</div>')

    b.append("<h2>Education</h2>")
    for e in d["education"]:
        b.append(f'<div class="edu"><div class="jobline"><span class="co">{esc(e["degree"])} '
                 f'<small>— {esc(e["school"])}</small></span>'
                 f'<span class="dates">{esc(e["years"])}</span></div></div>')

    return page(f"{d['name']} — CV", css, "".join(b))


# --------------------------------------------------------------------------
# Template C — Executive Compact (two-page target, condensed)
# --------------------------------------------------------------------------

def template_c(d):
    ink, accent = "#232323", "#8a6d3b"
    css = f"""
body {{ font: 9.4pt/1.42 'Helvetica Neue', Helvetica, Arial, sans-serif;
       color: {ink}; padding: 13mm 15mm; }}
header {{ display: flex; justify-content: space-between; align-items: flex-end;
         border-bottom: 1pt solid {ink}; padding-bottom: 2.5mm; margin-bottom: 3.5mm; }}
h1 {{ font-size: 17pt; font-weight: 700; letter-spacing: .2px; }}
.role {{ font-size: 10pt; color: {accent}; font-weight: 600;
        text-transform: uppercase; letter-spacing: 1px; margin-top: .6mm; }}
.contact {{ font-size: 8.2pt; text-align: right; color: #4a4a4a; line-height: 1.5; }}
h2 {{ font-size: 9.3pt; font-weight: 700; text-transform: uppercase;
     letter-spacing: .7px; color: {accent}; margin: 4mm 0 1.8mm; }}
.job {{ margin-bottom: 2.6mm; break-inside: avoid-page; }}
.jobline {{ display: flex; justify-content: space-between; align-items: baseline; }}
.jobline b {{ font-size: 9.9pt; }}
.jobline b small {{ font-weight: 400; color: #555; }}
.dates {{ font-size: 8.2pt; color: #555; white-space: nowrap; }}
.lede {{ font-size: 8.9pt; font-style: italic; color: #4a4a4a; margin: .4mm 0 .7mm; }}
ul {{ margin: 0 0 0 3.6mm; }}
li {{ margin-bottom: .45mm; }}
p.sum {{ margin-bottom: 1.5mm; }}
.skillrow {{ margin-bottom: .8mm; font-size: 8.9pt; }}
.projrow {{ margin-bottom: 1.5mm; font-size: 9.1pt; }}
.edu {{ display: flex; justify-content: space-between; margin-bottom: .8mm; font-size: 9.1pt; }}
"""
    b = [f"""<header>
<div><h1>{esc(d['name'])}</h1><div class="role">{esc(d['title'])}</div></div>
<div class="contact">{esc(d['location'])} · {esc(d['phone'])}<br>
{esc(d['email'])} · {esc(d['website'])}<br>{esc(d['linkedin'])} · {esc(d['github'])}</div>
</header>"""]

    b.append("<h2>Profile</h2>")
    b.append(f'<p class="sum">{esc(d["summary"][0])}</p>')

    b.append("<h2>Experience</h2>")
    for j in d["jobs"]:
        b.append(f"""<div class="job">
<div class="jobline"><b>{esc(j['role'])} <small>· {esc(j['company'])}, {esc(j['loc'])}</small></b><span class="dates">{esc(j['dates'])}</span></div>
{f'<div class="lede">{esc(j["quote"])}</div>' if j['quote'] else ''}
{bullets_html(j['bullets'][:3])}
</div>""")

    b.append("<h2>Selected Projects</h2>")
    for p in d["projects"]:
        first = p["bullets"][0] if p["bullets"] else p["quote"]
        b.append(f'<div class="projrow"><b>{esc(p["name"])}</b> — {esc(first)}</div>')

    b.append("<h2>Technical Skills</h2>")
    for s in d["skills"]:
        b.append(f'<div class="skillrow"><b>{esc(s["group"])}:</b> {esc(s["items"])}</div>')

    b.append("<h2>Education</h2>")
    for e in d["education"]:
        b.append(f'<div class="edu"><span><b>{esc(e["degree"])}</b> — {esc(e["school"])}</span>'
                 f'<span class="dates">{esc(e["years"])}</span></div>')

    return page(f"{d['name']} — CV", css, "".join(b))


# --------------------------------------------------------------------------
# Template D — Two-Column Visual (human-reader oriented)
# --------------------------------------------------------------------------

def template_d(d):
    navy, paper = "#16324f", "#f4f6f8"
    css = f"""
body {{ font: 9.6pt/1.48 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #202020; }}
.railbg {{ position: fixed; left: 0; top: 0; bottom: 0; width: 62mm;
          background: {paper}; border-right: .6pt solid #dfe3e8; }}
.grid {{ display: grid; grid-template-columns: 62mm 1fr; position: relative; }}
.rail {{ padding: 13mm 7mm 10mm 9mm; }}
.main {{ padding: 13mm 12mm 10mm 9mm; }}
h1 {{ font-size: 17.5pt; color: {navy}; line-height: 1.12; }}
.role {{ font-size: 9.6pt; font-weight: 600; margin: 1.2mm 0 4mm; color: #37506b; }}
.rail h2 {{ font-size: 8.6pt; text-transform: uppercase; letter-spacing: .7px;
           color: {navy}; margin: 4mm 0 1.6mm; border-bottom: 1pt solid #cfd6dd; padding-bottom: .8mm; }}
.rail .item {{ font-size: 8.6pt; margin-bottom: 1mm; word-wrap: break-word; }}
.rail .skillrow {{ font-size: 8.4pt; margin-bottom: 1.4mm; }}
.rail .skillrow b {{ display: block; color: {navy}; }}
.rail .edu {{ font-size: 8.4pt; margin-bottom: 1.6mm; }}
.rail .quote {{ font-size: 8.1pt; font-style: italic; color: #45505c; margin-bottom: 2mm; }}
.rail .quote b {{ display: block; font-style: normal; color: {navy}; }}
.main h2 {{ font-size: 10pt; text-transform: uppercase; letter-spacing: .7px;
           color: {navy}; margin: 4.5mm 0 2mm; }}
.main h2:first-child {{ margin-top: 0; }}
.job {{ margin-bottom: 3.2mm; break-inside: avoid-page; }}
.jobline {{ display: flex; justify-content: space-between; align-items: baseline; }}
.jobline b {{ font-size: 10.2pt; color: {navy}; }}
.dates {{ font-size: 8.4pt; color: #5a6672; white-space: nowrap; }}
.rolename {{ font-size: 9.4pt; font-weight: 600; margin-bottom: .8mm; }}
ul {{ margin: 0 0 0 3.8mm; }}
li {{ margin-bottom: .55mm; }}
li::marker {{ color: {navy}; }}
p.sum {{ margin-bottom: 1.6mm; font-size: 9.4pt; }}
"""
    rail = [f"<h1>{esc(d['name'])}</h1>", f'<div class="role">{esc(d["title"])}</div>']
    rail.append("<h2>Contact</h2>")
    for item in (d["location"], d["phone"], d["email"], d["website"], d["linkedin"], d["github"]):
        rail.append(f'<div class="item">{esc(item)}</div>')
    rail.append("<h2>Technical Skills</h2>")
    for s in d["skills"]:
        rail.append(f'<div class="skillrow"><b>{esc(s["group"])}</b>{esc(s["items"])}</div>')
    rail.append("<h2>Education</h2>")
    for e in d["education"]:
        rail.append(f'<div class="edu"><b>{esc(e["degree"])}</b><br>{esc(e["school"])} · {esc(e["years"])}</div>')
    rail.append("<h2>Endorsements</h2>")
    for r in d["recs"][:2]:
        short = r["quote"]
        if len(short) > 170:
            short = short[:167].rsplit(" ", 1)[0] + "…"
        rail.append(f'<div class="quote"><b>{esc(r["who"])} · {esc(r["role"])}</b>“{esc(short)}”</div>')

    main = ["<h2>Summary</h2>"]
    for p in d["summary"]:
        main.append(f'<p class="sum">{esc(p)}</p>')
    main.append("<h2>Experience</h2>")
    for j in d["jobs"]:
        main.append(f"""<div class="job">
<div class="jobline"><b>{esc(j['company'])}</b><span class="dates">{esc(j['dates'])}</span></div>
<div class="rolename">{esc(j['role'])} · {esc(j['loc'])}</div>
{bullets_html(j['bullets'][:3])}
</div>""")
    main.append("<h2>Selected Projects</h2>")
    for p in d["projects"]:
        main.append(f"""<div class="job">
<div class="jobline"><b>{esc(p['name'])}</b><span class="dates">{esc(p['tag'])}</span></div>
{bullets_html(p['bullets'][:1])}
</div>""")

    body = f'<div class="railbg"></div><div class="grid"><aside class="rail">{"".join(rail)}</aside><div class="main">{"".join(main)}</div></div>'
    return page(f"{d['name']} — CV", css, body)


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

TEMPLATES = {
    "cv-a-ats-classic": template_a,
    "cv-b-modern-professional": template_b,
    "cv-c-executive-compact": template_c,
    "cv-d-two-column-visual": template_d,
}


def main():
    d = load()
    OUT.mkdir(exist_ok=True)
    for name, fn in TEMPLATES.items():
        html_path = OUT / f"{name}.html"
        pdf_path = OUT / f"{name}.pdf"
        html_path.write_text(fn(d))
        r = subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={pdf_path}", str(html_path)],
            capture_output=True, text=True, timeout=120)
        ok = pdf_path.exists() and pdf_path.stat().st_size > 10_000
        print(f"{name}: {'OK' if ok else 'FAILED'} ({pdf_path.stat().st_size if pdf_path.exists() else 0} bytes)")
        if not ok:
            print(r.stderr[-500:])
            sys.exit(1)


if __name__ == "__main__":
    main()
