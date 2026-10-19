#!/usr/bin/env python3
"""Build the downloadable CV PDF from _config.yml.

_config.yml is the single source of truth — the same data that renders
https://koushamad.github.io/. This script renders it through the approved
two-column layout (navy sidebar) with the COMPLETE content, and prints it via
headless Chrome so the PDF carries a real, ATS-readable text layer.

Layout rules learned the hard way, kept on purpose:
  * heading letter-spacing stays <= ~1px — wider tracking makes the text layer
    extract as "S U M M A R Y", which ATS parsers cannot match to a section;
  * the sidebar background is a fixed underlay so it paints on every page;
  * each h2 is bound to its first block (`.keep`) because Chromium's print
    engine ignores `break-after: avoid` on headings.

Usage:  python3 scripts/build_cv_pdf.py [output.pdf]
Chrome: uses CHROME_BIN if set, else the macOS app path, else `chromium`.
"""

import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "assets" / "Kousha-Ghodsizad-CV.pdf"


def chrome_binary():
    for candidate in (
        os.environ.get("CHROME_BIN"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("chromium-browser"),
        shutil.which("chromium"),
        shutil.which("google-chrome"),
    ):
        if candidate and Path(candidate).exists():
            return candidate
    sys.exit("no Chrome/Chromium binary found (set CHROME_BIN)")


def esc(s):
    return html.escape(s or "", quote=False)


def parse_description(desc):
    """Split a description blob into bullets + optional '**Tech stack:**' line."""
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
        jobs.append({"company": e["title"], "role": e.get("sub_title", ""),
                     "loc": loc, "dates": dates,
                     "quote": (e.get("quote") or "").strip(),
                     "bullets": bullets, "tech": tech})

    projects = []
    for e in entries("Selected Projects"):
        bullets, tech = parse_description(e.get("description"))
        projects.append({"name": e["title"], "stack": e.get("sub_title", ""),
                         "tag": (e.get("caption") or "").strip(),
                         "bullets": bullets, "tech": tech})

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
                          "years": (e.get("caption") or "").strip()})

    recs = []
    for e in entries("LinkedIn Recommendations"):
        recs.append({"who": e["title"], "role": e.get("sub_title", ""),
                     "quote": " ".join((e.get("quote") or "").split())})

    return {
        "name": cfg["name"], "title": cfg["title"],
        "email": cfg["email"], "phone": cfg["phone"],
        "website": cfg["website"], "location": "Amsterdam, Netherlands",
        "linkedin": f"linkedin.com/in/{cfg['linkedin_username']}",
        "github": f"github.com/{cfg['github_username']}",
        "summary": [p.strip() for p in cfg["about_content"].split("\n\n") if p.strip()],
        "expertise": expertise, "jobs": jobs, "projects": projects,
        "skills": skills, "education": education, "recs": recs,
    }


def bullets_html(items):
    return "<ul>" + "".join(f"<li>{esc(b)}</li>" for b in items) + "</ul>"


