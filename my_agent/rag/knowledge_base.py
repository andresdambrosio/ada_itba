"""Motor RAG local usando ChromaDB y Google Embeddings."""

import os
import re
from pathlib import Path

import chromadb
from google import genai
from google.genai import types as genai_types

_DOCUMENTS_DIR = Path(__file__).parent / "documents"
_DB_DIR = Path(__file__).parent / "chroma_db"
_COLLECTION_NAME = "itba_knowledge"
_EMBED_MODEL = "gemini-embedding-001"
_CHUNK_SIZE = 400   # palabras por chunk
_CHUNK_OVERLAP = 50


def _get_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(_DB_DIR))


def _get_genai_client() -> genai.Client:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GOOGLE_API_KEY no está configurada en el entorno.")
    return genai.Client(api_key=api_key)


def _embed(texts: list[str]) -> list[list[float]]:
    """Genera embeddings con el modelo de Google."""
    client = _get_genai_client()
    result = client.models.embed_content(
        model=_EMBED_MODEL,
        contents=texts,
        config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
    )
    return [e.values for e in result.embeddings]


def _chunk_text(text: str, source: str) -> list[dict]:
    """Divide el texto en chunks con overlap y agrega metadata."""
    words = text.split()
    chunks = []
    step = _CHUNK_SIZE - _CHUNK_OVERLAP
    for i in range(0, len(words), step):
        chunk_words = words[i : i + _CHUNK_SIZE]
        chunk_text = " ".join(chunk_words)
        # Extraer título del primer encabezado markdown si existe
        title_match = re.search(r"^#+\s+(.+)$", chunk_text, re.MULTILINE)
        title = title_match.group(1) if title_match else source
        chunks.append({"text": chunk_text, "source": source, "title": title})
    return chunks


def build_index() -> int:
    """Indexa todos los documentos de la carpeta documents/. Retorna cantidad de chunks indexados."""

    client = _get_client()

    # Borra y recrea la colección para re-indexar limpio
    try:
        client.delete_collection(_COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    all_chunks: list[dict] = []
    for doc_path in sorted(_DOCUMENTS_DIR.glob("*.md")):
        text = doc_path.read_text(encoding="utf-8")
        chunks = _chunk_text(text, source=doc_path.stem)
        all_chunks.extend(chunks)

    if not all_chunks:
        return 0

    texts = [c["text"] for c in all_chunks]
    embeddings = _embed(texts)

    collection.add(
        ids=[f"chunk_{i}" for i in range(len(all_chunks))],
        embeddings=embeddings,
        documents=texts,
        metadatas=[{"source": c["source"], "title": c["title"]} for c in all_chunks],
    )

    return len(all_chunks)


def search(query: str, n_results: int = 3) -> list[dict]:
    """Busca chunks relevantes para una query. Retorna lista de {text, source, score}."""
    chroma_client = _get_client()
    genai_client = _get_genai_client()

    try:
        collection = chroma_client.get_collection(_COLLECTION_NAME)
    except Exception:
        build_index()
        collection = chroma_client.get_collection(_COLLECTION_NAME)

    query_embedding = genai_client.models.embed_content(
        model=_EMBED_MODEL,
        contents=query,
        config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    ).embeddings[0].values

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append(
            {
                "text": doc,
                "source": meta.get("source", ""),
                "title": meta.get("title", ""),
                "relevance_score": round(1 - dist, 3),  # cosine distance → similarity
            }
        )
    return output
