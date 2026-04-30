from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = "duckduckgo"


def discover_web_results(query: str, max_results: int | None = None) -> list[SearchResult]:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []

    limit = max_results or settings.ddg_max_results
    results: list[SearchResult] = []
    with DDGS() as ddgs:
        raw_results = ddgs.text(
            query,
            region=settings.ddg_region,
            max_results=limit,
        )
        for item in raw_results:
            title = str(item.get("title", "")).strip()
            url = str(item.get("href", "")).strip()
            snippet = str(item.get("body", "")).strip()
            if not url:
                continue
            results.append(SearchResult(title=title, url=url, snippet=snippet))
    return results
