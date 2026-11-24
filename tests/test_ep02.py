from types import SimpleNamespace as NS

import pytest

from supportbot import grade
from supportbot.answer import NO_ANSWER


class Fake:
    def __init__(self, text, model="claude-opus-5-5"):
        self.text, self.model, self.calls = text, model, []
        self.beta = NS(messages=NS(create=self.create))

    def create(self, **kw):
        self.calls.append(kw)
        return NS(content=[NS(type="text", text=self.text)], stop_reason="end_turn", model=self.model,
                  usage=NS(input_tokens=2000, output_tokens=50))


class NoCalls:
    beta = NS(messages=NS(create=lambda **kw: pytest.fail("rule-graded rows must not call the judge")))


def test_rank_is_first_matching_position():
    got = ["a.md#X", "tutorial/cors.md#CORS", "tutorial/cors.md#More"]
    assert grade.rank(got, "tutorial/cors.md") == 2
    assert grade.rank(got, "tutorial/security/") is None
    assert grade.rank(got, None) is None


def test_rule_grades():
    assert grade.rule_grade(NO_ANSWER, None) == "correct-none"
    assert grade.rule_grade("Use slowapi.", None) == "unsupported"
    assert grade.rule_grade(f" {NO_ANSWER}\n", "x.md") == "none"
    assert grade.rule_grade(f"{NO_ANSWER} But try [1].", "x.md") is None  # not the exact refusal: the judge decides


def test_judge_parses_grade_and_keeps_raw_reply():
    f = Fake('Sure: {"grade": "partial", "why": "no code"}', model="claude-sonnet-5-5")
    g = grade.judge(f, "q?", "ans", "REF TEXT")
    assert (g["grade"], g["why"], g["judge_model"]) == ("partial", "no code", "claude-sonnet-5-5")
    assert g["judge_raw"].startswith("Sure:")
    kw = f.calls[0]
    assert kw["model"] == "claude-opus-5-5" and kw["fallbacks"] == "default"
    assert "REF TEXT" in kw["messages"][0]["content"] and "<answer>\nans\n</answer>" in kw["messages"][0]["content"]
    assert abs(g["judge_cost_usd"] - (2000 * 4 + 50 * 20) / 1e6) < 1e-9


@pytest.mark.parametrize("text", ["full", '{"grade": "great"}', '{"grade": "full"', ""])
def test_unreadable_judge_reply_is_unparsed_not_a_grade(text):
    assert grade.judge(Fake(text), "q", "a", "r")["grade"] == "unparsed"


def test_grade_run_uses_rules_first_and_joins_split(tmp_path):
    (tmp_path / "p.md").write_text("page")
    run = [{"question": "q1", "retrieved": ["p.md#H"], "answer": NO_ANSWER, "expect": "p.md"},
           {"question": "q2", "retrieved": [], "answer": NO_ANSWER, "expect": None}]
    qs = [{"question": "q1", "split": "holdout"}]
    out = grade.grade_run(NoCalls(), run, qs, tmp_path)
    assert [(g["grade"], g["split"], g["rank"]) for g in out] == [("none", "holdout", 1), ("correct-none", "dev", None)]
    f = Fake('{"grade": "full", "why": "ok"}')
    out = grade.grade_run(f, [run[0] | {"answer": "Use X [1]."}], qs, tmp_path)
    assert out[0]["grade"] == "full" and out[0]["graded_by"] == "judge" and len(f.calls) == 1
    assert "<reference>\npage\n</reference>" in f.calls[0]["messages"][0]["content"]


def test_reference_joins_a_directory_and_caps_length(tmp_path):
    d = tmp_path / "security"
    d.mkdir()
    (d / "a.md").write_text("A" * 10)
    (d / "b.md").write_text("B" * grade.REF_CHARS)
    ref = grade.reference(tmp_path, "security/")
    assert ref.startswith("A" * 10 + "\n\nB") and len(ref) == grade.REF_CHARS