def render(d):
    navy, paper = "#16324f", "#f4f6f8"
    css = f"""
@page {{ size: A4; margin: 0; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
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
.rail .note {{ font-size: 8.1pt; font-style: italic; color: #45505c; margin-top: 2mm; }}
.main h2 {{ font-size: 10pt; text-transform: uppercase; letter-spacing: .7px;
           color: {navy}; margin: 4.5mm 0 2mm; }}
.main .keep > h2:first-child {{ margin-top: 4.5mm; }}
.main > .keep:first-child > h2 {{ margin-top: 0; }}
.keep {{ break-inside: avoid-page; }}
.job {{ margin-bottom: 3.2mm; break-inside: avoid-page; }}
.jobline {{ display: flex; justify-content: space-between; align-items: baseline; }}
.jobline b {{ font-size: 10.2pt; color: {navy}; }}
.dates {{ font-size: 8.4pt; color: #5a6672; white-space: nowrap; }}
.rolename {{ font-size: 9.4pt; font-weight: 600; margin-bottom: .8mm; }}
ul {{ margin: 0 0 0 3.8mm; }}
li {{ margin-bottom: .55mm; }}
li::marker {{ color: {navy}; }}
.tech {{ font-size: 8.3pt; color: #55606c; margin-top: .8mm; }}
p.sum {{ margin-bottom: 1.6mm; font-size: 9.4pt; }}
.exprow {{ margin-bottom: 1.6mm; }}
.exprow b {{ color: {navy}; }}
.rec {{ margin-bottom: 2.4mm; break-inside: avoid-page; }}
.rec .who {{ font-weight: 700; color: {navy}; font-size: 9.2pt; }}
.rec .quote {{ font-size: 8.9pt; font-style: italic; color: #38424d; }}
"""

    def sec(title, blocks):
        if not blocks:
            return f"<h2>{esc(title)}</h2>"
        return (f'<div class="keep"><h2>{esc(title)}</h2>{blocks[0]}</div>'
                + "".join(blocks[1:]))

    rail = [f"<h1>{esc(d['name'])}</h1>", f'<div class="role">{esc(d["title"])}</div>']
    rail.append("<h2>Contact</h2>")
    for item in (d["location"], d["phone"], d["email"], d["website"],
                 d["linkedin"], d["github"]):
        rail.append(f'<div class="item">{esc(item)}</div>')
    rail.append("<h2>Technical Skills</h2>")
    for s in d["skills"]:
        rail.append(f'<div class="skillrow"><b>{esc(s["group"])}</b>{esc(s["items"])}</div>')
    rail.append("<h2>Education</h2>")
    for e in d["education"]:
        rail.append(f'<div class="edu"><b>{esc(e["degree"])}</b><br>'
                    f'{esc(e["school"])} · {esc(e["years"])}</div>')
    rail.append('<div class="note">References available on request.</div>')

    main = [sec("Summary", [f'<p class="sum">{esc(p)}</p>' for p in d["summary"]])]

    main.append(sec("Core Expertise",
                    [f'<div class="exprow"><b>{esc(e["area"])}:</b> {esc(e["sub"])}. '
                     f'{esc(" ".join(e["bullets"]))}</div>' for e in d["expertise"]]))

    main.append(sec("Experience", [f"""<div class="job">
<div class="jobline"><b>{esc(j['company'])}</b><span class="dates">{esc(j['dates'])}</span></div>
<div class="rolename">{esc(j['role'])} · {esc(j['loc'])}</div>
{bullets_html(j['bullets'])}
{f'<div class="tech">{esc(j["tech"])}</div>' if j['tech'] else ''}
</div>""" for j in d["jobs"]]))

    main.append(sec("Selected Projects", [f"""<div class="job">
<div class="jobline"><b>{esc(p['name'])}</b><span class="dates">{esc(p['tag'])}</span></div>
<div class="rolename">{esc(p['stack'])}</div>
{bullets_html(p['bullets'])}
{f'<div class="tech">{esc(p["tech"])}</div>' if p['tech'] else ''}
</div>""" for p in d["projects"]]))

    main.append(sec("Recommendations",
                    [f'<div class="rec"><div class="who">{esc(r["who"])} — {esc(r["role"])}</div>'
                     f'<div class="quote">“{esc(r["quote"])}”</div></div>'
                     for r in d["recs"]]))

    body = (f'<div class="railbg"></div><div class="grid">'
            f'<aside class="rail">{"".join(rail)}</aside>'
            f'<div class="main">{"".join(main)}</div></div>')

    return (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<title>{esc(d["name"])} — CV</title><style>{css}</style></head>'
            f'<body>{body}</body></html>')


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = render(load())
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(doc)
        tmp = f.name
    try:
        subprocess.run(
            [chrome_binary(), "--headless=new", "--disable-gpu", "--no-sandbox",
             "--no-pdf-header-footer", f"--print-to-pdf={out}", tmp],
            check=True, capture_output=True, text=True, timeout=180)
    finally:
        os.unlink(tmp)
    if not out.exists() or out.stat().st_size < 10_000:
        sys.exit("PDF generation produced no usable output")
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
