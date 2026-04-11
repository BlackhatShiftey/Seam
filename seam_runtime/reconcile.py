from __future__ import annotations

from collections import defaultdict

from .mirl import IRBatch, MIRLRecord, ReconcileReport, RecordKind, Status


def reconcile_ir(batch: IRBatch) -> ReconcileReport:
    claims = [record for record in batch.records if record.kind == RecordKind.CLM]
    actions: list[dict[str, object]] = []
    added_records: list[MIRLRecord] = []
    groups: dict[tuple[str, str], list[MIRLRecord]] = defaultdict(list)

    for claim in claims:
        groups[(str(claim.attrs.get("subject")), str(claim.attrs.get("predicate")))].append(claim)

    for (subject, predicate), group in groups.items():
        if len(group) < 2:
            continue
        objects: dict[str, list[MIRLRecord]] = {}
        for claim in group:
            objects.setdefault(str(claim.attrs.get("object")), []).append(claim)
        if len(objects) == 1:
            ids = [claim.id for claim in group]
            actions.append({"type": "duplicates", "records": ids})
            added_records.append(MIRLRecord(id=f"rel:dup:{subject}:{predicate}", kind=RecordKind.REL, ns=group[0].ns, scope=group[0].scope, status=Status.INFERRED, conf=0.8, attrs={"src": ids[0], "predicate": "duplicates", "dst": ids[-1]}))
            continue

        ordered = sorted(group, key=lambda item: (item.updated_at, item.conf), reverse=True)
        winner = ordered[0]
        for loser in ordered[1:]:
            relation = "supersedes" if winner.updated_at >= loser.updated_at else "contradicts"
            actions.append({"type": relation, "winner": winner.id, "loser": loser.id})
            added_records.append(MIRLRecord(id=f"rel:{relation}:{winner.id}:{loser.id}", kind=RecordKind.REL, ns=winner.ns, scope=winner.scope, status=Status.INFERRED, conf=0.75, attrs={"src": winner.id, "predicate": relation, "dst": loser.id}))
        added_records.append(MIRLRecord(id=f"sta:reconciled:{subject}:{predicate}", kind=RecordKind.STA, ns=winner.ns, scope=winner.scope, status=Status.INFERRED, conf=winner.conf, prov=list({prov for claim in group for prov in claim.prov}), evidence=list({ev for claim in group for ev in claim.evidence}), attrs={"target": subject, "fields": {predicate: winner.attrs.get("object")}}))
    return ReconcileReport(added_records=added_records, actions=actions)
