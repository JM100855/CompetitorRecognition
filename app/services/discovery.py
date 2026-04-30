from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.config import settings


@dataclass(frozen=True)
class DiscoveredSource:
    company_name: str
    domain: str
    page_type: str
    url: str
    rationale: str
    score: float


@dataclass(frozen=True)
class SourceTemplate:
    company_name: str
    page_type: str
    url: str
    tags: tuple[str, ...]
    rationale: str
    base_score: float = 0.45


SOURCE_TEMPLATES: tuple[SourceTemplate, ...] = (
    SourceTemplate(
        company_name="TechCrunch",
        page_type="industry-news",
        url="https://techcrunch.com/",
        tags=("tech", "technology", "software", "startups", "saas", "ai"),
        rationale="Broad technology startup and product coverage.",
        base_score=0.98,
    ),
    SourceTemplate(
        company_name="Hacker News",
        page_type="community-signal",
        url="https://news.ycombinator.com/",
        tags=("tech", "technology", "software", "developer", "ai", "startups"),
        rationale="High-signal technology discussion and launch discovery.",
        base_score=0.92,
    ),
    SourceTemplate(
        company_name="The Verge",
        page_type="industry-news",
        url="https://www.theverge.com/tech",
        tags=("tech", "technology", "consumer-tech", "software", "ai"),
        rationale="Product, platform, and ecosystem shifts in tech.",
        base_score=0.86,
    ),
    SourceTemplate(
        company_name="Ars Technica",
        page_type="analysis",
        url="https://arstechnica.com/",
        tags=("tech", "technology", "software", "ai", "security"),
        rationale="Deeper reporting on technical and policy changes.",
        base_score=0.84,
    ),
    SourceTemplate(
        company_name="Reuters Energy",
        page_type="industry-news",
        url="https://www.reuters.com/business/energy/",
        tags=("oil", "gas", "energy", "utilities", "power", "oil-and-gas"),
        rationale="Free mainstream reporting on energy and commodities.",
        base_score=0.98,
    ),
    SourceTemplate(
        company_name="U.S. Energy Information Administration",
        page_type="market-data",
        url="https://www.eia.gov/",
        tags=("oil", "gas", "energy", "oil-and-gas", "power", "utilities"),
        rationale="Public energy statistics and official market context.",
        base_score=0.95,
    ),
    SourceTemplate(
        company_name="Rigzone",
        page_type="industry-news",
        url="https://www.rigzone.com/news/",
        tags=("oil", "gas", "energy", "oil-and-gas", "upstream"),
        rationale="Specialized oil and gas operations coverage.",
        base_score=0.9,
    ),
    SourceTemplate(
        company_name="OilPrice",
        page_type="analysis",
        url="https://oilprice.com/",
        tags=("oil", "gas", "energy", "oil-and-gas", "commodities"),
        rationale="Commodity and energy market commentary.",
        base_score=0.83,
    ),
    SourceTemplate(
        company_name="Reuters Business",
        page_type="macro-news",
        url="https://www.reuters.com/business/",
        tags=("general", "business", "industry", "markets"),
        rationale="General business baseline for any niche.",
        base_score=0.55,
    ),
    SourceTemplate(
        company_name="Associated Press Business",
        page_type="macro-news",
        url="https://apnews.com/hub/business",
        tags=("general", "business", "industry", "markets"),
        rationale="Free general business coverage for cross-checking.",
        base_score=0.5,
    ),
)


KEYWORD_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "tech": ("technology", "software", "startups", "developer", "ai", "saas"),
    "technology": ("tech", "software", "startups", "developer", "ai", "saas"),
    "oil": ("gas", "energy", "oil-and-gas", "commodities", "upstream"),
    "gas": ("oil", "energy", "oil-and-gas", "commodities", "upstream"),
    "energy": ("oil", "gas", "power", "utilities", "oil-and-gas"),
    "ai": ("tech", "technology", "software"),
}


