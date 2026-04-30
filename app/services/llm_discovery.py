import json
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.services.discovery import DiscoveredSource

ALLOWED_PAGE_TYPES = {
    "homepage",
    "pricing",
    "product",
    "careers",
    "industry-news",
    "community-signal",
    "market-data",
    "analysis",
    "macro-news",
    "vendor-site",
    "newsletter",
    "research",
    "docs",
}


def discover_sources_with_ollama(name: str, description: str | None = None) -> list[DiscoveredSource]:
    prompt = _build_prompt(name, description)
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            response = client.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            response.raise_for_status()
    except httpx.HTTPError:
        return []

    payload = response.json()
    raw = payload.get("response", "")
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []

    items = parsed.get("sources", []) if isinstance(parsed, dict) else []
    discovered: list[DiscoveredSource] = []
    for item in items:
        source = _coerce_source(item)
        if source is not None:
            discovered.append(source)
    return discovered


def _build_prompt(name: str, description: str | None) -> str:
    return f"""
You are helping a competitor-intelligence scraper.
Given a niche, return a compact JSON object with a top-level "sources" array.

Goal:
- identify direct competitor company sites first
- identify niche-specific news, community, research, regulator, and market-data sources
- prefer stable public URLs that can be scraped directly
- include a mix of vendor websites and independent sources
- avoid login walls, search result pages, and vague company names without URLs

Niche: {name}
Description: {description or "n/a"}

Rules:
- Return 10 to 12 sources.
- Bias toward breadth, not repetition:
  - 4 to 6 competitor companies
  - 3 to 4 niche publications / newsletters / communities
  - 2 to 3 market-data / research / regulator sources
- Each source must have:
  company_name, domain, page_type, url, rationale, score
- page_type must be one of:
  homepage, pricing, product, careers, industry-news, community-signal, market-data,
  analysis, macro-news, vendor-site, newsletter, research, docs
- score must be a float between 0.5 and 1.0
- url must be absolute and start with https://
- For competitor companies, prefer the canonical homepage or a strong pricing/product page.
- Include both incumbent and newer companies when relevant.
- Include at least one source that is not a company website.
- Do not return duplicate domains unless different paths add real value.
- When unsure, prefer the company homepage rather than a speculative deep link.
- output JSON only, no markdown
""".strip()


def _coerce_source(item: object) -> DiscoveredSource | None:
    if not isinstance(item, dict):
        return None

    url = str(item.get("url", "")).strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    company_name = str(item.get("company_name", "")).strip()
    domain = str(item.get("domain", "")).strip() or parsed.netloc.replace("www.", "")
    page_type = str(item.get("page_type", "")).strip().lower()
    rationale = str(item.get("rationale", "")).strip()

    if not company_name or not rationale or page_type not in ALLOWED_PAGE_TYPES:
        return None

    try:
        score = float(item.get("score", 0.6))
    except (TypeError, ValueError):
        score = 0.6

    return DiscoveredSource(
        company_name=company_name,
        domain=domain,
        page_type=page_type,
        url=url,
        rationale=rationale,
        score=round(min(max(score, 0.5), 1.0), 3),
    )
