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
from dataclasses import dataclass


@dataclass
class SearchResult:
    """A single search result, optionally with full scraped content."""

    url: str
    title: str = ""
    description: str = ""
    content: str = ""  # Full markdown from individual scrape


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
