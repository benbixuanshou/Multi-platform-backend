"""Milvus Collection creation script.

Run once before starting the app:
    python backend/migrations/002_milvus_collections.py

Requires: pymilvus, running Milvus instance (from docker-compose).
"""

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

MILVUS_HOST = "localhost"
MILVUS_PORT = 19530
DIM = 1024  # bge-large-zh outputs 1024-dimensional vectors


def create_collections():
    connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)

    # ---- Collection 1: comment_embeddings ----
    if not utility.has_collection("comment_embeddings"):
        fields = [
            FieldSchema(name="comment_id", dtype=DataType.VARCHAR, max_length=36, is_primary=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
            FieldSchema(name="platform", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="post_id", dtype=DataType.VARCHAR, max_length=36),
            FieldSchema(name="status", dtype=DataType.VARCHAR, max_length=32),
        ]
        schema = CollectionSchema(fields, description="Comment semantic embeddings")
        col = Collection("comment_embeddings", schema)
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        col.create_index("embedding", index_params)
        col.load()
        print("[OK] comment_embeddings created")
    else:
        print("[SKIP] comment_embeddings already exists")

    # ---- Collection 2: edit_log_embeddings ----
    if not utility.has_collection("edit_log_embeddings"):
        fields = [
            FieldSchema(name="edit_log_id", dtype=DataType.VARCHAR, max_length=36, is_primary=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
            FieldSchema(name="intent", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="created_at", dtype=DataType.INT64),
        ]
        schema = CollectionSchema(fields, description="Reply edit log semantic embeddings")
        col = Collection("edit_log_embeddings", schema)
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        col.create_index("embedding", index_params)
        col.load()
        print("[OK] edit_log_embeddings created")
    else:
        print("[SKIP] edit_log_embeddings already exists")

    # ---- Collection 3: user_identity_embeddings (reserved) ----
    if not utility.has_collection("user_identity_embeddings"):
        fields = [
            FieldSchema(name="platform_user_id", dtype=DataType.VARCHAR, max_length=128, is_primary=True),
            FieldSchema(name="platform", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
        ]
        schema = CollectionSchema(fields, description="Cross-platform user identity (reserved)")
        col = Collection("user_identity_embeddings", schema)
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        col.create_index("embedding", index_params)
        col.load()
        print("[OK] user_identity_embeddings created (reserved)")
    else:
        print("[SKIP] user_identity_embeddings already exists")

    connections.disconnect("default")
    print("Done.")


if __name__ == "__main__":
    create_collections()
