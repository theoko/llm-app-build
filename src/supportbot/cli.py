"""python -m supportbot ask "question"   |   python -m supportbot run evals/questions.jsonl runs/ep01.jsonl"""
import json
import sys
from pathlib import Path

import anthropic

from .answer import ask
from .corpus import load
from .retrieve import BM25

DOCS = Path(__file__).resolve().parents[2] / "corpus-src" / "docs" / "en" / "docs"


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
    chunks = load(DOCS)
    index = BM25(chunks)
    client = anthropic.Anthropic()
    if argv[:1] == ["ask"] and len(argv) == 2:
        r = answer_one(client, index, argv[1])
        print(r["answer"], "\n\nSources:", *r["cited"], sep="\n")
        print(f"\n{r['input_tokens']} in / {r['output_tokens']} out tokens, ${r['cost_usd']}")
        return 0
    if argv[:1] == ["run"] and len(argv) == 3:
        rows = [json.loads(l) for l in Path(argv[1]).read_text().splitlines() if l.strip()]
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
