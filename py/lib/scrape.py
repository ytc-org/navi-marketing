"""Web scraping and search via Firecrawl.

Handles both SDK versions:
  - Newer 'firecrawl' package: Firecrawl class with .scrape() and .search()
  - Older 'firecrawl' package: FirecrawlApp class with .scrape_url() and .search()

Note: Firecrawl's search endpoint returns metadata only (URL, title, description)
even when scrape_options is passed. To get full page content, we search first
then scrape each result individually.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """A single search result, optionally with full scraped content."""

    url: str
    title: str = ""
    description: str = ""
    content: str = ""  # Full markdown from individual scrape


@dataclass
class ScrapedPage:
    """A scraped page with markdown body plus head/metadata signals.

    Markdown extraction silently drops the HTML ``<head>`` (meta description,
    title tag, canonical, JSON-LD schema) and most JS-rendered widgets (coverage
    maps, interactive pricing cards). Workflows that judged a page only from its
    markdown were flagging those elements as "missing" when they were present on
    the live page. This carries the head signals through so downstream prompts
    can rely on them instead of guessing from the body text.
    """

    url: str
    markdown: str = ""
    meta_title: str | None = None
    meta_description: str | None = None
    canonical: str | None = None
    has_schema: bool = False
    og_tags: dict[str, str] = field(default_factory=dict)
    # True when we got real HTML to inspect. When False, "not detected" below
    # means "couldn't check" — NOT "absent from the page".
    head_inspected: bool = False

    def head_signals_markdown(self) -> str:
        """Render the detected head/metadata signals as a Markdown block."""
        if not self.head_inspected:
            return (
                "Head/metadata signals: NOT AVAILABLE for this page "
                "(HTML head could not be inspected). Do not infer that meta "
                "tags, schema, or canonical are missing — they were simply not "
                "captured by the crawl."
            )
        lines = [
            f"- Meta title: {self.meta_title or '(not detected)'}",
            f"- Meta description: {self.meta_description or '(not detected)'}",
            f"- Canonical URL: {self.canonical or '(not detected)'}",
            f"- Structured data (JSON-LD schema): {'present' if self.has_schema else '(not detected)'}",
        ]
        if self.og_tags:
            og = ", ".join(f"{k}={v}" for k, v in sorted(self.og_tags.items()))
            lines.append(f"- Open Graph tags: {og}")
        return "\n".join(lines)


def _get_api_key() -> str | None:
    return os.getenv("FIRECRAWL_API_KEY")


def _get_app():
    """Get a Firecrawl client, handling both SDK versions."""
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("FIRECRAWL_API_KEY not set. Add it to your .env file.")

    import firecrawl

    if hasattr(firecrawl, "FirecrawlApp"):
        return firecrawl.FirecrawlApp(api_key=api_key)
    elif hasattr(firecrawl, "Firecrawl"):
        return firecrawl.Firecrawl(api_key=api_key)
    else:
        raise RuntimeError(f"Unexpected firecrawl module. Available: {dir(firecrawl)}")


def _scrape(app, url: str) -> str:
    """Call the scrape method, handling both SDK versions. Returns markdown string."""
    for method_name in ("scrape_url", "scrape"):
        method = getattr(app, method_name, None)
        if not method:
            continue
        try:
            if method_name == "scrape_url":
                result = method(url, params={"formats": ["markdown"]})
            else:
                result = method(url, formats=["markdown"])

            if isinstance(result, dict):
                return result.get("markdown", "")
            if hasattr(result, "markdown"):
                return result.markdown or ""
            return ""
        except TypeError:
            # Wrong signature — try the other method
            continue

    raise RuntimeError(f"Firecrawl client has no working scrape method. Available: {dir(app)}")


def _scrape_full(app, url: str) -> ScrapedPage:
    """Scrape a URL for markdown + raw HTML, parse head/metadata signals.

    Requests both ``markdown`` and ``html`` so we can read the ``<head>``
    deterministically rather than asking the LLM to find meta tags in body text
    (which strips them). Falls back to markdown-only if the SDK rejects the html
    format for some reason.
    """
    result = None
    for method_name in ("scrape_url", "scrape"):
        method = getattr(app, method_name, None)
        if not method:
            continue
        try:
            if method_name == "scrape_url":
                result = method(url, params={"formats": ["markdown", "html"]})
            else:
                result = method(url, formats=["markdown", "html"])
            break
        except TypeError:
            continue

    if result is None:
        # Couldn't fetch with html; fall back to markdown-only string path.
        return ScrapedPage(url=url, markdown=_scrape(app, url), head_inspected=False)

    markdown = _field(result, "markdown") or ""
    html = _field(result, "html") or _field(result, "rawHtml") or ""
    metadata = _field(result, "metadata") or {}

    page = ScrapedPage(url=url, markdown=markdown)
    _populate_head_signals(page, html, metadata)
    return page


def _field(result, name: str):
    """Read a field from a Firecrawl result that may be a dict or an object."""
    if isinstance(result, dict):
        return result.get(name)
    return getattr(result, name, None)


# --- Head/metadata parsing (regex-based; no new dependencies) ---

def _populate_head_signals(page: ScrapedPage, html: str, metadata) -> None:
    """Fill a ScrapedPage's head signals from Firecrawl metadata and raw HTML.

    Prefers Firecrawl's parsed ``metadata`` (already extracts title/description/
    og tags) and falls back to scanning the raw HTML head. Either source counts
    as a successful inspection.
    """
    md = metadata if isinstance(metadata, dict) else {}

    title = md.get("title") or md.get("ogTitle")
    description = md.get("description") or md.get("ogDescription")
    canonical = md.get("canonical") or md.get("sourceURL")
    og_tags: dict[str, str] = {
        k: v for k, v in md.items()
        if isinstance(k, str) and k.startswith("og") and isinstance(v, str)
    }

    if html:
        if not title:
            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            if m:
                title = m.group(1).strip()
        if not description:
            description = _meta_content(html, "description")
        if not canonical:
            m = re.search(
                r'<link[^>]+rel=["\']canonical["\'][^>]*>', html, re.IGNORECASE
            )
            if m:
                href = re.search(r'href=["\']([^"\']+)["\']', m.group(0), re.IGNORECASE)
                if href:
                    canonical = href.group(1).strip()
        page.has_schema = bool(
            re.search(
                r'<script[^>]+type=["\']application/ld\+json["\']',
                html,
                re.IGNORECASE,
            )
        )

    page.meta_title = title.strip() if isinstance(title, str) else None
    page.meta_description = description.strip() if isinstance(description, str) else None
    page.canonical = canonical.strip() if isinstance(canonical, str) else None
    page.og_tags = og_tags
    # We "inspected" the head if we had either parsed metadata or raw HTML.
    page.head_inspected = bool(md) or bool(html)


def _meta_content(html: str, name: str) -> str | None:
    """Pull <meta name="..." content="..."> regardless of attribute order."""
    for tag in re.findall(r"<meta\b[^>]*>", html, re.IGNORECASE):
        name_m = re.search(r'name=["\']([^"\']+)["\']', tag, re.IGNORECASE)
        if not name_m or name_m.group(1).strip().lower() != name.lower():
            continue
        content_m = re.search(r'content=["\']([^"\']*)["\']', tag, re.IGNORECASE)
        if content_m:
            return content_m.group(1).strip()
    return None


def scrape_page_full(url: str) -> ScrapedPage:
    """Scrape a URL and return markdown plus parsed head/metadata signals.

    Use this for the *target* page of an audit, where knowing the real meta
    tags and schema matters. Competitor scraping can use the lighter
    ``scrape_page`` (markdown only). Returns a ScrapedPage with empty markdown
    on failure rather than raising.
    """
    if not _get_api_key():
        print("  Warning: FIRECRAWL_API_KEY not set. Skipping scrape.")
        return ScrapedPage(url=url, head_inspected=False)

    try:
        app = _get_app()
        return _scrape_full(app, url)
    except Exception as exc:
        print(f"  Warning: Firecrawl error for {url}: {exc}")
        return ScrapedPage(url=url, head_inspected=False)


def scrape_page(url: str) -> str:
    """Scrape a URL via Firecrawl and return the page content as Markdown.

    Returns empty string on failure rather than raising — callers decide
    whether missing content is fatal.
    """
    if not _get_api_key():
        print("  Warning: FIRECRAWL_API_KEY not set. Skipping scrape.")
        return ""

    try:
        app = _get_app()
        return _scrape(app, url)
    except Exception as exc:
        print(f"  Warning: Firecrawl error for {url}: {exc}")
        return ""


def scrape_pages(urls: list[str]) -> dict[str, str]:
    """Scrape multiple URLs. Returns a dict mapping URL -> markdown content."""
    results: dict[str, str] = {}
    for url in urls:
        print(f"  Scraping: {url}")
        results[url] = scrape_page(url)
    return results


def search(query: str, *, limit: int = 5) -> list[SearchResult]:
    """Search the web via Firecrawl. Returns metadata only (no page content).

    Use search_and_scrape() if you need full page content.
    """
    if not _get_api_key():
        print(f"  Warning: FIRECRAWL_API_KEY not set. Skipping search for: {query}")
        return []

    try:
        app = _get_app()
        response = app.search(query=query, limit=limit)
        return _parse_search_response(response)
    except Exception as exc:
        print(f"  Warning: Firecrawl search error for '{query}': {exc}")
        return []


def search_and_scrape(
    query: str,
    *,
    limit: int = 5,
    scrape_content: bool = True,
) -> list[SearchResult]:
    """Search the web via Firecrawl, then scrape each result for full content.

    Args:
        query: Search query string.
        limit: Max number of results to return.
        scrape_content: If True, each result gets individually scraped for
                        full markdown content. If False, just returns
                        URL/title/description (much faster, much cheaper).

    Returns:
        List of SearchResult objects.
    """
    results = search(query, limit=limit)

    if not scrape_content or not results:
        return results

    # Scrape each result individually for full content
    app = None
    try:
        app = _get_app()
    except Exception:
        return results

    for r in results:
        if not r.url:
            continue
        try:
            r.content = _scrape(app, r.url)
        except Exception as exc:
            print(f"    Warning: Could not scrape {r.url}: {exc}")
            r.content = ""

    return results


def _parse_search_response(response) -> list[SearchResult]:
    """Parse whatever shape the SDK returns into a list of SearchResult."""
    items = _extract_items(response)
    results: list[SearchResult] = []

    for item in items:
        if isinstance(item, dict):
            results.append(SearchResult(
                url=item.get("url", ""),
                title=item.get("title", ""),
                description=item.get("description", ""),
            ))
        elif hasattr(item, "url"):
            results.append(SearchResult(
                url=getattr(item, "url", ""),
                title=getattr(item, "title", ""),
                description=getattr(item, "description", ""),
            ))

    return results


def _extract_items(response) -> list:
    """Pull the list of result items from whatever shape the SDK returns."""
    if isinstance(response, list):
        return response
    # Object with .web attribute (SearchData)
    if hasattr(response, "web") and response.web:
        return response.web
    # Dict with common keys
    if isinstance(response, dict):
        for key in ("web", "data", "results"):
            if key in response and isinstance(response[key], list):
                return response[key]
    # Fallback: try other attributes
    for attr in ("data", "results"):
        val = getattr(response, attr, None)
        if isinstance(val, list):
            return val
    try:
        return list(response)
    except TypeError:
        return []
