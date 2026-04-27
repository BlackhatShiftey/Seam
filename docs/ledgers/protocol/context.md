# Context Routing Ledger

Current stable facts:

- `HISTORY.md` is complete append-only chronology.
- `HISTORY_INDEX.md` is compact routing state.
- `tools.history.build_context_pack` is the default way to load task-specific history under a token budget.
- `tools.history.verify_continuity` is the end-of-session quality gate.
- Full history should not be loaded during normal startup.

Useful commands:

```powershell
python -m tools.history.build_context_pack --topics protocol,history --latest 2 --token-budget 1000
python -m tools.history.build_context_pack --route protocol/context --token-budget 900
python -m tools.history.verify_continuity
```
