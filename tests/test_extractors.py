from app.services.extractors import extract_page_document


def test_extract_page_document_returns_title_and_summary() -> None:
    html = "<html><head><title>Test</title></head><body><h1>Hello</h1><p>World</p></body></html>"
    document = extract_page_document(html)

    assert document["title"] == "Test"
    assert "Hello" in document["summary_text"]
