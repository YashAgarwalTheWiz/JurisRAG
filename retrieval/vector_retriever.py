import time
import cohere
from qdrant_client import QdrantClient
from config import COHERE_API_KEY, QDRANT_API_KEY, QDRANT_URL, COLLECTION_NAME

co = cohere.Client(COHERE_API_KEY)
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

RERANK_CANDIDATE_POOL = 20
RERANK_CHARS_PER_DOC = 2000


def _call_with_retry(fn, max_retries=3, base_delay=15):
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            is_rate_limit = "429" in str(e) or getattr(e, "status_code", None) == 429
            if not is_rate_limit or attempt == max_retries - 1:
                raise
            wait = base_delay * (attempt + 1)
            print(f"[vector_search] Cohere rate limit hit, waiting {wait}s before retry...")
            time.sleep(wait)


def vector_search(query, top_k=5):
    response = _call_with_retry(lambda: co.embed(
        texts=[query], model='embed-english-v3.0', input_type='search_query'
    ))
    query_vector = response.embeddings[0]

    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=max(top_k, RERANK_CANDIDATE_POOL)
    )
    candidates = [hit.payload for hit in results.points]

    if not candidates:
        return []

    reranked = _call_with_retry(lambda: co.rerank(
        model="rerank-english-v3.0",
        query=query,
        documents=[c["text"][:RERANK_CHARS_PER_DOC] for c in candidates],
        top_n=top_k,
    ))

    return [candidates[result.index] for result in reranked.results]