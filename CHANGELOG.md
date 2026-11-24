---
version: 0.1.0
---
# Changelog

## 0.1.0 (2026-11-24) — episode 1
- feat: heading chunker, BM25 retrieval, cited answers with Claude Opus 5.5, token and cost logging
- feat: 8-question set with hand-picked expected pages; `run` writes one JSON line per question
- test: chunker, ranking, prompt and citation parsing, refusal handling (fake client, no network)
- data: first real run `runs/ep01.jsonl` (2026-11-24, $0.088), hand grades `runs/ep01-grades.json` (2 full, 3 partial, 2 wrong "don't know", 1 correct), probe `runs/ep01-probe.json` ("How do I" alone ranks the Docker chunk first; 409 of 1,992 chunks hold a `{* ... *}` include tag instead of code)
