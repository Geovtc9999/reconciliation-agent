"""Stockage objet MinIO — bucket « artefacts » (source de vérité des propositions)."""
from __future__ import annotations

import io
import json
from functools import lru_cache

from minio import Minio

from .config import settings


@lru_cache(maxsize=1)
def _client() -> Minio:
    return Minio(
        settings.s3_endpoint,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        secure=settings.s3_secure,
    )


def bucket_ok() -> bool:
    return _client().bucket_exists(settings.s3_bucket)


def _key(*parts: str) -> str:
    return settings.artefacts_prefix + "/".join(p.strip("/") for p in parts)


def put_json(rel_path: str, obj: dict) -> str:
    """Écrit un JSON dans artefacts/reconciliations/<rel_path>. Renvoie l'URI s3://."""
    data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    key = _key(rel_path)
    _client().put_object(
        settings.s3_bucket, key, io.BytesIO(data), length=len(data),
        content_type="application/json",
    )
    return f"s3://{settings.s3_bucket}/{key}"


def get_json(rel_path: str) -> dict | None:
    key = _key(rel_path)
    try:
        resp = _client().get_object(settings.s3_bucket, key)
        try:
            return json.loads(resp.read())
        finally:
            resp.close()
            resp.release_conn()
    except Exception:
        return None


def list_proposals() -> list[str]:
    """Liste les proposal_id présents sous le préfixe reconciliations/."""
    ids = set()
    prefix = settings.artefacts_prefix
    for obj in _client().list_objects(settings.s3_bucket, prefix=prefix, recursive=True):
        rest = obj.object_name[len(prefix):]
        if "/" in rest:
            ids.add(rest.split("/", 1)[0])
    return sorted(ids)
