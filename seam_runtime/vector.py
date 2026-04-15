from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from typing import Iterable

from .mirl import MIRLRecord, RecordKind, iter_textual_fields
from .models import EmbeddingModel, cosine


INDEXABLE_KINDS = {RecordKind.CLM, RecordKind.STA, RecordKind.EVT, RecordKind.REL}


class SQLiteVectorIndex:
    def __init__(self, path: str, model: EmbeddingModel) -> None:
        self.path = path
        self.model = model

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def ensure_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                create table if not exists vector_index (
                    record_id text not null,
                    model_name text not null,
                    dimension integer not null,
                    source_text text not null,
                    vector_json text not null,
                    updated_at text not null,
                    primary key (record_id, model_name)
                )
                """
            )
            connection.commit()

    def index_records(self, records: Iterable[MIRLRecord]) -> None:
        self.ensure_schema()
        with closing(self._connect()) as connection:
            for record in records:
                if record.kind not in INDEXABLE_KINDS:
                    continue
                source_text = self.render_record_text(record)
                vector = self.model.embed(source_text)
                connection.execute(
                    """
                    insert or replace into vector_index (record_id, model_name, dimension, source_text, vector_json, updated_at)
                    values (?, ?, ?, ?, ?, ?)
                    """,
                    (record.id, self.model.name, len(vector), source_text, json.dumps(vector), record.updated_at),
                )
            connection.commit()

    def search(self, query: str, limit: int = 10) -> dict[str, float]:
        self.ensure_schema()
        query_vector = self.model.embed(query)
        scores: dict[str, float] = {}
        with closing(self._connect()) as connection:
            rows = connection.execute("select record_id, vector_json from vector_index where model_name = ?", (self.model.name,)).fetchall()
        for row in rows:
            score = cosine(query_vector, json.loads(row["vector_json"]))
            if score > 0:
                scores[row["record_id"]] = score
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
        return dict(ordered)

    @staticmethod
    def render_record_text(record: MIRLRecord) -> str:
        parts = [record.kind.value]
        parts.extend(iter_textual_fields(record))
        return " ".join(part for part in parts if part)
