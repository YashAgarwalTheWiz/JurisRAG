import cohere
from qdrant_client import QdrantClient
from config import COHERE_API_KEY, QDRANT_API_KEY, QDRANT_URL, COLLECTION_NAME

co = cohere.Client(COHERE_API_KEY)
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def vector_search(query, top_k=5):
    response = co.embed(texts=[query], model='embed-english-v3.0', input_type='search_query')
    query_vector = response.embeddings[0]

    # query_points replaces the deprecated search() method. Two changes:
    # the parameter is named `query`, not `query_vector`, and the return
    # value is a QueryResponse object — the list of hits is on `.points`,
    # not the object itself.
    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k
    )
    return [hit.payload for hit in results.points]