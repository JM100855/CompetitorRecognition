import httpx

from app.core.config import settings


def fetch_url(url: str) -> str | None:
    headers = {"User-Agent": settings.default_user_agent}
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds, headers=headers, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text
    except httpx.HTTPError:
        return None

