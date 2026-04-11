from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from .mirl import MIRLRecord
from .models import EmbeddingModel
from .vector import INDEXABLE_KINDS, SQLiteVectorIndex


class VectorAdapter(Protocol):
    name: str

    def index_records(self, records: list[MIRLRecord]) -> None:
        ...

    def search(self, query: str, limit: int = 10) -> dict[str, float]:
        ...


@dataclass
class SQLiteVectorAdapter:
    path: str
    model: EmbeddingModel
    name: str = "sqlite-vector"

    def __post_init__(self) -> None:
        self.index = SQLiteVectorIndex(self.path, self.model)
        self.index.ensure_schema()

    def index_records(self, records: list[MIRLRecord]) -> None:
        self.index.index_records(records)

    def search(self, query: str, limit: int = 10) -> dict[str, float]:
        return self.index.search(query, limit=limit)


@dataclass
class PgVectorAdapter:
    dsn: str
    model: EmbeddingModel
    table_name: str = "seam_vector_index"
    name: str = "pgvector"

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required for PgVectorAdapter") from exc
        return psycopg.connect(self.dsn)

    def ensure_schema(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("create extension if not exists vector")
                cursor.execute(
                    f"""
                    create table if not exists {self.table_name} (
                        record_id text primary key,
                        model_name text not null,
                        source_text text not null,
                        vector_json jsonb not null
                    )
                    """
                )
            connection.commit()

    def index_records(self, records: list[MIRLRecord]) -> None:
        self.ensure_schema()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for record in records:
                    if record.kind not in INDEXABLE_KINDS:
                        continue
                    source_text = " ".join(part for part in record.attrs.values() if isinstance(part, str))
                    vector = self.model.embed(source_text)
                    cursor.execute(
                        f"""
                        insert into {self.table_name} (record_id, model_name, source_text, vector_json)
                        values (%s, %s, %s, %s)
                        on conflict (record_id) do update
                        set model_name = excluded.model_name,
                            source_text = excluded.source_text,
                            vector_json = excluded.vector_json
                        """,
                        (record.id, self.model.name, source_text, json.dumps(vector)),
                    )
            connection.commit()

    def search(self, query: str, limit: int = 10) -> dict[str, float]:
        self.ensure_schema()
        query_vector = self.model.embed(query)
        scores: dict[str, float] = {}
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"select record_id, vector_json from {self.table_name} where model_name = %s", (self.model.name,))
                rows = cursor.fetchall()
        for record_id, vector_json in rows:
            vector = json.loads(vector_json) if isinstance(vector_json, str) else vector_json
            score = sum(a * b for a, b in zip(query_vector, vector, strict=False))
            if score > 0:
                scores[record_id] = score
        return dict(sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit])
