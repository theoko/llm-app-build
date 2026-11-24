# supportbot

A support assistant over the FastAPI documentation, built from an empty folder one episode at a time. Each episode adds one production piece; see [SERIES.md](SERIES.md).

## Run it

```sh
python3 -m venv .venv && .venv/bin/pip install -e . pytest
scripts/get-docs.sh                       # FastAPI docs at a pinned commit
export ANTHROPIC_API_KEY=...              # or `ant auth login`
.venv/bin/python -m supportbot ask "How do I make a query parameter optional?"
.venv/bin/python -m supportbot run evals/questions.jsonl runs/ep01.jsonl
.venv/bin/python -m supportbot run evals/ep02-questions.jsonl runs/ep02.jsonl
.venv/bin/python -m supportbot grade runs/ep02.jsonl evals/ep02-questions.jsonl runs/ep02-graded.jsonl
.venv/bin/python -m supportbot agree runs/ep02-graded.jsonl runs/ep02-hand.json
.venv/bin/pytest -q
```

## Episode 1: the baseline

`corpus.py` splits each docs page into one chunk per heading, `retrieve.py` ranks chunks with BM25 keyword search, and `answer.py` sends the top 5 to Claude with instructions to answer only from them, cite each claim, and say "I don't know based on the docs." otherwise. Every answer logs its tokens and cost.

`evals/questions.jsonl` holds 8 questions written in a user's words. The `expect` field names the docs page that holds the answer; it was chosen by hand. `runs/ep01.jsonl` is the real output shown in the episode.

## Episode 2: an evaluation set

`evals/ep02-questions.jsonl` keeps the 8 episode 1 questions first, unchanged, and adds 31 more, worded as a user would ask them, without reading the page text first. 5 of the 39 have no answer in the docs. 10 are marked `holdout`: later episodes tune retrieval on the `dev` rows only, so the holdout score stays honest. Holdout answers were read once, to audit the judge in this episode; later episodes use only their totals.

`grade.py` grades a run three ways:

- **Retrieval:** the rank of the first chunk from the expected page (hit@1, hit@5, MRR). No model needed.
- **Rules:** the exact refusal on an answerable question is `none`, on an unanswerable one `correct-none`; any other reply to an unanswerable question is `unsupported`.
- **Judge:** every other answer goes to Claude with the expected docs page as reference and a three-grade rubric (`full`, `partial`, `wrong`). A reply that is not one line of valid JSON counts as `unparsed`, never as a grade.

The judge was checked against hand grades: the 8 saved episode 1 answers (`runs/ep01-judged.jsonl`), and a blind sample of 8 new answers graded by hand before the judge ran (`runs/ep02-hand.json`).

`grade ... --v2` (judge v2, also shown the bot's own sources) and `compare` are in this release for episode 3; the episode 2 numbers come from judge v1.

## Credits

Corpus: the [FastAPI documentation](https://github.com/fastapi/fastapi) by Sebastián Ramírez and contributors, MIT License, used unmodified at commit `05e6df7e`. This project is independent and not affiliated with FastAPI.
