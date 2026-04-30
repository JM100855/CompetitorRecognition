from dataclasses import dataclass
from hashlib import sha256

import httpx

from app.core.config import settings
from app.services.scraper import fetch_url


@dataclass(frozen=True)
class ExtractedDocument:
    title: str
    url: str
    text: str
    summary: str
    published_at: str | None
    source_name: str | None
    content_hash: str


def extract_web_document(url: str, *, title_hint: str = "", source_name: str | None = None) -> ExtractedDocument | None:
    html = fetch_url(url)
    if html is None:
        return None

    text = ""
    extracted_title = title_hint
    published_at = None
    try:
        import trafilatura

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        ) or ""
        metadata = trafilatura.extract_metadata(html)
        if metadata is not None:
            extracted_title = metadata.title or extracted_title
            published_at = metadata.date
            source_name = source_name or metadata.sitename
    except ImportError:
        text = ""

    if not text:
        # Reuse the simpler built-in extractor when trafilatura is not available.
        from app.services.extractors import extract_page_document

        fallback = extract_page_document(html)
        extracted_title = fallback["title"] or extracted_title
        text = fallback["raw_text"]

    summary = " ".join(text.split())[:900]
    content_hash = sha256(f"{extracted_title}\n{text[:4000]}".encode("utf-8")).hexdigest()
    return ExtractedDocument(
        title=extracted_title or url,
        url=url,
        text=text[:30000],
        summary=summary,
        published_at=published_at,
        source_name=source_name,
        content_hash=content_hash,
    )
