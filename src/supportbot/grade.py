"""Episode 2: grade a run. Retrieval by the rank of the expected page; answers by rule where
possible, otherwise by a model judge that reads the docs page the question should be answered from."""
import json
import re
from pathlib import Path

from .answer import MODEL, NO_ANSWER, PRICE_IN, PRICE_OUT, build_prompt

# full/partial/wrong come from the judge; none/correct-none/unsupported from rules; unparsed = judge reply unreadable.
GRADES = ("full", "partial", "wrong", "none", "correct-none", "unsupported", "unparsed")
REF_CHARS = 30000     # judge v1 (kept so the v1 files reproduce)
REF_CHARS_V2 = 40000  # longest expected reference, tutorial/security/, is 37,209 chars joined
JUDGE = (
    "You grade one answer from a FastAPI support bot against the FastAPI docs page that answers the question.\n"
    "Grades:\n"
    "full = correct, and it gives usable code (or the question needs none)\n"
    "partial = the right idea, but no usable code, or it answers only part of the question\n"
    "wrong = it says something the reference contradicts, or code that would not work\n"
    "The reference may hold tags like {* ../../docs_src/x.py *} where the docs include code from a file "
    "you cannot see. Do not mark an answer down only because its code is not visible in the reference.\n"
    'Reply with one line of JSON and nothing else: {"grade": "full|partial|wrong", "why": "<one sentence>"}'
)


# v2: the judge also sees the bot's own numbered sources, and can grade a reworded refusal `none`.
JUDGE_V2 = (
    "You grade one answer from a FastAPI support bot. The bot was told to answer only from the numbered "
    "<sources> it was given and to cite them as [n]. You also get <reference>, the FastAPI docs page that "
    "answers the question; the bot did not see it.\n"
    "Grades:\n"
    "full = correct, and it gives usable code (or the question needs none)\n"
    "partial = the right idea, but no usable code, or it answers only part of the question\n"
    "none = it does not answer: it declines, or says its sources don't cover the question, and gives no usable answer\n"
    "wrong = it says something the reference or the sources contradict, or code that would not work\n"
    "Saying its sources don't cover something is not wrong when those sources indeed don't; grade the answer on what it does give. "
    "A feature counts as documented if the sources or the reference show it.\n"
    "The texts may hold tags like {* ../../docs_src/x.py *} where the docs include code from a file "
    "you cannot see. Do not mark an answer down only because its code is not visible.\n"
    'Reply with one line of JSON and nothing else: {"grade": "full|partial|none|wrong", "why": "<one sentence>"}'
)


def rank(retrieved: list[str], expect: str | None) -> int | None:
    """1-based position of the first retrieved chunk from the expected page, or None."""
    if not expect:
        return None
    return next((i for i, p in enumerate(retrieved, 1) if expect in p), None)


def rule_grade(answer: str, expect: str | None) -> str | None:
    said_no = answer.strip() == NO_ANSWER
    if expect is None:
        return "correct-none" if said_no else "unsupported"
    return "none" if said_no else None


def reference(docs: Path, expect: str, cap: int = REF_CHARS) -> str:
    files = sorted((docs / expect).rglob("*.md")) if expect.endswith("/") else [docs / expect]
    return "\n\n".join(f.read_text(encoding="utf-8") for f in files)[:cap]


