from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from .mirl import IRBatch, MIRLRecord, Pack, PersistReport, RecordKind, TraceGraph, utc_now


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
                create table if not exists document_status (
                    document_id text primary key,
                    ns text not null,
                    scope text not null,
                    source_ref text not null,
                    source_hash text not null,
                    byte_count integer not null,
                    chunk_count integer not null,
                    extraction_status text not null,
                    indexed_status text not null,
                    deleted_at text,
                    metadata_json text not null,
                    created_at text not null,
                    updated_at text not null
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
                create table if not exists machine_artifacts (
                    artifact_id text primary key,
                    source_type text not null,
                    source_id text not null,
                    codec text,
                    transform_chain text,
                    tokenizer text,
                    sha256_raw text,
                    sha256_machine text,
                    bytes_raw integer,
                    bytes_machine integer,
                    tokens_raw integer,
                    tokens_machine integer,
                    token_savings_ratio real,
                    roundtrip_ok integer not null,
                    metadata_json text not null,
                    artifact_json text not null,
                    machine_text text,
                    created_at text not null
                );
                create table if not exists benchmark_runs (
                    run_id text primary key,
                    requested_suite text,
                    executed_suites text not null,
                    status text not null,
                    bundle_hash text,
                    manifest_json text not null,
                    summary_json text not null,
                    report_json text not null,
                    created_at text not null
                );
                create table if not exists benchmark_cases (
                    run_id text not null,
                    case_id text not null,
                    family text not null,
                    status text not null,
                    case_hash text,
                    metrics_json text not null,
                    trace_json text not null,
                    case_json text not null,
                    primary key (run_id, case_id)
                );
                create table if not exists projection_index (
                    projection_id text primary key,
                    record_id text not null,
                    projection_kind text not null,
                    projection_text text not null,
                    tokenizer text,
                    token_count integer,
                    metadata_json text not null,
                    updated_at text not null
                );
                create index if not exists idx_ir_records_kind on ir_records (kind);
                create index if not exists idx_ir_records_ns_scope on ir_records (ns, scope);
                create index if not exists idx_document_status_source on document_status (source_ref);
                create index if not exists idx_document_status_hash on document_status (source_hash);
                create index if not exists idx_ir_edges_src on ir_edges (src_id);
                create index if not exists idx_ir_edges_dst on ir_edges (dst_id);
                create index if not exists idx_machine_artifacts_source on machine_artifacts (source_type, source_id);
                create index if not exists idx_benchmark_cases_family on benchmark_cases (family);
                create unique index if not exists idx_projection_record_kind on projection_index (record_id, projection_kind);
                """
            )
            connection.commit()

    def get_stats(self) -> dict[str, object]:
        with closing(self._connect()) as connection:
            total_records = connection.execute("select count(*) from ir_records").fetchone()[0]
            vector_entries = connection.execute("select count(*) from vector_index").fetchone()[0]
            pack_entries = connection.execute("select count(*) from pack_store").fetchone()[0]
            namespaces = connection.execute("select count(distinct ns) from ir_records").fetchone()[0]
            scopes = connection.execute("select count(distinct scope) from ir_records").fetchone()[0]
            benchmark_runs = connection.execute("select count(*) from benchmark_runs").fetchone()[0]
            machine_artifacts = connection.execute("select count(*) from machine_artifacts").fetchone()[0]
        return {
            "total_records": total_records,
            "vector_entries": vector_entries,
            "pack_entries": pack_entries,
            "namespaces": namespaces,
            "scopes": scopes,
            "benchmark_runs": benchmark_runs,
            "machine_artifacts": machine_artifacts,
        }

    def list_namespaces(self, limit: int = 100) -> list[str]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "select distinct ns from ir_records order by ns limit ?",
                (limit,),
            ).fetchall()
        return [row["ns"] for row in rows]

    def list_scopes(self, ns: str, limit: int = 100) -> list[str]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "select distinct scope from ir_records where ns = ? order by scope limit ?",
                (ns, limit),
            ).fetchall()
        return [row["scope"] for row in rows]

    def list_record_summaries(self, ns: str, scope: str, limit: int = 100) -> list[dict[str, object]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                select id, kind, status, updated_at
                from ir_records
                where ns = ? and scope = ?
                order by updated_at desc, id
                limit ?
                """,
                (ns, scope, limit),
            ).fetchall()
        return [dict(row) for row in rows]

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

    def upsert_document_status(
        self,
        *,
        document_id: str,
        ns: str,
        scope: str,
        source_ref: str,
        source_hash: str,
        byte_count: int,
        chunk_count: int,
        extraction_status: str,
        indexed_status: str,
        metadata: dict[str, object] | None = None,
        deleted_at: str | None = None,
    ) -> dict[str, object]:
        now = utc_now()
        with closing(self._connect()) as connection:
            existing = connection.execute("select created_at from document_status where document_id = ?", (document_id,)).fetchone()
            created_at = existing["created_at"] if existing else now
            connection.execute(
                """
                insert or replace into document_status
                (document_id, ns, scope, source_ref, source_hash, byte_count, chunk_count,
                 extraction_status, indexed_status, deleted_at, metadata_json, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    ns,
                    scope,
                    source_ref,
                    source_hash,
                    int(byte_count),
                    int(chunk_count),
                    extraction_status,
                    indexed_status,
                    deleted_at,
                    json.dumps(metadata or {}, sort_keys=True, separators=(",", ":")),
                    created_at,
                    now,
                ),
            )
            connection.commit()
        return self.read_document_status(document_id)

    def read_document_status(self, document_id: str) -> dict[str, object]:
        with closing(self._connect()) as connection:
            row = connection.execute("select * from document_status where document_id = ?", (document_id,)).fetchone()
        if row is None:
            raise KeyError(document_id)
        return _document_status_row(row)

    def list_document_status(self, limit: int = 20) -> list[dict[str, object]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "select * from document_status order by updated_at desc limit ?",
                (limit,),
            ).fetchall()
        return [_document_status_row(row) for row in rows]

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

    def write_machine_artifact(
        self,
        source_type: str,
        source_id: str,
        artifact: dict[str, object],
        roundtrip_ok: bool,
        metadata: dict[str, object] | None = None,
    ) -> str:
        artifact_id = f"mx:{uuid4().hex[:12]}"
        machine_text = str(artifact.get("machine_text", "") or "")
        machine_bytes = machine_text.encode("utf-8") if machine_text else b""
        with closing(self._connect()) as connection:
            connection.execute(
                """
                insert or replace into machine_artifacts
                (artifact_id, source_type, source_id, codec, transform_chain, tokenizer, sha256_raw, sha256_machine,
                 bytes_raw, bytes_machine, tokens_raw, tokens_machine, token_savings_ratio, roundtrip_ok,
                 metadata_json, artifact_json, machine_text, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    source_type,
                    source_id,
                    artifact.get("codec"),
                    artifact.get("transform"),
                    artifact.get("token_estimator"),
                    artifact.get("sha256"),
                    hashlib.sha256(machine_bytes).hexdigest() if machine_bytes else None,
                    artifact.get("original_bytes"),
                    artifact.get("machine_bytes"),
                    artifact.get("original_tokens"),
                    artifact.get("machine_tokens"),
                    artifact.get("token_savings_ratio"),
                    1 if roundtrip_ok else 0,
                    json.dumps(metadata or {}, sort_keys=True, separators=(",", ":")),
                    json.dumps(artifact, sort_keys=True, separators=(",", ":")),
                    machine_text or None,
                    utc_now(),
                ),
            )
            connection.commit()
        return artifact_id

    def read_machine_artifact(self, artifact_id: str) -> dict[str, object]:
        with closing(self._connect()) as connection:
            row = connection.execute("select * from machine_artifacts where artifact_id = ?", (artifact_id,)).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        artifact = json.loads(row["artifact_json"])
        return {
            "artifact_id": row["artifact_id"],
            "source_type": row["source_type"],
            "source_id": row["source_id"],
            "codec": row["codec"],
            "transform_chain": row["transform_chain"],
            "tokenizer": row["tokenizer"],
            "sha256_raw": row["sha256_raw"],
            "sha256_machine": row["sha256_machine"],
            "bytes_raw": row["bytes_raw"],
            "bytes_machine": row["bytes_machine"],
            "tokens_raw": row["tokens_raw"],
            "tokens_machine": row["tokens_machine"],
            "token_savings_ratio": row["token_savings_ratio"],
            "roundtrip_ok": bool(row["roundtrip_ok"]),
            "metadata": json.loads(row["metadata_json"]),
            "artifact": artifact,
            "machine_text": row["machine_text"],
            "created_at": row["created_at"],
        }

    def write_projection(
        self,
        record_id: str,
        projection_kind: str,
        projection_text: str,
        tokenizer: str | None = None,
        token_count: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> str:
        projection_id = f"px:{uuid4().hex[:12]}"
        with closing(self._connect()) as connection:
            connection.execute("delete from projection_index where record_id = ? and projection_kind = ?", (record_id, projection_kind))
            connection.execute(
                """
                insert into projection_index
                (projection_id, record_id, projection_kind, projection_text, tokenizer, token_count, metadata_json, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    projection_id,
                    record_id,
                    projection_kind,
                    projection_text,
                    tokenizer,
                    token_count,
                    json.dumps(metadata or {}, sort_keys=True, separators=(",", ":")),
                    utc_now(),
                ),
            )
            connection.commit()
        return projection_id

    def read_projections(self, record_id: str | None = None, projection_kind: str | None = None) -> list[dict[str, object]]:
        query = "select * from projection_index where 1=1"
        params: list[object] = []
        if record_id is not None:
            query += " and record_id = ?"
            params.append(record_id)
        if projection_kind is not None:
            query += " and projection_kind = ?"
            params.append(projection_kind)
        query += " order by updated_at desc"
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            {
                "projection_id": row["projection_id"],
                "record_id": row["record_id"],
                "projection_kind": row["projection_kind"],
                "projection_text": row["projection_text"],
                "tokenizer": row["tokenizer"],
                "token_count": row["token_count"],
                "metadata": json.loads(row["metadata_json"]),
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def write_benchmark_run(self, report: dict[str, object]) -> str:
        manifest = dict(report.get("manifest", {}))
        summary = dict(report.get("summary", {}))
        run_id = str(manifest.get("run_id") or f"bench:{uuid4().hex[:12]}")
        executed_suites = list(manifest.get("executed_suites", []))
        with closing(self._connect()) as connection:
            connection.execute(
                """
                insert or replace into benchmark_runs
                (run_id, requested_suite, executed_suites, status, bundle_hash, manifest_json, summary_json, report_json, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    manifest.get("requested_suite"),
                    json.dumps(executed_suites),
                    summary.get("status", "FAIL"),
                    report.get("bundle_hash"),
                    json.dumps(manifest, sort_keys=True, separators=(",", ":")),
                    json.dumps(summary, sort_keys=True, separators=(",", ":")),
                    json.dumps(report, sort_keys=True, separators=(",", ":")),
                    manifest.get("created_at") or utc_now(),
                ),
            )
            connection.execute("delete from benchmark_cases where run_id = ?", (run_id,))
            for family_name, family in dict(report.get("families", {})).items():
                for case in family.get("cases", []):
                    connection.execute(
                        """
                        insert into benchmark_cases
                        (run_id, case_id, family, status, case_hash, metrics_json, trace_json, case_json)
                        values (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            f"{family_name}:{case.get('case_id')}",
                            family_name,
                            case.get("status"),
                            case.get("case_hash"),
                            json.dumps(case.get("metrics", {}), sort_keys=True, separators=(",", ":")),
                            json.dumps(case.get("trace", {}), sort_keys=True, separators=(",", ":")),
                            json.dumps(case, sort_keys=True, separators=(",", ":")),
                        ),
                    )
            connection.commit()
        return run_id

    def read_benchmark_run(self, run_id: str) -> dict[str, object]:
        with closing(self._connect()) as connection:
            row = connection.execute("select report_json from benchmark_runs where run_id = ?", (run_id,)).fetchone()
        if row is None:
            return {}
        return json.loads(row["report_json"])

    def list_benchmark_runs(self, limit: int = 10) -> list[dict[str, object]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "select run_id, requested_suite, executed_suites, status, bundle_hash, created_at from benchmark_runs order by created_at desc limit ?",
                (limit,),
            ).fetchall()
        return [
            {
                "run_id": row["run_id"],
                "requested_suite": row["requested_suite"],
                "executed_suites": json.loads(row["executed_suites"]),
                "status": row["status"],
                "bundle_hash": row["bundle_hash"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def _document_status_row(row: sqlite3.Row) -> dict[str, object]:
    return {
        "document_id": row["document_id"],
        "ns": row["ns"],
        "scope": row["scope"],
        "source_ref": row["source_ref"],
        "source_hash": row["source_hash"],
        "byte_count": row["byte_count"],
        "chunk_count": row["chunk_count"],
        "extraction_status": row["extraction_status"],
        "indexed_status": row["indexed_status"],
        "deleted_at": row["deleted_at"],
        "metadata": json.loads(row["metadata_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }

