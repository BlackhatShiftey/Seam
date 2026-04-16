from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .mirl import IRBatch, MIRLRecord, Pack, PersistReport, RecordKind, TraceGraph


class SQLiteStore:
    def __init__(self, path: str | Path = "seam.db") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                create table if not exists raw_docs (
                    id text primary key,
                    ns text not null,
                    scope text not null,
                    source_ref text,
                    content text not null,
                    created_at text not null
                );
                create table if not exists raw_spans (
                    id text primary key,
                    raw_id text not null,
                    start integer not null,
                    end integer not null,
                    span_text text,
                    created_at text not null
                );
                create table if not exists ir_records (
                    id text primary key,
                    kind text not null,
                    ns text not null,
                    scope text not null,
                    status text not null,
                    conf real not null,
                    t0 text,
                    t1 text,
                    created_at text not null,
                    updated_at text not null,
                    payload_json text not null
                );
                create table if not exists ir_edges (
                    id integer primary key autoincrement,
                    src_id text not null,
                    edge_type text not null,
                    dst_id text not null
                );
                create table if not exists symbol_table (
                    id text primary key,
                    ns text not null,
                    symbol text not null,
                    expansion text not null,
                    payload_json text not null
                );
                create table if not exists pack_store (
                    id text primary key,
                    mode text not null,
                    lens text not null,
                    refs_json text not null,
                    payload_json text not null,
                    created_at text not null
                );
                create table if not exists prov_log (
                    id text primary key,
                    entity text,
                    activity text,
                    agent text,
                    payload_json text not null
                );
                create table if not exists vector_index (
                    record_id text not null,
                    model_name text not null,
                    dimension integer not null,
                    source_text text not null,
                    vector_json text not null,
                    updated_at text not null,
                    primary key (record_id, model_name)
                );
                create index if not exists idx_ir_records_kind on ir_records (kind);
                create index if not exists idx_ir_records_ns_scope on ir_records (ns, scope);
                create index if not exists idx_ir_edges_src on ir_edges (src_id);
                create index if not exists idx_ir_edges_dst on ir_edges (dst_id);
                """
            )
            connection.commit()

    def persist_ir(self, batch: IRBatch) -> PersistReport:
        with closing(self._connect()) as connection:
            for record in batch.records:
                payload = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
                connection.execute(
                    """
                    insert or replace into ir_records
                    (id, kind, ns, scope, status, conf, t0, t1, created_at, updated_at, payload_json)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (record.id, record.kind.value, record.ns, record.scope, record.status.value, record.conf, record.t0, record.t1, record.created_at, record.updated_at, payload),
                )
                self._persist_specialized(connection, record)
                self._persist_edges(connection, record)
            connection.commit()
        return PersistReport(stored_ids=[record.id for record in batch.records], store_path=self.path)

    def _persist_specialized(self, connection: sqlite3.Connection, record: MIRLRecord) -> None:
        attrs = record.attrs
        if record.kind == RecordKind.RAW:
            connection.execute(
                "insert or replace into raw_docs (id, ns, scope, source_ref, content, created_at) values (?, ?, ?, ?, ?, ?)",
                (record.id, record.ns, record.scope, attrs.get("source_ref"), attrs.get("content", ""), record.created_at),
            )
        elif record.kind == RecordKind.SPAN:
            connection.execute(
                "insert or replace into raw_spans (id, raw_id, start, end, span_text, created_at) values (?, ?, ?, ?, ?, ?)",
                (record.id, attrs.get("raw_id"), int(attrs.get("start", 0)), int(attrs.get("end", 0)), attrs.get("text"), record.created_at),
            )
        elif record.kind == RecordKind.SYM:
            connection.execute(
                "insert or replace into symbol_table (id, ns, symbol, expansion, payload_json) values (?, ?, ?, ?, ?)",
                (record.id, record.ns, attrs.get("symbol"), attrs.get("expansion"), json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))),
            )
        elif record.kind == RecordKind.PACK:
            connection.execute(
                "insert or replace into pack_store (id, mode, lens, refs_json, payload_json, created_at) values (?, ?, ?, ?, ?, ?)",
                (record.id, attrs.get("mode"), attrs.get("lens", "general"), json.dumps(attrs.get("refs", [])), json.dumps(attrs.get("payload", {}), sort_keys=True, separators=(",", ":")), record.created_at),
            )
        elif record.kind == RecordKind.PROV:
            connection.execute(
                "insert or replace into prov_log (id, entity, activity, agent, payload_json) values (?, ?, ?, ?, ?)",
                (record.id, attrs.get("entity"), attrs.get("activity"), attrs.get("agent"), json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))),
            )

    def _persist_edges(self, connection: sqlite3.Connection, record: MIRLRecord) -> None:
        attrs = record.attrs
        edges: list[tuple[str, str, str]] = []
        if record.kind == RecordKind.REL:
            edges.append((str(attrs.get("src")), str(attrs.get("predicate")), str(attrs.get("dst"))))
        elif record.kind == RecordKind.CLM:
            subject = str(attrs.get("subject"))
            obj = attrs.get("object")
            if isinstance(obj, str) and ":" in obj:
                edges.append((subject, str(attrs.get("predicate")), obj))
        for prov in record.prov:
            edges.append((record.id, "prov", prov))
        for evidence in record.evidence:
            edges.append((record.id, "evidence", evidence))
        for src_id, edge_type, dst_id in edges:
            connection.execute("insert into ir_edges (src_id, edge_type, dst_id) values (?, ?, ?)", (src_id, edge_type, dst_id))

    def load_ir(self, ids: list[str] | None = None, ns: str | None = None, scope: str | None = None) -> IRBatch:
        query = "select payload_json from ir_records where 1=1"
        params: list[object] = []
        if ids:
            query += f" and id in ({','.join('?' for _ in ids)})"
            params.extend(ids)
        if ns:
            query += " and ns = ?"
            params.append(ns)
        if scope:
            query += " and scope = ?"
            params.append(scope)
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        return IRBatch([MIRLRecord.from_dict(json.loads(row["payload_json"])) for row in rows])

    def read_pack(self, pack_id: str) -> Pack:
        with closing(self._connect()) as connection:
            row = connection.execute("select * from pack_store where id = ?", (pack_id,)).fetchone()
        if row is None:
            raise KeyError(pack_id)
        return Pack(pack_id=row["id"], mode=row["mode"], lens=row["lens"], refs=json.loads(row["refs_json"]), payload=json.loads(row["payload_json"]), budget=0, reversible=row["mode"] == "exact", token_cost=0, created_at=row["created_at"])

    def trace(self, root_id: str) -> TraceGraph:
        batch = self.load_ir()
        records = batch.by_id()
        if root_id not in records:
            raise KeyError(root_id)
        seen = {root_id}
        queue = [root_id]
        edges: list[dict[str, str]] = []
        while queue:
            current = queue.pop(0)
            record = records[current]
            refs = list(record.prov) + list(record.evidence)
            for key in ("src", "dst", "target", "raw_id", "subject"):
                value = record.attrs.get(key)
                if isinstance(value, str) and value in records:
                    refs.append(value)
            obj = record.attrs.get("object")
            if isinstance(obj, str) and obj in records:
                refs.append(obj)
            for dst in refs:
                edges.append({"src": current, "type": "trace", "dst": dst})
                if dst in records and dst not in seen:
                    seen.add(dst)
                    queue.append(dst)
        return TraceGraph(root_id=root_id, nodes=[records[node_id] for node_id in seen], edges=edges)
