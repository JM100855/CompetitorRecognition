from bs4 import BeautifulSoup


def extract_page_document(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    text_chunks = [chunk.strip() for chunk in soup.stripped_strings]
    text = " ".join(text_chunks)
    summary = text[:600]
    return {
        "title": title,
        "summary_text": summary,
        "raw_text": text[:20000],
    }

