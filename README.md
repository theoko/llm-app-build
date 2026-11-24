# supportbot

A support assistant over the FastAPI documentation, built from an empty folder one episode at a time. Each episode adds one production piece; see [SERIES.md](SERIES.md).

## Run it

```sh
python3 -m venv .venv && .venv/bin/pip install -e . pytest
scripts/get-docs.sh                       # FastAPI docs at a pinned commit
export ANTHROPIC_API_KEY=...              # or `ant auth login`
.venv/bin/python -m supportbot ask "How do I make a query parameter optional?"
.venv/bin/python -m supportbot run evals/questions.jsonl runs/ep01.jsonl
.venv/bin/pytest -q
```

## Episode 1: the baseline

`corpus.py` splits each docs page into one chunk per heading, `retrieve.py` ranks chunks with BM25 keyword search, and `answer.py` sends the top 5 to Claude with instructions to answer only from them, cite each claim, and say "I don't know based on the docs." otherwise. Every answer logs its tokens and cost.

`evals/questions.jsonl` holds 8 questions written in a user's words. The `expect` field names the docs page that holds the answer; it was chosen by hand. `runs/ep01.jsonl` is the real output shown in the episode.

## Credits

Corpus: the [FastAPI documentation](https://github.com/fastapi/fastapi) by Sebastián Ramírez and contributors, MIT License, used unmodified at commit `05e6df7e`. This project is independent and not affiliated with FastAPI.
