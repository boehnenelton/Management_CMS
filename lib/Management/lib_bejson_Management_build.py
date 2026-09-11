"""
Library:        lib_bejson_Management_build.py
Family:         Management
Description:    Static homepage HTML renderer and export writer — factored
                 out into its own file (adopted from Lineage B's separation
                 of concerns: pure renderer, no DB access, takes pre-loaded
                 dicts from the section libraries). Uses Python's stdlib
                 html.escape instead of a hand-rolled replace() chain
                 (security fix applied to both prior lineages, which both
                 had the same weakness here).
Version:        1.0.0
Date:           2026-07-03
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  6c9e3a1f-4b7d-4e2a-8c5f-1d6b3a9e7f31
"""

import os
import logging
from html import escape as _e
from pathlib import Path
from typing import Any, Dict, List


def _management_build_render_links_section(categories_grouped: Dict[str, List[dict]]) -> str:
    if not categories_grouped:
        return ""
    parts = []
    for category_name, links in categories_grouped.items():
        parts.append(f'<div class="cat-block"><h3 class="cat-name">{_e(category_name or "Uncategorized")}</h3><div class="link-grid">')
        for link in links:
            icon = f'<span class="link-icon">{_e(link.get("icon") or "")}</span>' if link.get("icon") else ""
            desc = f'<span class="link-desc">{_e(link.get("description") or "")}</span>' if link.get("description") else ""
            parts.append(
                f'<a class="link-card" href="{_e(link.get("url") or "")}" target="_blank" rel="noopener">'
                f'{icon}<span class="link-title">{_e(link.get("label") or "")}</span>{desc}</a>'
            )
        parts.append("</div></div>")
    return "<section class='section'><div class='section-title'>Links</div>" + "".join(parts) + "</section>"


def _management_build_render_notes_section(notes: List[dict]) -> str:
    if not notes:
        return ""
    parts = []
    for note in notes:
        bg = _e(note.get("color") or "#1a1a1a")
        parts.append(
            f'<div class="note-card" style="background:{bg}">'
            f'<div class="note-card-title">{_e(note.get("label") or "")}</div>'
            f'<div class="note-card-body">{_e(note.get("content") or "")}</div></div>'
        )
    return "<section class='section'><div class='section-title'>Notes</div><div class='notes-grid'>" + "".join(parts) + "</div></section>"


def _management_build_render_tasks_section(tasks: List[dict]) -> str:
    open_tasks = [t for t in tasks if not t.get("done")]
    if not open_tasks:
        return ""
    parts = []
    for task in open_tasks:
        priority = _e(task.get("priority") or "medium")
        parts.append(
            f'<div class="todo-item pri-{priority}"><span class="todo-dot"></span>'
            f'<span class="todo-text">{_e(task.get("label") or "")}</span>'
            f'<span class="todo-pri">{priority}</span></div>'
        )
    return "<section class='section'><div class='section-title'>To-Do</div><div class='todos-list'>" + "".join(parts) + "</div></section>"


_MANAGEMENT_BUILD_CLOCK_JS = """
function _mb_pad(v){return String(v).padStart(2,'0');}
function _mb_update_clock(){var n=new Date(),el=document.getElementById('clock');
if(el)el.textContent=_mb_pad(n.getHours())+':'+_mb_pad(n.getMinutes())+':'+_mb_pad(n.getSeconds());}
setInterval(_mb_update_clock,1000);_mb_update_clock();
""".strip()

_MANAGEMENT_BUILD_GREETING_JS = """
(function(){var h=new Date().getHours(),el=document.getElementById('greeting');
if(el)el.textContent=h<12?'Good morning':h<17?'Good afternoon':'Good evening';})();
""".strip()


def management_build_render_homepage(config: Dict[str, Any], categories_grouped: Dict[str, List[dict]],
                                      notes: List[dict], tasks: List[dict]) -> str:
    """
    Renders a complete self-contained homepage HTML string.
    config: result of management_config_load()
    categories_grouped: {category_name: [link_dict, ...]}
    notes: list of note dicts (generic schema: label, content, color, category)
    tasks: list of task dicts (generic schema: label, done, priority, detail)
    """
    title = _e(config.get("site_title", "My Homepage"))
    subtitle = _e(config.get("site_subtitle", "Start Page"))
    accent = _e(config.get("accent_color", "#DE2626"))
    bg = _e(config.get("bg_color", "#0a0a0a"))
    show_clock = config.get("show_clock", True)
    show_greeting = config.get("show_greeting", True)

    clock_html = '<div id="clock" class="clock"></div>' if show_clock else ""
    greeting_html = '<div id="greeting" class="greeting"></div>' if show_greeting else ""
    clock_js = _MANAGEMENT_BUILD_CLOCK_JS if show_clock else ""
    greeting_js = _MANAGEMENT_BUILD_GREETING_JS if show_greeting else ""

    sections = (
        _management_build_render_links_section(categories_grouped)
        + _management_build_render_notes_section(notes)
        + _management_build_render_tasks_section(tasks)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Source+Code+Pro:wght@400;600&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:{bg};--s:#141414;--s2:#1e1e1e;--t:#f0f0f0;--m:#888;--a:{accent};
  --font:Inter,system-ui,sans-serif;--mono:'Source Code Pro',monospace;--r:8px}}