def discover_sources_for_niche(name: str, description: str | None = None) -> list[DiscoveredSource]:
    llm_sources: list[DiscoveredSource] = []
    strategy = settings.discovery_strategy.lower()
    if strategy in {"ollama", "hybrid"}:
        from app.services.llm_discovery import discover_sources_with_ollama

        llm_sources = discover_sources_with_ollama(name, description)

    catalog_sources = _discover_catalog_sources(name, description)
    if strategy == "catalog":
        return catalog_sources
    if strategy == "ollama" and llm_sources:
        return _expand_source_graph(_merge_sources(llm_sources, []))

    return _expand_source_graph(_merge_sources(llm_sources, catalog_sources))


def _discover_catalog_sources(name: str, description: str | None = None) -> list[DiscoveredSource]:
    terms = _expand_terms(name, description)
    scored: list[DiscoveredSource] = []

    for template in SOURCE_TEMPLATES:
        overlap = len(terms.intersection(template.tags))
        if overlap == 0 and "general" not in template.tags:
            continue

        score = template.base_score + (0.07 * overlap)
        domain = urlparse(template.url).netloc.replace("www.", "")
        scored.append(
            DiscoveredSource(
                company_name=template.company_name,
                domain=domain,
                page_type=template.page_type,
                url=template.url,
                rationale=template.rationale,
                score=round(min(score, 1.0), 3),
            )
        )

    scored.sort(key=lambda item: item.score, reverse=True)
    top = scored[: settings.max_discovered_sources]
    if top:
        return top

    fallback = [
        template for template in SOURCE_TEMPLATES if "general" in template.tags
    ]
    return [
        DiscoveredSource(
            company_name=template.company_name,
            domain=urlparse(template.url).netloc.replace("www.", ""),
            page_type=template.page_type,
            url=template.url,
            rationale=template.rationale,
            score=template.base_score,
        )
        for template in fallback
    ]


def _merge_sources(
    primary: list[DiscoveredSource], secondary: list[DiscoveredSource]
) -> list[DiscoveredSource]:
    merged: dict[str, DiscoveredSource] = {}
    for source in sorted(primary + secondary, key=lambda item: item.score, reverse=True):
        if source.url in merged:
            continue
        merged[source.url] = source
    return list(merged.values())[: settings.max_discovered_sources]


def _expand_source_graph(sources: list[DiscoveredSource]) -> list[DiscoveredSource]:
    expanded: dict[str, DiscoveredSource] = {}
    for source in sources:
        if source.url not in expanded:
            expanded[source.url] = source
        for child in _expand_source(source):
            if child.url in expanded:
                continue
            expanded[child.url] = child

    ordered = sorted(expanded.values(), key=lambda item: item.score, reverse=True)
    return ordered[: settings.max_discovered_sources]


def _expand_source(source: DiscoveredSource) -> list[DiscoveredSource]:
    if source.page_type not in {"homepage", "vendor-site", "product"}:
        return []

    parsed = urlparse(source.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return []
    if parsed.path not in {"", "/"}:
        return []

    base_url = f"{parsed.scheme}://{parsed.netloc}"
    expansions = (
        ("pricing", "/pricing", "Likely pricing page for competitor packaging and positioning.", 0.08),
        ("product", "/product", "Likely product overview page for feature and roadmap tracking.", 0.06),
        ("docs", "/docs", "Likely docs page for capability and API signal tracking.", 0.05),
        ("careers", "/careers", "Likely hiring page for staffing and go-to-market signals.", 0.05),
    )
    results: list[DiscoveredSource] = []
    for page_type, path, rationale_suffix, penalty in expansions:
        results.append(
            DiscoveredSource(
                company_name=source.company_name,
                domain=source.domain,
                page_type=page_type,
                url=f"{base_url}{path}",
                rationale=f"{source.rationale} {rationale_suffix}",
                score=round(max(0.5, source.score - penalty), 3),
            )
        )
    return results


def _expand_terms(name: str, description: str | None = None) -> set[str]:
    raw = f"{name} {description or ''}".lower()
    separators = ",./_-"
    for separator in separators:
        raw = raw.replace(separator, " ")

    terms = {part.strip() for part in raw.split() if part.strip()}
    expanded = set(terms)
    for term in list(terms):
        expanded.update(KEYWORD_EXPANSIONS.get(term, ()))

    if "oil" in expanded and "gas" in expanded:
        expanded.add("oil-and-gas")
    return expanded
