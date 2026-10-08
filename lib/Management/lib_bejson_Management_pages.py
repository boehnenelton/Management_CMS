"""
Library:        lib_bejson_Management_pages.py
Family:         Management
Description:    Schema-only module. PAGE_FIELDS/PAGE_SEO_FIELDS here exist
                 solely because lib_bejson_Management_bootstrap.py's
                 webframework_scaffold_deploy_taxonomy_mfdb() call needs a
                 primary "Page" taxonomy entity to construct the
                 Content/Pages MFDB manifest that NavLink, admin Media, and
                 LandingSection are deployed into as secondary entities on
                 top of. Do NOT treat this as the real Page/PageSeo content
                 store — for actual site pages, see
                 lib_bejson_Management_content.py (PAGE_FIELDS/
                 PAGE_SEO_FIELDS there back Content/Page — singular — which
                 is what app.py's /api/pages* routes and the public-hosting
                 static build actually read and write).

                 AUDIT FIX (2026-09-24): this module previously also
                 shipped a full Page/PageSeo/PageCategory CRUD layer
                 (management_pages_add/list/get/update/delete/publish/
                 archive/seo_set/seo_get/category_add/category_list/
                 category_delete), inherited wholesale from the same
                 evaluated third-party CLI tool lib_bejson_Management_cli.py
                 was adapted from. It wrote to this taxonomy-scaffold Page
                 entity (Content/Pages, plural) instead of the real one
                 (Content/Page, singular) — meaning lib_bejson_Management_
                 cli.py's Pages CLI commands operated on a permanently-empty
                 dataset the web app never reads, with a schema that had
                 already drifted from content.py's (no title/excerpt/
                 page_type/locking fields — "title" was silently folded
                 into the generic taxonomy "label" field instead of stored
                 as its own field, the exact bug content.py's own changelog
                 records fixing on the real Page entity). The PageCategory
                 functions additionally referenced an entity bootstrap.py
                 never deploys as a secondary at all (only LandingSection/
                 PageSeo/Media/NavLink are), so category_create/list/delete
                 were unreachable no-ops/exceptions in practice. All of it
                 has been removed; lib_bejson_Management_cli.py's Pages/
                 Category/SEO methods now call lib_bejson_Management_
                 content.py and lib_bejson_Management_taxonomy.py directly,
                 against the same cms_page/cms_category manifests app.py
                 uses, so there is exactly one Page/PageSeo implementation
                 in the codebase. management_pages_slugify() is kept since
                 it's a generic helper still safe to reuse.
Version:        3.0.0
Date:           2026-09-24
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  9f1c3d7a-2e8b-4a5f-b6d1-5e9c8a2f7d43
"""

import re
import uuid

PAGE_FIELDS = [
    {"name": "slug",               "type": "string"},
    {"name": "status",             "type": "string"},   # draft | published | archived
    {"name": "meta_description",   "type": "string"},
    {"name": "layout",             "type": "string"},    # e.g. "default", "landing"
    {"name": "content_html",       "type": "string"},
    {"name": "content_markdown",   "type": "string"},
    {"name": "author",             "type": "string"},
    {"name": "featured_image",     "type": "string"},
    {"name": "parent_page_id_fk",  "type": "string"},    # page hierarchy
    {"name": "sort_order",         "type": "integer"},
]

PAGE_STATUSES = ("draft", "published", "archived")

# SEO metadata, one row per page — secondary entity, not a taxonomy.
PAGE_SEO_FIELDS = [
    {"name": "seo_id",            "type": "string"},
    {"name": "page_id_fk",        "type": "string"},
    {"name": "meta_title",        "type": "string"},
    {"name": "meta_keywords",     "type": "string"},
    {"name": "og_title",          "type": "string"},
    {"name": "og_description",   "type": "string"},
    {"name": "og_image",          "type": "string"},
    {"name": "canonical_url",     "type": "string"},
    {"name": "robots_directive",  "type": "string"},
    {"name": "created_at",        "type": "string"},
]


def management_pages_slugify(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or str(uuid.uuid4())[:8]