body{{background:var(--bg);color:var(--t);font-family:var(--font);min-height:100vh}}
a{{color:inherit;text-decoration:none}}
.container{{max-width:1200px;margin:0 auto;padding:2rem 1.5rem}}
.site-header{{text-align:center;padding:3rem 0 2rem;border-bottom:1px solid #222;margin-bottom:2.5rem}}
.site-title{{font-size:2.4rem;font-weight:700;letter-spacing:-.5px}}
.site-subtitle{{color:var(--m);font-size:.95rem;margin-top:.3rem}}
.clock{{font-family:var(--mono);font-size:1.6rem;font-weight:600;color:var(--a);margin-top:.8rem;letter-spacing:2px}}
.greeting{{font-size:1rem;color:#aaa;margin-top:.4rem;font-weight:300}}
.section{{margin-bottom:2.5rem}}
.section-title{{font-size:.72rem;font-weight:600;letter-spacing:.12em;text-transform:uppercase;
  color:var(--m);margin-bottom:1rem;padding-bottom:.4rem;border-bottom:1px solid #222}}
.cat-block{{margin-bottom:1.8rem}}
.cat-name{{font-size:.78rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--a);margin-bottom:.65rem}}
.link-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:.55rem}}
.link-card{{display:flex;flex-direction:column;gap:.2rem;padding:.75rem 1rem;
  background:var(--s);border-radius:var(--r);border:1px solid #222;transition:border-color .15s}}
.link-card:hover{{border-color:var(--a)}}
.link-icon{{font-size:1rem}}.link-title{{font-size:.88rem;font-weight:600}}
.link-desc{{font-size:.73rem;color:var(--m);line-height:1.35}}
.notes-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:.75rem}}
.note-card{{border-radius:var(--r);padding:1rem 1.1rem;border:1px solid #333}}
.note-card-title{{font-size:.83rem;font-weight:700;margin-bottom:.45rem}}
.note-card-body{{font-size:.78rem;color:#ccc;line-height:1.55;white-space:pre-wrap}}
.todos-list{{display:flex;flex-direction:column;gap:.35rem}}
.todo-item{{display:flex;align-items:center;gap:.65rem;padding:.45rem .75rem;
  background:var(--s);border-radius:6px;border-left:3px solid #333}}
.todo-item.pri-high{{border-left-color:var(--a)}}.todo-item.pri-medium{{border-left-color:#e8a020}}
.todo-dot{{width:5px;height:5px;border-radius:50%;background:currentColor;flex-shrink:0}}
.todo-text{{flex:1;font-size:.83rem}}
.todo-pri{{font-size:.68rem;color:var(--m);text-transform:uppercase;letter-spacing:.06em}}
.site-footer{{text-align:center;padding:2rem 0;border-top:1px solid #222;color:var(--m);font-size:.72rem;margin-top:3rem}}
@media(max-width:600px){{.site-title{{font-size:1.6rem}}
  .link-grid{{grid-template-columns:repeat(auto-fill,minmax(140px,1fr))}}
  .notes-grid{{grid-template-columns:1fr}}}}
</style></head><body>
<div class="container">
  <header class="site-header">
    <div class="site-title">{title}</div><div class="site-subtitle">{subtitle}</div>
    {clock_html}{greeting_html}
  </header>
  {sections}
  <footer class="site-footer">Built with Management_CMS &middot; Elton Boehnen &middot; boehnenelton2024.pages.dev</footer>
</div>
<script>{clock_js}{greeting_js}</script>
</body></html>"""


def management_build_write_export(export_output_path, html_content: str) -> Dict[str, Any]:
    """Writes the rendered HTML to export_output_path/index.html atomically. Returns {"path": str, "size": int}."""
    export_output_path = Path(export_output_path)
    export_output_path.mkdir(parents=True, exist_ok=True)
    output_file = export_output_path / "index.html"
    tmp_file = output_file.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        f.write(html_content)
        f.flush()
        os.fsync(f.fileno())
    tmp_file.replace(output_file)
    logging.info("Homepage exported to: %s (%d bytes)", output_file, len(html_content))
    return {"path": str(output_file), "size": len(html_content)}
