"""
Library:        lib_bejson_Management_landing.py
Family:         Management
Description:    Landing page section builder — hero, features, pricing,
                 testimonials, CTA, FAQ, content, gallery, stats,
                 newsletter. Sections are LandingSection records stored as
                 a secondary entity in the Pages MFDB (page_id_fk links
                 back to a Page, idx_position controls order) — proper
                 MFDB storage, not a loose JSON file per page.

                 Section renderers adapted from an external reference CMS,
                 kept because they were already sound (correct html.escape
                 usage throughout); rebuilt here as pure functions storing
                 through lib_bejson_Core_mfdb_core like every other
                 Management module, with full UUIDs.
Version:        1.0.0
Date:           2026-07-05
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  7d2e9f4a-1c6b-4e8d-a3f7-9b5c2d8e1f41
"""

import os
import sys
import json
import uuid
from datetime import datetime, timezone
from html import escape as _e
from typing import Any, Dict, List, Optional

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
if CORE_DIR not in sys.path:
    sys.path.append(CORE_DIR)

import lib_bejson_Core_mfdb_core as MFDBCore

LANDING_SECTION_FIELDS = [
    {"name": "section_id",   "type": "string"},
    {"name": "page_id_fk",   "type": "string"},
    {"name": "section_type", "type": "string"},
    {"name": "section_data", "type": "string"},   # JSON-serialized dict, shape depends on section_type
    {"name": "idx_position", "type": "integer"},
    {"name": "created_at",   "type": "string"},
]

LANDING_SECTION_TYPES = {
    "hero":         {"label": "Hero Section",    "fields": ["headline", "subheadline", "cta_text", "cta_url", "background_image", "alignment"]},
    "features":     {"label": "Features Grid",   "fields": ["section_title", "features"]},
    "pricing":      {"label": "Pricing Table",   "fields": ["section_title", "plans", "highlighted_plan"]},
    "testimonials": {"label": "Testimonials",    "fields": ["section_title", "testimonials"]},
    "cta":          {"label": "Call to Action",  "fields": ["headline", "subheadline", "cta_text", "cta_url", "background_color"]},
    "faq":          {"label": "FAQ Accordion",   "fields": ["section_title", "questions"]},
    "content":      {"label": "Content Block",   "fields": ["title", "body_html", "layout"]},
    "gallery":      {"label": "Image Gallery",   "fields": ["section_title", "images", "columns"]},
    "stats":        {"label": "Stats Bar",       "fields": ["stats"]},
    "newsletter":   {"label": "Newsletter Signup", "fields": ["headline", "subheadline", "placeholder_text", "button_text"]},
}


def management_landing_list_section_types() -> Dict[str, Dict[str, Any]]:
    return LANDING_SECTION_TYPES.copy()


def management_landing_add_section(manifest_path: str, page_id: str, section_type: str,
                                    section_data: dict, idx_position: Optional[int] = None) -> str:
    section_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if idx_position is None:
        existing = management_landing_get_sections(manifest_path, page_id)
        idx_position = len(existing)
    MFDBCore.mfdb_core_add_entity_record(
        manifest_path, "LandingSection",
        [section_id, page_id, section_type, json.dumps(section_data), idx_position, created_at],
    )
    return section_id


def management_landing_get_sections(manifest_path: str, page_id: str) -> List[Dict[str, Any]]:
    all_sections = MFDBCore.mfdb_core_load_entity(manifest_path, "LandingSection")
    sections = [s for s in all_sections if s.get("page_id_fk") == page_id]
    sections.sort(key=lambda s: s.get("idx_position", 0))
    return sections


def management_landing_update_section(manifest_path: str, section_id: str, section_data: dict) -> bool:
    all_sections = MFDBCore.mfdb_core_load_entity(manifest_path, "LandingSection")
    for i, s in enumerate(all_sections):
        if s.get("section_id") == section_id:
            merged = {**json.loads(s.get("section_data") or "{}"), **section_data}
            MFDBCore.mfdb_core_update_entity_record(manifest_path, "LandingSection", i, "section_data", json.dumps(merged))
            return True
    return False


def management_landing_remove_section(manifest_path: str, section_id: str) -> bool:
    all_sections = MFDBCore.mfdb_core_load_entity(manifest_path, "LandingSection")
    for i, s in enumerate(all_sections):
        if s.get("section_id") == section_id:
            MFDBCore.mfdb_core_remove_entity_record(manifest_path, "LandingSection", i)
            return True
    return False


def management_landing_reorder_sections(manifest_path: str, page_id: str, section_id_order: list) -> bool:
    all_sections = MFDBCore.mfdb_core_load_entity(manifest_path, "LandingSection")
    order_index = {sid: i for i, sid in enumerate(section_id_order)}
    changed = False
    for i, s in enumerate(all_sections):
        if s.get("page_id_fk") == page_id and s.get("section_id") in order_index:
            MFDBCore.mfdb_core_update_entity_record(manifest_path, "LandingSection", i, "idx_position", order_index[s["section_id"]])
            changed = True
    return changed


