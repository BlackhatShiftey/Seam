from __future__ import annotations

from typing import Iterable

from .mirl import Artifact, MIRLRecord


def transpile_python(records: Iterable[MIRLRecord]) -> Artifact:
    ordered = sorted(records, key=lambda record: record.id)
    record_ids = [record.id for record in ordered]
    body = "\n".join(
        [
            "from seam import SeamRuntime",
            "",
            "runtime = SeamRuntime()",
            f"record_ids = {record_ids!r}",
            'pack = runtime.pack_ir(record_ids=record_ids, lens="workflow", mode="context")',
            "print(pack.to_dict())",
        ]
    )
    return Artifact(target="python", body=body, metadata={"record_ids": record_ids})
