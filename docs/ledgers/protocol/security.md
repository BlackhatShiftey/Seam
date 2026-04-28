# Security Routing Ledger

Current stable facts:

- Do not commit or preserve API keys, passwords, private keys, local `.env` values, provider session URLs, chat/share links, thread links, or local agent transcript links.
- If a secret or private session URL appears in the working tree, delete the file or redact the value immediately.
- If a committed secret is discovered, stop and request explicit history-rewrite and rotation handling.
- `tools.history.verify_continuity` includes high-confidence session-link and secret scans.

Useful commands:

```powershell
python -m tools.history.verify_continuity
git check-ignore -v .env
```