def management_landing_render_sections(manifest_path: str, page_id: str, primary_color: str = "#DE2626") -> str:
    """Renders all of a page's sections, in order, to a single HTML string."""
    sections = management_landing_get_sections(manifest_path, page_id)
    parts = []
    for section in sections:
        renderer = _SECTION_RENDERERS.get(section.get("section_type"))
        if renderer:
            data = json.loads(section.get("section_data") or "{}")
            parts.append(renderer(data, primary_color))
    return "\n".join(parts)


def _render_hero(data: dict, primary: str) -> str:
    align = data.get("alignment", "center")
    bg = data.get("background_image", "")
    bg_style = f'background-image:url({_e(bg)});background-size:cover;' if bg else f'background:linear-gradient(135deg, {primary}, #1a1a1a);'
    return f"""<section class="cms-hero" style="{bg_style}color:#fff;padding:100px 24px;text-align:{align};">
  <div style="max-width:900px;margin:0 auto;">
    <h1 style="font-size:3rem;margin-bottom:1rem;line-height:1.2">{_e(data.get('headline', ''))}</h1>
    <p style="font-size:1.25rem;opacity:0.9;margin-bottom:2rem">{_e(data.get('subheadline', ''))}</p>
    <a href="{_e(data.get('cta_url', '#'))}" style="display:inline-block;background:#fff;color:#1a1a1a;padding:14px 32px;border-radius:6px;text-decoration:none;font-weight:600">{_e(data.get('cta_text', 'Get Started'))}</a>
  </div>
</section>"""


def _render_features(data: dict, primary: str) -> str:
    cards = ""
    for f in data.get("features", []):
        icon = f.get("icon", "")
        icon_html = f'<div style="font-size:2rem;margin-bottom:0.5rem">{_e(icon)}</div>' if icon else ""
        cards += f"""<div style="flex:1;min-width:250px;background:#fff;padding:1.5rem;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
  {icon_html}
  <h3 style="margin-bottom:0.5rem">{_e(f.get('title', ''))}</h3>
  <p style="color:#6b7280">{_e(f.get('description', ''))}</p>
</div>"""
    return f"""<section style="padding:60px 24px;max-width:1200px;margin:0 auto;">
  <h2 style="text-align:center;margin-bottom:2rem">{_e(data.get('section_title', 'Features'))}</h2>
  <div style="display:flex;flex-wrap:wrap;gap:1.5rem">{cards}</div>
</section>"""


def _render_pricing(data: dict, primary: str) -> str:
    plans = data.get("plans", [])
    highlighted = data.get("highlighted_plan", "")
    cards = ""
    for plan in plans:
        is_hi = plan.get("name") == highlighted
        border = f"2px solid {primary}" if is_hi else "1px solid #e5e7eb"
        bg = f"background:{primary};color:#fff;" if is_hi else "background:#fff;"
        features = ""
        for feat in plan.get("features", []):
            bullet = "&#10003; " if is_hi else "&#8226; "
            features += f'<li style="margin-bottom:0.5rem">{bullet}{_e(feat)}</li>'
        btn_style = f"#fff;color:{primary}" if is_hi else f"{primary};color:#fff"
        cards += f"""<div style="flex:1;min-width:280px;padding:2rem;border-radius:8px;border:{border};{bg}">
  <h3 style="margin-bottom:0.5rem">{_e(plan.get('name', ''))}</h3>
  <p style="font-size:2rem;font-weight:700;margin-bottom:1rem">{_e(plan.get('price', ''))}</p>
  <ul style="list-style:none;padding:0;margin-bottom:1.5rem">{features}</ul>
  <a href="{_e(plan.get('cta_url', '#'))}" style="display:block;text-align:center;padding:10px;border-radius:6px;background:{btn_style};text-decoration:none;font-weight:600">{_e(plan.get('cta_text', 'Choose'))}</a>
</div>"""
    return f"""<section style="padding:60px 24px;max-width:1200px;margin:0 auto;background:#f3f4f6">
  <h2 style="text-align:center;margin-bottom:2rem">{_e(data.get('section_title', 'Pricing'))}</h2>
  <div style="display:flex;flex-wrap:wrap;gap:1.5rem;justify-content:center">{cards}</div>
</section>"""


def _render_testimonials(data: dict, primary: str) -> str:
    cards = ""
    for t in data.get("testimonials", []):
        cards += f"""<div style="flex:1;min-width:280px;background:#fff;padding:1.5rem;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
  <p style="font-style:italic;margin-bottom:1rem;color:#374151">&quot;{_e(t.get('quote', ''))}&quot;</p>
  <p style="font-weight:600">{_e(t.get('name', ''))}</p>
  <p style="color:#9ca3af;font-size:0.875rem">{_e(t.get('role', ''))}</p>
</div>"""
    return f"""<section style="padding:60px 24px;max-width:1200px;margin:0 auto;">
  <h2 style="text-align:center;margin-bottom:2rem">{_e(data.get('section_title', 'What People Say'))}</h2>
  <div style="display:flex;flex-wrap:wrap;gap:1.5rem">{cards}</div>
</section>"""


def _render_cta(data: dict, primary: str) -> str:
    bg = data.get("background_color", primary)
    return f"""<section style="background:{bg};color:#fff;padding:80px 24px;text-align:center;">
  <div style="max-width:700px;margin:0 auto;">
    <h2 style="font-size:2rem;margin-bottom:1rem">{_e(data.get('headline', ''))}</h2>
    <p style="opacity:0.9;margin-bottom:2rem">{_e(data.get('subheadline', ''))}</p>
    <a href="{_e(data.get('cta_url', '#'))}" style="display:inline-block;background:#fff;color:#1a1a1a;padding:14px 32px;border-radius:6px;text-decoration:none;font-weight:600">{_e(data.get('cta_text', 'Get Started'))}</a>
  </div>
</section>"""


def _render_faq(data: dict, primary: str) -> str:
    items = ""
    for q in data.get("questions", []):
        items += f"""<details style="margin-bottom:0.75rem;background:#fff;border-radius:6px;overflow:hidden">
  <summary style="padding:1rem;cursor:pointer;font-weight:600;background:#f9fafb;border:1px solid #e5e7eb">{_e(q.get('question', ''))}</summary>
  <div style="padding:1rem;border:1px solid #e5e7eb;border-top:none">{_e(q.get('answer', ''))}</div>
</details>"""
    return f"""<section style="padding:60px 24px;max-width:800px;margin:0 auto;">
  <h2 style="text-align:center;margin-bottom:2rem">{_e(data.get('section_title', 'Frequently Asked Questions'))}</h2>
  {items}
</section>"""


def _render_content(data: dict, primary: str) -> str:
    layout = data.get("layout", "single")
    max_width = "1200px" if layout == "wide" else "720px"
    # body_html is intentionally NOT escaped — it's rich content the page author
    # controls, same trust boundary as any other CMS body-content field.
    return f"""<section style="padding:60px 24px;max-width:{max_width};margin:0 auto;">
  <h2>{_e(data.get('title', ''))}</h2>
  <div>{data.get('body_html', '')}</div>
</section>"""


def _render_gallery(data: dict, primary: str) -> str:
    cols = data.get("columns", 3)
    imgs = ""
    for img in data.get("images", []):
        imgs += f'<div style="flex:1;min-width:{100 // max(cols, 1)}%;padding:4px"><img src="{_e(img)}" style="width:100%;border-radius:6px"></div>'
    return f"""<section style="padding:60px 24px;max-width:1200px;margin:0 auto;">
  <h2 style="text-align:center;margin-bottom:2rem">{_e(data.get('section_title', 'Gallery'))}</h2>
  <div style="display:flex;flex-wrap:wrap;margin:-4px">{imgs}</div>
</section>"""


def _render_stats(data: dict, primary: str) -> str:
    items = ""
    for s in data.get("stats", []):
        items += f"""<div style="text-align:center;flex:1;min-width:150px">
  <p style="font-size:2.5rem;font-weight:700;color:{primary}">{_e(s.get('value', ''))}</p>
  <p style="color:#6b7280;text-transform:uppercase;font-size:0.75rem;letter-spacing:1px">{_e(s.get('label', ''))}</p>
</div>"""
    return f"""<section style="padding:40px 24px;max-width:1200px;margin:0 auto;border-top:1px solid #e5e7eb;border-bottom:1px solid #e5e7eb">
  <div style="display:flex;flex-wrap:wrap;gap:2rem;justify-content:center">{items}</div>
</section>"""


def _render_newsletter(data: dict, primary: str) -> str:
    return f"""<section style="padding:60px 24px;max-width:600px;margin:0 auto;text-align:center;">
  <h2 style="margin-bottom:0.5rem">{_e(data.get('headline', 'Stay Updated'))}</h2>
  <p style="color:#6b7280;margin-bottom:1.5rem">{_e(data.get('subheadline', 'Subscribe to our newsletter'))}</p>
  <form style="display:flex;gap:0.5rem" onsubmit="event.preventDefault();alert('Thanks for subscribing!');">
    <input type="email" placeholder="{_e(data.get('placeholder_text', 'Enter your email'))}" style="flex:1;padding:12px;border:1px solid #e5e7eb;border-radius:6px" required>
    <button type="submit" style="padding:12px 24px;background:{primary};color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600">{_e(data.get('button_text', 'Subscribe'))}</button>
  </form>
</section>"""


_SECTION_RENDERERS = {
    "hero": _render_hero, "features": _render_features, "pricing": _render_pricing,
    "testimonials": _render_testimonials, "cta": _render_cta, "faq": _render_faq,
    "content": _render_content, "gallery": _render_gallery, "stats": _render_stats,
    "newsletter": _render_newsletter,
}
