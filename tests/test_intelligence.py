from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.services.content_extraction import ExtractedDocument
from app.services.gemini_extraction import ExtractionResult
from app.services.gemini_extraction import EntityRecord
from app.services.gemini_extraction import RelationRecord
from app.services.intelligence import answer_intelligence_query, run_intelligence_capture


def _build_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_run_intelligence_capture_persists_documents_entities_and_relations(monkeypatch) -> None:
    db = _build_session()

    monkeypatch.setattr(
        "app.services.intelligence.discover_web_results",
        lambda query, max_results: [
            type("Result", (), {"title": "Acme raises funding", "url": "https://example.com/a", "snippet": "news"})()
        ],
    )
    monkeypatch.setattr(
        "app.services.intelligence.extract_web_document",
        lambda url, title_hint="", source_name=None: ExtractedDocument(
            title=title_hint or "Acme raises funding",
            url=url,
            text="Acme AI raised funding and partnered with Northwind Analytics.",
            summary="Acme AI raised funding and partnered with Northwind Analytics.",
            published_at=None,
            source_name="example.com",
            content_hash="hash-1",
        ),
    )
    monkeypatch.setattr(
        "app.services.intelligence.extract_entities_and_relations",
        lambda niche, title, url, text: ExtractionResult(
            entities=[
                EntityRecord(name="Acme AI", entity_type="company", description="Vendor"),
                EntityRecord(name="Northwind Analytics", entity_type="company", description="Partner"),
            ],
            relations=[
                RelationRecord(
                    source_entity="Acme AI",
                    target_entity="Northwind Analytics",
                    relation_type="partnered-with",
                    evidence="Acme AI partnered with Northwind Analytics.",
                    confidence=0.91,
                )
            ],
            summary="Acme AI raised funding and partnered with Northwind Analytics.",
            model_used="test-model",
        ),
    )
    monkeypatch.setattr("app.services.intelligence.upsert_documents", lambda documents: None)
    monkeypatch.setattr("app.services.intelligence.upsert_graph", lambda entities, relations: None)

    run = run_intelligence_capture(db, niche="AI sales", query="AI sales companies", max_results=5)

    assert run.status == "completed"
    assert run.source_count == 1
    assert run.document_count == 1
    assert run.entity_count == 2
    assert run.relation_count == 1
    assert "Acme AI" in (run.summary or "")


def test_answer_intelligence_query_uses_vector_and_graph_hits(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.intelligence.query_documents",
        lambda query, limit=5: [
            {
                "document": "Pricing page mentions enterprise package",
                "metadata": {"title": "Acme Pricing", "url": "https://example.com/pricing"},
                "distance": 0.12,
            }
        ],
    )
    monkeypatch.setattr(
        "app.services.intelligence.query_graph",
        lambda query, limit=5: [
            {
                "source_entity": "Acme AI",
                "relation_type": "competes-with",
                "target_entity": "Northwind Analytics",
                "confidence": 0.88,
            }
        ],
    )

    payload = answer_intelligence_query("enterprise pricing", limit=5)

    assert "Acme Pricing" in payload["answer"]
    assert "competes-with" in payload["answer"]
    assert payload["vector_hits"]
    assert payload["graph_hits"]
