"""Sitemap parsing and URL labeling.

Reads a sitemap.xml (or sitemap index) and returns a list of (url, label) tuples
ready for embedding. Handles both <sitemapindex> (which lists child sitemaps)
and <urlset> (which lists actual URLs).

Label derivation:
- If the sitemap includes <news:title>, <image:title>, or <lastmod> context, we
  don't currently use them — we just derive a label from the URL path itself by
  converting the last meaningful slug segment into a space-separated phrase.

This is cheap and deterministic. For richer labels (actual page titles), callers
can enrich the list before embedding, but the slug-derived label is usually good
enough for semantic similarity against topic phrases.
"""

from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlparse


NAMESPACE = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _fetch(url: str, timeout: int = 20) -> bytes:
    """Fetch a URL and return raw bytes. Uses urllib to avoid extra deps."""
    req = urllib.request.Request(url, headers={"User-Agent": "navi-content-ops/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def _slug_to_label(url: str) -> str:
    """Turn a URL path into a human-readable phrase.

    Examples:
        /posts/best-prepaid-unlimited-plans → best prepaid unlimited plans
        /guides/2024/carrier-comparison/     → carrier comparison
        /about                                → about
        /                                     → home

    Falls back to the hostname if the path is empty.
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return "home"

    segments = [s for s in path.split("/") if s]
    # Skip purely numeric segments (years, pagination, etc.)
    meaningful = [s for s in segments if not s.isdigit()]
    if not meaningful:
        return parsed.netloc

    # Use the last meaningful segment (usually the page slug)
    slug = meaningful[-1]
    # Strip file extensions
    slug = re.sub(r"\.(html?|php|aspx?)$", "", slug, flags=re.IGNORECASE)
    # Replace hyphens/underscores with spaces
    label = re.sub(r"[-_]+", " ", slug).strip()
    return label or parsed.netloc


def parse_sitemap(sitemap_url: str, max_urls: int = 2000) -> list[tuple[str, str]]:
    """Fetch and parse a sitemap.xml, returning (url, label) tuples.

    Follows sitemap indexes (a sitemap that links to child sitemaps) one level
    deep. Caps total URLs at max_urls to keep embedding costs bounded.
    """
    collected: list[tuple[str, str]] = []

    try:
        data = _fetch(sitemap_url)
    except Exception as exc:
        raise RuntimeError(f"Could not fetch sitemap at {sitemap_url}: {exc}") from exc

    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise RuntimeError(f"Invalid XML in sitemap at {sitemap_url}: {exc}") from exc

    tag = root.tag.split("}", 1)[-1]

    if tag == "sitemapindex":
        # Follow up to 10 child sitemaps
        child_urls = [
            loc.text.strip()
            for loc in root.findall("sm:sitemap/sm:loc", NAMESPACE)
            if loc.text
        ][:10]
        for child_url in child_urls:
            if len(collected) >= max_urls:
                break
            try:
                collected.extend(parse_sitemap(child_url, max_urls=max_urls - len(collected)))
            except Exception as exc:
                print(f"  Skipping child sitemap {child_url}: {exc}")
    elif tag == "urlset":
        for url_el in root.findall("sm:url/sm:loc", NAMESPACE):
            if url_el.text:
                url = url_el.text.strip()
                label = _slug_to_label(url)
                collected.append((url, label))
                if len(collected) >= max_urls:
                    break
    else:
        raise RuntimeError(f"Unexpected root tag <{tag}> in sitemap at {sitemap_url}")

    return collected


def default_sitemap_url(page_url: str) -> str:
    """Given a page URL, return the default sitemap.xml location at the same domain."""
    parsed = urlparse(page_url)
    return f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
