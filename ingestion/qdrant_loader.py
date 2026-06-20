from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
import cohere
import uuid
from config import QDRANT_URL, QDRANT_API_KEY, COLLECTION_NAME, COHERE_API_KEY

qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
co = cohere.Client(COHERE_API_KEY)

if not qdrant.collection_exists(COLLECTION_NAME):
    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
    )


def load_to_qdrant(case_id, text):
    response = co.embed(texts=[text], model="embed-english-v3.0", input_type="search_document")
    vector = response.embeddings[0]

    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, case_id))
    point = PointStruct(
        id=point_id,
        vector=vector,
        payload={'case_id': case_id, 'text': text}
    )
    qdrant.upsert(collection_name=COLLECTION_NAME, points=[point])