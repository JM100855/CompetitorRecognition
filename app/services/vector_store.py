from pathlib import Path

from app.core.config import settings


def upsert_documents(documents: list[dict[str, object]]) -> None:
    if not documents:
        return
    try:
        import chromadb
    except ImportError:
        return

    Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=settings.chroma_path)
    collection = client.get_or_create_collection(name=settings.chroma_collection_name)
    ids = [str(item["id"]) for item in documents]
    texts = [str(item["text"]) for item in documents]
    metadatas = [dict(item["metadata"]) for item in documents]
    collection.upsert(ids=ids, documents=texts, metadatas=metadatas)


def query_documents(query: str, limit: int = 5) -> list[dict[str, object]]:
    try:
        import chromadb
    except ImportError:
        return []

    client = chromadb.PersistentClient(path=settings.chroma_path)
    collection = client.get_or_create_collection(name=settings.chroma_collection_name)
    result = collection.query(query_texts=[query], n_results=limit)
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    hits: list[dict[str, object]] = []
    for document, metadata, distance in zip(documents, metadatas, distances):
        hits.append(
            {
                "document": document,
                "metadata": metadata,
                "distance": distance,
            }
        )
    return hits
