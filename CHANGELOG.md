---
version: 0.2.0
---
# Changelog

## 0.2.0 (2026-11-24) — episode 2
- feat: `grade.py` and `grade` / `agree` commands: retrieval rank (hit@1, hit@5, MRR), rule grades for refusals and unanswerable questions, a Claude judge with the expected page as reference; unreadable judge replies count as `unparsed`
- data: `evals/ep02-questions.jsonl`, 39 questions (the 8 from episode 1 first, unchanged; 5 with no answer in the docs; 10 marked `holdout`)
- data: real run `runs/ep02.jsonl` ($0.403), graded `runs/ep02-graded.jsonl` (judge $0.302), summary `runs/ep02-graded.summary.json`; judge calibration on the saved episode 1 answers `runs/ep01-judged.jsonl` ($0.101)
- result (deterministic): the expected page is in the top 5 for 6/7 episode 1 questions and 12/27 new ones; among new questions, dev 10/19 and holdout 2/8. All dev rows: 16/26, MRR 0.442 (dev holds the 7 easier episode 1 questions; holdout MRR 0.104). This is a lower bound: the PATCH question counts as a miss but was answered in full from another page.
- result (one run, not repeated): grades over all 39 are 8 full, 9 partial, 3 wrong, 14 none, 5 correct-none, 0 unsupported, 0 unparsed. 11 of the 14 `none` answers had the expected page outside the top 5. Questions 1-8 got identical retrieval in both episodes, yet 2 of 8 changed grade (file upload none -> wrong, login partial -> none), so a shift of a few grades between runs is noise until runs are repeated.
- result: the judge agreed with hand grades on 4 of 5 judged episode 1 answers and on 6 of 8 in a blind episode 2 sample (both misses: judge `partial`, hand `full`). The blind sample held no answer the judge called `wrong`, so it checks full versus partial only.
- known issue: all 3 episode 2 `wrong` grades (and the 1 in the episode 1 calibration) are doubtful. Websockets and login: the bot said the sources it was given don't cover the topic, and the judge read that as a false claim about FastAPI. File upload (expected page at rank 1): a refusal in other words, which the three judge grades have no slot for. Database session: `Depends(..., max_concurrency=5)` is documented in `advanced/advanced-dependencies.md`, a page the judge never saw, because the judge gets only the expected page, not the retrieved sources. The episode 2 grades above come from judge v1 and stay as they are.
- feat (not yet run; for episode 3): judge v2, `grade ... --v2`. The judge also sees the bot's own numbered sources (re-searched, and the run fails closed if the search no longer returns the run's sources), may grade a reworded refusal `none`, and gets a 40,000-character reference (v1: 30,000). `compare` counts grade changes between two graded runs of the same questions, split into rule-level and judge-level changes
- test: 16 offline tests for grading, judge v2 and compare (fake client, no network); 20 in all

## 0.1.0 (2026-11-24) — episode 1
- feat: heading chunker, BM25 retrieval, cited answers with Claude Opus 5.5, token and cost logging
- feat: 8-question set with hand-picked expected pages; `run` writes one JSON line per question
- test: chunker, ranking, prompt and citation parsing, refusal handling (fake client, no network)
- data: first real run `runs/ep01.jsonl` (2026-11-24, $0.088), hand grades `runs/ep01-grades.json` (2 full, 3 partial, 2 wrong "don't know", 1 correct), probe `runs/ep01-probe.json` ("How do I" alone ranks the Docker chunk first; 409 of 1,992 chunks hold a `{* ... *}` include tag instead of code)
