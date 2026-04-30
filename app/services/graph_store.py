from pathlib import Path

from app.core.config import settings


def initialize_graph() -> object | None:
    try:
        import kuzu
    except ImportError:
        return None

    Path(settings.kuzu_path).mkdir(parents=True, exist_ok=True)
    db = kuzu.Database(settings.kuzu_path)
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE IF NOT EXISTS Entity(name STRING, entity_type STRING, description STRING, PRIMARY KEY(name))")
    conn.execute("CREATE REL TABLE IF NOT EXISTS Related(FROM Entity TO Entity, relation_type STRING, evidence STRING, confidence DOUBLE)")
    return conn


def upsert_graph(entities: list[dict[str, object]], relations: list[dict[str, object]]) -> None:
    conn = initialize_graph()
    if conn is None:
        return

    for entity in entities:
        conn.execute(
            """
            MERGE (e:Entity {name: $name})
            SET e.entity_type = $entity_type, e.description = $description
            """,
            {
                "name": str(entity["name"]),
                "entity_type": str(entity["entity_type"]),
                "description": str(entity.get("description", "")),
            },
        )

    for relation in relations:
        conn.execute(
            """
            MATCH (a:Entity {name: $source_entity}), (b:Entity {name: $target_entity})
            CREATE (a)-[:Related {relation_type: $relation_type, evidence: $evidence, confidence: $confidence}]->(b)
            """,
            {
                "source_entity": str(relation["source_entity"]),
                "target_entity": str(relation["target_entity"]),
                "relation_type": str(relation["relation_type"]),
                "evidence": str(relation.get("evidence", "")),
                "confidence": float(relation.get("confidence", 0.0)),
            },
        )


def query_graph(query: str, limit: int = 5) -> list[dict[str, object]]:
    conn = initialize_graph()
    if conn is None:
        return []

    escaped = query.replace("'", "''")
    result = conn.execute(
        f"""
        MATCH (a:Entity)-[r:Related]->(b:Entity)
        WHERE lower(a.name) CONTAINS lower('{escaped}')
           OR lower(b.name) CONTAINS lower('{escaped}')
           OR lower(r.relation_type) CONTAINS lower('{escaped}')
        RETURN a.name, r.relation_type, b.name, r.confidence
        LIMIT {int(limit)}
        """
    )
    hits: list[dict[str, object]] = []
    while result.has_next():
        row = result.get_next()
        hits.append(
            {
                "source_entity": row[0],
                "relation_type": row[1],
                "target_entity": row[2],
                "confidence": row[3],
            }
        )
    return hits
