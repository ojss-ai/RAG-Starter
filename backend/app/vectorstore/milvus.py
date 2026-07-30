import asyncio

from app.vectorstore import VectorHit, VectorItem

_HNSW_PARAMS = {"M": 16, "efConstruction": 200}  # plan §3 / SRS NFR-1


class MilvusVectorStore:
    """Milvus gateway. pymilvus is imported lazily so environments without it (unit tests,
    memory backend) never pay for or require the dependency. All pymilvus calls are sync —
    they run in a worker thread to keep the event loop free."""

    def __init__(self, uri: str, collection: str, dim: int):
        self._uri = uri
        self._collection = collection
        self._dim = dim
        self._client = None

    def _get_client(self):
        if self._client is None:
            from pymilvus import MilvusClient  # lazy: see class docstring
            self._client = MilvusClient(uri=self._uri)
        return self._client

    async def ensure_ready(self) -> None:
        def _setup():
            from pymilvus import DataType
            client = self._get_client()
            if client.has_collection(self._collection):
                return
            schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
            schema.add_field("pk", DataType.INT64, is_primary=True)
            schema.add_field("chunk_id", DataType.VARCHAR, max_length=64)
            schema.add_field("document_id", DataType.VARCHAR, max_length=64)
            schema.add_field("partition_key", DataType.VARCHAR, max_length=128,
                             is_partition_key=True)  # plan §4: partitioned collections
            schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=self._dim)
            index_params = client.prepare_index_params()
            index_params.add_index(field_name="embedding", index_type="HNSW",
                                   metric_type="COSINE", params=_HNSW_PARAMS)
            client.create_collection(self._collection, schema=schema,
                                     index_params=index_params)
        await asyncio.to_thread(_setup)

    async def upsert(self, items: list[VectorItem]) -> None:
        rows = [{"chunk_id": it.chunk_id, "document_id": it.document_id,
                 "partition_key": it.partition_key, "embedding": it.embedding}
                for it in items]

        def _insert():
            self._get_client().insert(self._collection, rows)
        await asyncio.to_thread(_insert)

    async def delete_document(self, document_id: str) -> None:
        def _delete():
            self._get_client().delete(self._collection,
                                      filter=f'document_id == "{document_id}"')
        await asyncio.to_thread(_delete)

    async def search(self, vector: list[float], top_k: int,
                     partition_key: str | None = None) -> list[VectorHit]:
        def _search():
            kwargs = dict(collection_name=self._collection, data=[vector], limit=top_k,
                          output_fields=["chunk_id", "document_id"])
            if partition_key is not None:
                kwargs["filter"] = f'partition_key == "{partition_key}"'
            return self._get_client().search(**kwargs)
        results = await asyncio.to_thread(_search)
        hits = results[0] if results else []
        return [VectorHit(chunk_id=h["entity"]["chunk_id"],
                          document_id=h["entity"]["document_id"],
                          score=float(h["distance"])) for h in hits]

    async def stats(self) -> dict:
        def _stats():
            client = self._get_client()
            res = client.get_collection_stats(self._collection)
            return int(res.get("row_count", 0))
        return {"backend": "milvus", "vectors": await asyncio.to_thread(_stats)}
