from __future__ import annotations

from seam_runtime.cli import run_cli
from seam_runtime.dsl import compile_dsl
from seam_runtime.mirl import IRBatch, MIRLRecord, Pack
from seam_runtime.models import HashEmbeddingModel, OpenAICompatibleEmbeddingModel
from seam_runtime.nl import compile_nl
from seam_runtime.pack import pack_records, unpack_exact_pack
from seam_runtime.runtime import SeamRuntime
from seam_runtime.verify import verify_ir


def pack_ir(records, lens: str = "general", budget: int = 512, mode: str = "context") -> Pack:
    if isinstance(records, IRBatch):
        batch = records
    else:
        batch = IRBatch(list(records))
    return pack_records(batch.records, lens=lens, budget=budget, mode=mode)


def decompile_ir(records, mode: str = "expanded") -> str:
    if isinstance(records, IRBatch):
        batch = records
    else:
        batch = IRBatch(list(records))
    states = [record for record in batch.records if record.kind.value == "STA"]
    claims = [record for record in batch.records if record.kind.value == "CLM"]
    if states:
        fields = states[0].attrs.get("fields", {})
        summary = "; ".join(f"{key}={value}" for key, value in fields.items())
    elif claims:
        summary = "; ".join(f"{record.attrs.get('subject')} {record.attrs.get('predicate')} {record.attrs.get('object')}" for record in claims)
    else:
        summary = "No MIRL records available."
    return summary if mode == "minimal" else f"MIRL summary: {summary}"


def render_ir(records) -> str:
    if isinstance(records, IRBatch):
        return records.to_text()
    return IRBatch(list(records)).to_text()


def load_ir_lines(text: str) -> list[MIRLRecord]:
    return IRBatch.from_text(text).records


def unpack_pack(pack: Pack | str):
    if isinstance(pack, Pack):
        if pack.mode == "exact":
            return unpack_exact_pack(pack).to_json()
        return pack.payload
    raise TypeError("unpack_pack now expects a Pack instance")


def main() -> None:
    run_cli()


if __name__ == "__main__":
    main()
