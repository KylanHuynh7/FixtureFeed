# Pending review

Decisions made by the engineer under the temporary delegation (DECISIONS.md #21).
None of these is approved. Each needs the director's explicit approval or reversal.

| # | Decision | Why | Alternative | Easy to reverse? |
|---|---|---|---|---|
| R1 | TBD rule marks only the **Sunday** games in a TBD week (Thu/Sat/Mon keep their listed times). | Those slots are announced separately; marking them TBD would hide real times. Same result for the 2026 schedule. | Mark the whole week TBD, as #18 C was worded. | Yes, one line in `sources/nflverse.py`. |
| R2 | A small runnable entry point: `uv run python -m fixturefeed.ingest [FILE]`, fetching with Python's built-in `urllib`. | Something has to run the pipeline; built-in library means no new dependency. | A command-line tool via `[project.scripts]`, or `httpx` as a dependency. | Yes. |
| R3 | Ingests are serialized with a Postgres advisory lock. | Two overlapping runs could otherwise both plan against the same old state and double-apply changes. | No lock (rely on running one at a time). | Yes. |
| R4 | Unknown team abbreviations reject the whole snapshot. | Safer than inserting half a schedule; a renamed team would show up as a clear rejection reason. | Skip only the affected rows. | Yes. |
| R5 | If a source ID (e.g. date-based `pfr`) gets reused by a different game, it is re-pointed to the newest game. | IDs can be recycled after reschedules; newest snapshot is the truth. Matching never uses `pfr`, so this only affects stored metadata. | Keep the first mapping and ignore the new one. | Yes. |
| R6 | Change-log format: one summary row for created/cancelled/restored, plus one `updated` row per changed field. | Easy to query for the future change-history page. | One row per change with a JSON blob of all fields. | Yes before launch; harder after real history accumulates. |
| R7 | Raw snapshots are saved to `data/snapshots/` (gitignored) on every run, including rejected ones. | A rejected file is exactly what you need to debug a rejection. | Save accepted snapshots only. | Yes. |
| R8 | `CURRENT_SEASON = 2026` constant in `config.py`; only that season is ingested and served. | MVP needs one season; the file contains 1999–2026. | Ingest all seasons. | Yes. |