def test_summary_counts_per_split():
    rows = [{"split": "dev", "expect": "a", "rank": 1, "grade": "full"},
            {"split": "dev", "expect": "b", "rank": 4, "grade": "partial", "judge_cost_usd": 0.01},
            {"split": "dev", "expect": "c", "rank": None, "grade": "none"},
            {"split": "holdout", "expect": None, "rank": None, "grade": "unsupported"}]
    s = grade.summary(rows)
    assert (s["dev"]["hit_at_1"], s["dev"]["hit_at_5"], s["dev"]["mrr"]) == (1, 2, round(1.25 / 3, 3))
    assert s["holdout"]["answerable"] == 0 and s["holdout"]["mrr"] is None
    assert s["all"]["grades"]["unsupported"] == 1 and s["judge_cost_usd"] == 0.01


def test_agree_with_list_and_dict():
    g = [{"question": "a", "grade": "full", "graded_by": "judge"}, {"question": "b", "grade": "none", "graded_by": "rule"}]
    assert grade.agree(g, ["partial", "none"]) | {"mismatches": None} == {
        "compared": 2, "agree": 1, "judge_compared": 1, "judge_agree": 0, "mismatches": None}
    assert grade.agree(g, {"b": "none"})["compared"] == 1


def _index(tmp_path):
    from supportbot.corpus import load
    from supportbot.retrieve import BM25
    (tmp_path / "files.md").write_text("# Upload files\n\nUse File and UploadFile to accept an uploaded file in a request body.\n")
    (tmp_path / "cors.md").write_text("# CORS\n\nAdd CORSMiddleware so a frontend on another origin can call the API.\n")
    return BM25(load(tmp_path))


def test_v2_judge_sees_the_bots_numbered_sources_and_can_grade_none(tmp_path):
    idx = _index(tmp_path)
    got = [f"{c.path}#{c.heading}" for c, _ in idx.search("upload a file", k=5)]
    run = [{"question": "upload a file", "retrieved": got, "answer": "My sources don't cover this.", "expect": "files.md"}]
    f = Fake('{"grade": "none", "why": "declines"}')
    out = grade.grade_run(f, run, [], tmp_path, idx)
    assert (out[0]["grade"], out[0]["judge_version"]) == ("none", 2)
    kw = f.calls[0]
    assert kw["system"] == grade.JUDGE_V2
    assert "<sources>\n[1] files.md — Upload files\nUse File and UploadFile" in kw["messages"][0]["content"]
    assert "Question: upload a file" in kw["messages"][0]["content"]


def test_v1_still_rejects_none_and_sends_no_sources(tmp_path):
    f = Fake('{"grade": "none", "why": "declines"}')
    assert grade.judge(f, "q", "a", "ref")["grade"] == "unparsed"
    assert "<sources>" not in f.calls[0]["messages"][0]["content"] and f.calls[0]["system"] == grade.JUDGE


def test_v2_fails_closed_when_search_differs_from_the_run(tmp_path):
    idx = _index(tmp_path)
    run = [{"question": "upload a file", "retrieved": ["other.md#X"], "answer": "Use File [1].", "expect": "files.md"}]
    with pytest.raises(ValueError, match="no longer returns"):
        grade.grade_run(Fake('{"grade": "full"}'), run, [], tmp_path, idx)


def test_v2_reference_cap_is_larger(tmp_path):
    (tmp_path / "big.md").write_text("x" * (grade.REF_CHARS + 5))
    assert len(grade.reference(tmp_path, "big.md")) == grade.REF_CHARS
    assert len(grade.reference(tmp_path, "big.md", grade.REF_CHARS_V2)) == grade.REF_CHARS + 5


def test_compare_splits_rule_and_judge_level_changes():
    a = [{"question": "q1", "split": "dev", "grade": "none", "graded_by": "rule"},
         {"question": "q2", "split": "dev", "grade": "full", "graded_by": "judge"},
         {"question": "q3", "split": "holdout", "grade": "partial", "graded_by": "judge"}]
    b = [dict(a[0], grade="partial", graded_by="judge"), dict(a[1], grade="partial"), a[2]]
    c = grade.compare(a, b)
    assert (c["changed"], c["rule_level"], c["judge_level"]) == (2, 1, 1)
    assert [x["question"] for x in c["changes"]] == ["q1", "q2"]
    with pytest.raises(ValueError):
        grade.compare(a, b[:2])
