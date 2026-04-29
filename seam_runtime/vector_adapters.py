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

    def stale_records(self, records: list[MIRLRecord]) -> list[dict[str, object]]:
        return self.index.stale_records(records)


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
                        source_hash text not null default '',
                        embedding vector not null,
                        updated_at text not null
                    )
                    """
                )
                cursor.execute(
                    """
                    select column_name
                    from information_schema.columns
                    where table_name = %s and column_name = 'source_hash'
                    """,
                    (self.table_name,),
                )
                if cursor.fetchone() is None:
                    cursor.execute(f"alter table {self.table_name} add column source_hash text not null default ''")
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
                    source_hash = _hash_text(source_text)
                    cursor.execute(
                        f"select source_hash, dimension from {self.table_name} where record_id = %s and model_name = %s",
                        (record.id, self.model.name),
                    )
                    current = cursor.fetchone()
                    if current and current[0] == source_hash and int(current[1]) == int(self.model.dimension):
                        continue
                    vector = self.model.embed(source_text)
                    cursor.execute(
                        f"""
                        insert into {self.table_name} (record_id, model_name, dimension, source_text, source_hash, embedding, updated_at)
                        values (%s, %s, %s, %s, %s, %s::vector, %s)
                        on conflict (record_id) do update
                        set model_name = excluded.model_name,
                            dimension = excluded.dimension,
                            source_text = excluded.source_text,
                            source_hash = excluded.source_hash,
                            embedding = excluded.embedding,
                            updated_at = excluded.updated_at
                        """,
                        (record.id, self.model.name, len(vector), source_text, source_hash, _vector_literal(vector), record.updated_at),
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

    def stale_records(self, records: list[MIRLRecord]) -> list[dict[str, object]]:
        self.ensure_schema()
        stale: list[dict[str, object]] = []
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for record in records:
                    if record.kind not in INDEXABLE_KINDS:
                        continue
                    source_text = SQLiteVectorIndex.render_record_text(record)
                    source_hash = _hash_text(source_text)
                    cursor.execute(
                        f"select source_hash, dimension from {self.table_name} where record_id = %s and model_name = %s",
                        (record.id, self.model.name),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        stale.append({"record_id": record.id, "reason": "missing"})
                    elif row[0] != source_hash:
                        stale.append({"record_id": record.id, "reason": "source_changed"})
                    elif int(row[1]) != int(self.model.dimension):
                        stale.append({"record_id": record.id, "reason": "dimension_changed"})
        return stale


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(name):
        raise ValueError(f"Unsafe SQL identifier: {name}")
    return name


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in vector) + "]"


def _hash_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()
