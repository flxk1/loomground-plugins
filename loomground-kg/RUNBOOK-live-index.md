# Runbook — Live Index (auto-index every addition to the library)

Keeps the KG current: any PDF added to a library is indexed into the graph within seconds,
reusing the KG `canonical_urn`, appending only the small claim/fingerprint rows. Read-only on
the corpus. Device/OS-neutral core; the launchd agent below is the macOS adapter.

## Prerequisites
- The updated engine (with `versum sync/watch/seed-state`) on disk. It's at
  `Projects/Loomground/_kg_migrate/enginelive/loomground-versum` (verified: `sync.py` present).
- Your KG config at `Knowledge/Loomground Sources/06_Graph/versum/loomground-kg.config.json`
  (already written; the only machine-specific file).
- `/usr/bin/python3` with `pdfplumber` (verified 0.11.9).

## One-time setup (run in Terminal)
Environment shortcut (optional):
```
export LOOMGROUND_KG_CONFIG="/Users/rafelixkrone/Documents/Claude/Knowledge/Loomground Sources/06_Graph/versum/loomground-kg.config.json"
export PYTHONPATH="/Users/rafelixkrone/Documents/Claude/Projects/Loomground/_kg_migrate/enginelive/loomground-versum"
```
1. **Seed** — snapshot the ~6,900 already-migrated files as "done" so the watcher only picks
   up *new* additions. This hashes the corpus once (a few minutes; it's the one slow step):
   ```
   python3 -m versum seed-state --config "$LOOMGROUND_KG_CONFIG"
   ```
2. **Install the watcher** (the macOS auto-start adapter):
   ```
   cp "/Users/rafelixkrone/Documents/Claude/Projects/Loomground/skills/loomground-kg/adapters/launchd/com.loomground.kg.watch.plist" ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.loomground.kg.watch.plist
   ```
   It now runs on login and every ~30s scans for changes, indexing new files.

## Verify
- Drop a PDF into any domain folder under `Knowledge/Library/<domain>/`.
- Within ~30s: `tail -f Projects/Loomground/_kg_migrate/watch.out.log` shows `indexed=1`.
- `python3 kg_query.py status` (in the skill dir) shows the claim/work counts rise.

## Rollback (stop auto-indexing)
```
launchctl unload ~/Library/LaunchAgents/com.loomground.kg.watch.plist
```
The KG is untouched by unloading; re-load to resume. To run a single pass by hand instead:
`python3 -m versum sync --config "$LOOMGROUND_KG_CONFIG"`.

## Notes / escalation
- Nothing is fetched or deleted; the corpus is read-only. New docs not in the registry mint a
  fresh `canonical_urn` — for provenance-correct new documents, route them through
  `capture-to-kg` first, then the watcher indexes them.
- Updates to the engine can't overwrite files through the Cowork bridge; install a new engine
  into a fresh folder and repoint `PYTHONPATH`/the plist.
- If `watch.err.log` shows repeated errors, `launchctl unload` and run one `sync` by hand to see
  the failing file.
