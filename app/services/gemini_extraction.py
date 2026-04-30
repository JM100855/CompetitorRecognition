import json
import re
from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class EntityRecord:
    name: str
    entity_type: str
    description: str


@dataclass(frozen=True)
class RelationRecord:
    source_entity: str
    target_entity: str
    relation_type: str
    evidence: str
    confidence: float


@dataclass(frozen=True)
class ExtractionResult:
    entities: list[EntityRecord]
    relations: list[RelationRecord]
    summary: str
    model_used: str


def extract_entities_and_relations(
    niche: str,
    title: str,
    url: str,
    text: str,
) -> ExtractionResult:
    if settings.gemini_api_key:
        try:
            return _extract_with_gemini(niche, title, url, text)
        except Exception:
            pass
    return _extract_with_heuristics(title, url, text)


def _extract_with_gemini(niche: str, title: str, url: str, text: str) -> ExtractionResult:
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_model)
    prompt = f"""
You are extracting structured competitive intelligence.
Return JSON only with keys: summary, entities, relations.

Entity schema:
- name
- entity_type
- description

Relation schema:
- source_entity
- target_entity
- relation_type
- evidence
- confidence

Niche: {niche}
Title: {title}
URL: {url}
Document:
\"\"\"
{text[:12000]}
\"\"\"
""".strip()
    response = model.generate_content(prompt)
    payload = _load_json_block(response.text)
    entities = [
        EntityRecord(
            name=str(item.get("name", "")).strip(),
            entity_type=str(item.get("entity_type", "unknown")).strip(),
            description=str(item.get("description", "")).strip(),
        )
        for item in payload.get("entities", [])
        if str(item.get("name", "")).strip()
    ]
    relations = [
        RelationRecord(
            source_entity=str(item.get("source_entity", "")).strip(),
            target_entity=str(item.get("target_entity", "")).strip(),
            relation_type=str(item.get("relation_type", "")).strip(),
            evidence=str(item.get("evidence", "")).strip(),
            confidence=float(item.get("confidence", 0.5)),
        )
        for item in payload.get("relations", [])
        if str(item.get("source_entity", "")).strip() and str(item.get("target_entity", "")).strip()
    ]
    return ExtractionResult(
        entities=entities,
        relations=relations,
        summary=str(payload.get("summary", "")).strip() or text[:300],
        model_used=settings.gemini_model,
    )


def _extract_with_heuristics(title: str, url: str, text: str) -> ExtractionResult:
    candidates = re.findall(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2}\b", text[:4000])
    seen: set[str] = set()
    entities: list[EntityRecord] = []
    for name in candidates:
        if name.lower() in seen or len(name) < 3:
            continue
        seen.add(name.lower())
        entity_type = "company" if any(word in name.lower() for word in ("inc", "corp", "labs", "ai")) else "topic"
        entities.append(EntityRecord(name=name, entity_type=entity_type, description=f"Mentioned in {title or url}"))
        if len(entities) >= 8:
            break

    relations: list[RelationRecord] = []
    for left, right in zip(entities, entities[1:]):
        relations.append(
            RelationRecord(
                source_entity=left.name,
                target_entity=right.name,
                relation_type="co-mentioned-with",
                evidence=text[:220],
                confidence=0.35,
            )
        )

    return ExtractionResult(
        entities=entities,
        relations=relations,
        summary=" ".join(text.split())[:300],
        model_used="heuristic-fallback",
    )


def _load_json_block(text: str) -> dict[str, object]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
