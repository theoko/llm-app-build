"""python -m supportbot ask "question"
python -m supportbot run evals/questions.jsonl runs/ep01.jsonl
python -m supportbot grade runs/ep02.jsonl evals/ep02-questions.jsonl runs/ep02-graded.jsonl [--v2]
python -m supportbot agree runs/ep02-graded.jsonl runs/ep02-hand.json
python -m supportbot compare runs/ep02-graded-v2.jsonl runs/ep02b-graded-v2.jsonl"""
import json
import sys
from pathlib import Path

import anthropic

from .answer import ask
from .corpus import load
from .grade import agree, compare, grade_run, summary
from .retrieve import BM25

DOCS = Path(__file__).resolve().parents[2] / "corpus-src" / "docs" / "en" / "docs"


def _jsonl(path: str) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def answer_one(client, index, question: str) -> dict:
    sources = [c for c, _ in index.search(question, k=5)]
    a = ask(client, question, sources)
    return {
        "question": question,
        "retrieved": [f"{c.path}#{c.heading}" for c in sources],
        "answer": a.text,
        "cited": [f"{sources[n - 1].path}#{sources[n - 1].heading}" for n in a.cited],
        "input_tokens": a.input_tokens,
        "output_tokens": a.output_tokens,
        "cost_usd": round(a.cost_usd, 5),
        "stop_reason": a.stop_reason,
    }


def main(argv: list[str]) -> int:
    if argv[:1] == ["agree"] and len(argv) == 3:
        hand = json.loads(Path(argv[2]).read_text())
        res = agree(_jsonl(argv[1]), hand["grades"])
        print(json.dumps(res, indent=1))
        return 0
    if argv[:1] == ["compare"] and len(argv) == 3:
        print(json.dumps(compare(_jsonl(argv[1]), _jsonl(argv[2])), indent=1))
        return 0
    if argv[:1] == ["grade"] and (len(argv) == 4 or argv[4:] == ["--v2"]):
        index = BM25(load(DOCS)) if argv[4:] == ["--v2"] else None
        graded = grade_run(anthropic.Anthropic(), _jsonl(argv[1]), _jsonl(argv[2]), DOCS, index)
        Path(argv[3]).write_text("".join(json.dumps(g) + "\n" for g in graded))
        s = summary(graded)
        Path(argv[3]).with_suffix(".summary.json").write_text(json.dumps(s, indent=1) + "\n")
        print(json.dumps(s, indent=1))
        return 0
    chunks = load(DOCS)
    index = BM25(chunks)
    client = anthropic.Anthropic()
    if argv[:1] == ["ask"] and len(argv) == 2:
        r = answer_one(client, index, argv[1])
        print(r["answer"], "\n\nSources:", *r["cited"], sep="\n")
        print(f"\n{r['input_tokens']} in / {r['output_tokens']} out tokens, ${r['cost_usd']}")
        return 0
    if argv[:1] == ["run"] and len(argv) == 3:
        rows = _jsonl(argv[1])
        with open(argv[2], "w") as out:
            for row in rows:
                r = answer_one(client, index, row["question"]) | {"expect": row.get("expect")}
                r["retrieval_hit"] = bool(row.get("expect")) and any(row["expect"] in p for p in r["retrieved"])
                out.write(json.dumps(r) + "\n")
                print(("hit " if r["retrieval_hit"] else "miss") if row.get("expect") else "none", "|", row["question"])
        print(f"{len(chunks)} chunks indexed")
        return 0
    print(__doc__)
    return 2
