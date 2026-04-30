from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.models.domain import ExtractedEntity, ExtractedRelation, IntelligenceRun, WebDocument
from app.services.content_extraction import extract_web_document
from app.services.gemini_extraction import extract_entities_and_relations
from app.services.graph_store import query_graph, upsert_graph
from app.services.vector_store import query_documents, upsert_documents
from app.services.web_search import discover_web_results


def run_intelligence_capture(db: Session, niche: str, query: str, max_results: int) -> IntelligenceRun:
    run = IntelligenceRun(niche=niche.strip(), query=query.strip(), status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    search_results = discover_web_results(query, max_results=max_results)
    run.source_count = len(search_results)
    db.commit()

    collected_docs: list[WebDocument] = []
    collected_entities: list[ExtractedEntity] = []
    collected_relations: list[ExtractedRelation] = []
    vector_payloads: list[dict[str, object]] = []
    graph_entities: list[dict[str, object]] = []
    graph_relations: list[dict[str, object]] = []
    summaries: list[str] = []

    for item in search_results:
        document = extract_web_document(item.url, title_hint=item.title, source_name=urlparse(item.url).netloc)
        if document is None or not document.text.strip():
            continue

        stored_doc = WebDocument(
            run_id=run.id,
            title=document.title,
            url=document.url,
            source_name=document.source_name,
            published_at=document.published_at,
            content_hash=document.content_hash,
            summary_text=document.summary,
            raw_text=document.text,
        )
        db.add(stored_doc)
        db.flush()
        collected_docs.append(stored_doc)

        extraction = extract_entities_and_relations(niche, document.title, document.url, document.text)
        summaries.append(extraction.summary)
        vector_payloads.append(
            {
                "id": f"run-{run.id}-doc-{stored_doc.id}",
                "text": document.text[:6000],
                "metadata": {
                    "run_id": run.id,
                    "document_id": stored_doc.id,
                    "url": document.url,
                    "title": document.title,
                    "niche": niche,
                },
            }
        )

        for entity in extraction.entities:
            stored_entity = ExtractedEntity(
                run_id=run.id,
                document_id=stored_doc.id,
                name=entity.name,
                entity_type=entity.entity_type,
                description=entity.description,
                metadata_json=None,
            )
            db.add(stored_entity)
            collected_entities.append(stored_entity)
            graph_entities.append(
                {
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "description": entity.description,
                }
            )

        for relation in extraction.relations:
            stored_relation = ExtractedRelation(
                run_id=run.id,
                document_id=stored_doc.id,
                source_entity=relation.source_entity,
                target_entity=relation.target_entity,
                relation_type=relation.relation_type,
                evidence=relation.evidence,
                confidence=relation.confidence,
            )
            db.add(stored_relation)
            collected_relations.append(stored_relation)
            graph_relations.append(
                {
                    "source_entity": relation.source_entity,
                    "target_entity": relation.target_entity,
                    "relation_type": relation.relation_type,
                    "evidence": relation.evidence,
                    "confidence": relation.confidence,
                }
            )

    upsert_documents(vector_payloads)
    upsert_graph(graph_entities, graph_relations)

    run.document_count = len(collected_docs)
    run.entity_count = len(collected_entities)
    run.relation_count = len(collected_relations)
    run.summary = _build_run_summary(niche, summaries, collected_entities, collected_relations)
    run.status = "completed"
    run.finished_at = datetime.utcnow()
    db.commit()

    return get_intelligence_run(db, run.id) or run


def list_intelligence_runs(db: Session) -> list[IntelligenceRun]:
    return db.scalars(
        select(IntelligenceRun)
        .options(
            selectinload(IntelligenceRun.documents),
            selectinload(IntelligenceRun.entities),
            selectinload(IntelligenceRun.relations),
        )
        .order_by(desc(IntelligenceRun.created_at))
    ).all()


def get_intelligence_run(db: Session, run_id: int) -> IntelligenceRun | None:
    return db.scalars(
        select(IntelligenceRun)
        .where(IntelligenceRun.id == run_id)
        .options(
            selectinload(IntelligenceRun.documents),
            selectinload(IntelligenceRun.entities),
            selectinload(IntelligenceRun.relations),
        )
    ).first()


def answer_intelligence_query(query: str, limit: int = 5) -> dict[str, object]:
    vector_hits = query_documents(query, limit=limit)
    graph_hits = query_graph(query, limit=limit)
    answer = _compose_query_answer(query, vector_hits, graph_hits)
    return {
        "answer": answer,
        "vector_hits": vector_hits,
        "graph_hits": graph_hits,
    }


def _build_run_summary(
    niche: str,
    summaries: list[str],
    entities: list[ExtractedEntity],
    relations: list[ExtractedRelation],
) -> str:
    entity_names = ", ".join(sorted({entity.name for entity in entities})[:8]) or "no major entities"
    relation_names = ", ".join(sorted({relation.relation_type for relation in relations})[:6]) or "no clear relationships"
    lead = summaries[0] if summaries else f"No usable documents were captured for {niche}."
    return (
        f"Niche: {niche}. "
        f"Lead finding: {lead} "
        f"Key entities: {entity_names}. "
        f"Observed relationship types: {relation_names}."
    )


def _compose_query_answer(
    query: str, vector_hits: list[dict[str, object]], graph_hits: list[dict[str, object]]
) -> str:
    if not vector_hits and not graph_hits:
        return f"No vector or graph matches are available yet for: {query}"

    lines = [f"Query: {query}"]
    if vector_hits:
        lines.append("Vector retrieval surfaced these documents:")
        for hit in vector_hits[:3]:
            metadata = hit.get("metadata") or {}
            lines.append(f"- {metadata.get('title', 'Untitled')} | {metadata.get('url', 'n/a')}")
    if graph_hits:
        lines.append("Graph retrieval surfaced these relationships:")
        for hit in graph_hits[:3]:
            lines.append(
                f"- {hit.get('source_entity')} -> {hit.get('relation_type')} -> {hit.get('target_entity')}"
            )
    return "\n".join(lines)