def judge(client, question: str, answer: str, ref: str, sources=None) -> dict:
    """sources=None: judge v1 (reference only). A list of Chunks: judge v2."""
    v2 = sources is not None
    asked = build_prompt(question, sources) if v2 else f"Question: {question}"
    allowed = ("full", "partial", "wrong", "none") if v2 else ("full", "partial", "wrong")
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low"},
        system=JUDGE_V2 if v2 else JUDGE,
        messages=[{"role": "user", "content": f"<reference>\n{ref}\n</reference>\n\n{asked}\n\n<answer>\n{answer}\n</answer>"}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    grade, why = "unparsed", ""
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            j = json.loads(m.group(0))
            if j.get("grade") in allowed:
                grade, why = j["grade"], str(j.get("why", ""))
        except json.JSONDecodeError:
            pass
    cost = resp.usage.input_tokens * PRICE_IN + resp.usage.output_tokens * PRICE_OUT
    return {"grade": grade, "why": why, "judge_raw": raw, "judge_model": getattr(resp, "model", ""),
            "judge_cost_usd": round(cost, 5), "judge_stop_reason": resp.stop_reason}


def grade_run(client, run_rows: list[dict], questions: list[dict], docs: Path, index=None) -> list[dict]:
    """index=None grades with judge v1; a BM25 index switches to v2, which re-runs the search to get the sources."""
    split = {q["question"]: q.get("split", "dev") for q in questions}
    out = []
    for r in run_rows:
        g = {"question": r["question"], "split": split.get(r["question"], "dev"), "expect": r.get("expect"),
             "rank": rank(r["retrieved"], r.get("expect")), "answer": r["answer"], "judge_version": 2 if index else 1}
        rule = rule_grade(r["answer"], r.get("expect"))
        if rule:
            g |= {"grade": rule, "graded_by": "rule"}
        elif index:
            sources = [c for c, _ in index.search(r["question"], k=5)]
            if [f"{c.path}#{c.heading}" for c in sources] != r["retrieved"]:
                raise ValueError(f"search no longer returns the run's sources: {r['question']}")
            g |= judge(client, r["question"], r["answer"], reference(docs, r["expect"], REF_CHARS_V2), sources) | {"graded_by": "judge"}
        else:
            g |= judge(client, r["question"], r["answer"], reference(docs, r["expect"])) | {"graded_by": "judge"}
        out.append(g)
    return out


def summary(graded: list[dict]) -> dict:
    res = {}
    for name in ("dev", "holdout", "all"):
        rows = [g for g in graded if name == "all" or g["split"] == name]
        ans = [g for g in rows if g["expect"]]
        res[name] = {
            "questions": len(rows),
            "answerable": len(ans),
            "hit_at_1": sum(g["rank"] == 1 for g in ans),
            "hit_at_5": sum(g["rank"] is not None for g in ans),
            "mrr": round(sum(1 / g["rank"] for g in ans if g["rank"]) / len(ans), 3) if ans else None,
            "grades": {k: sum(g["grade"] == k for g in rows) for k in GRADES},
        }
    res["judge_cost_usd"] = round(sum(g.get("judge_cost_usd", 0) for g in graded), 4)
    return res


def agree(graded: list[dict], hand) -> dict:
    """hand: a list aligned with the run (episode 1 file) or a {question: grade} dict."""
    pairs = list(zip(graded, hand)) if isinstance(hand, list) else [(g, hand[g["question"]]) for g in graded if g["question"] in hand]
    misses = [{"question": g["question"], "hand": h, "auto": g["grade"]} for g, h in pairs if g["grade"] != h]
    judged = [(g, h) for g, h in pairs if g["graded_by"] == "judge"]
    return {"compared": len(pairs), "agree": len(pairs) - len(misses),
            "judge_compared": len(judged), "judge_agree": sum(g["grade"] == h for g, h in judged), "mismatches": misses}


def compare(a: list[dict], b: list[dict]) -> dict:
    """Grade changes between two graded runs of the same questions. A rule-level change means one answer was
    the exact refusal and the other was not (pure answer variance); a judge-level change has a judge grade on
    both sides, so it mixes answer and judge variance."""
    if [g["question"] for g in a] != [g["question"] for g in b]:
        raise ValueError("the two runs hold different questions")
    changed = [{"question": x["question"], "split": x["split"], "a": x["grade"], "b": y["grade"],
                "level": "judge" if x["graded_by"] == y["graded_by"] == "judge" else "rule"}
               for x, y in zip(a, b) if x["grade"] != y["grade"]]
    return {"questions": len(a), "changed": len(changed),
            "rule_level": sum(c["level"] == "rule" for c in changed),
            "judge_level": sum(c["level"] == "judge" for c in changed), "changes": changed}
