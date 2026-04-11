from __future__ import annotations

import re
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

    def __post_init__(self) -> None:
        self.table_name = _validate_identifier(self.table_name)

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
                        dimension integer not null,
                        source_text text not null,
                        embedding vector not null,
                        updated_at text not null
                    )
                    """
                )
                cursor.execute(f"create index if not exists {self.table_name}_model_name_idx on {self.table_name} (model_name)")
            connection.commit()

    def index_records(self, records: list[MIRLRecord]) -> None:
        self.ensure_schema()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for record in records:
                    if record.kind not in INDEXABLE_KINDS:
                        continue
                    source_text = SQLiteVectorIndex.render_record_text(record)
                    vector = self.model.embed(source_text)
                    cursor.execute(
                        f"""
                        insert into {self.table_name} (record_id, model_name, dimension, source_text, embedding, updated_at)
                        values (%s, %s, %s, %s, %s::vector, %s)
                        on conflict (record_id) do update
                        set model_name = excluded.model_name,
                            dimension = excluded.dimension,
                            source_text = excluded.source_text,
                            embedding = excluded.embedding,
                            updated_at = excluded.updated_at
                        """,
                        (record.id, self.model.name, len(vector), source_text, _vector_literal(vector), record.updated_at),
                    )
            connection.commit()

    def search(self, query: str, limit: int = 10) -> dict[str, float]:
        self.ensure_schema()
        query_vector = self.model.embed(query)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    select record_id, 1 - (embedding <=> %s::vector) as score
                    from {self.table_name}
                    where model_name = %s and dimension = %s
                    order by embedding <=> %s::vector
                    limit %s
                    """,
                    (_vector_literal(query_vector), self.model.name, len(query_vector), _vector_literal(query_vector), limit),
                )
                rows = cursor.fetchall()
        return {record_id: float(score) for record_id, score in rows if score is not None and float(score) > 0}


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(name):
        raise ValueError(f"Unsafe SQL identifier: {name}")
    return name


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in vector) + "]"
