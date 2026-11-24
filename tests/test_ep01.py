from types import SimpleNamespace as NS

from supportbot import answer
from supportbot.corpus import Chunk, split_markdown
from supportbot.retrieve import BM25


def test_split_ignores_headings_in_code():
    md = "# Title\n" + "intro text " * 10 + "\n```py\n# not a heading\n```\n## Next\n" + "body " * 20
    assert [h for h, _ in split_markdown(md)] == ["Title", "Next"]


def test_bm25_ranks_matching_chunk_first():
    cs = [Chunk(0, "a.md", "Cats", "cats purr " * 5), Chunk(1, "b.md", "CORS", "cors origins allow")]
    assert BM25(cs).search("allow cors origins")[0][0].path == "b.md"
    assert BM25(cs).search("zebra") == []


class Fake:
    def __init__(self, resp):
        self.resp, self.kw = resp, None
        self.beta = NS(messages=NS(create=self.create))

    def create(self, **kw):
        self.kw = kw
        return self.resp


SRC = [Chunk(0, "x.md", "X", "use Query(default=None)"), Chunk(1, "y.md", "Y", "other")]


def resp(text, stop="end_turn"):
    return NS(content=[NS(type="text", text=text)], stop_reason=stop, usage=NS(input_tokens=1000, output_tokens=100))


def test_ask_sends_sources_and_parses_citations():
    f = Fake(resp("Use Query [1], not [7]."))
    a = answer.ask(f, "optional?", SRC)
    content = f.kw["messages"][0]["content"]
    assert "[1] x.md — X" in content and "Question: optional?" in content
    assert f.kw["model"] == "claude-opus-5-5" and f.kw["fallbacks"] == "default"
    assert a.cited == [1]  # [7] is out of range and dropped
    assert abs(a.cost_usd - (1000 * 4 + 100 * 20) / 1e6) < 1e-12


def test_refusal_is_not_treated_as_an_answer():
    a = answer.ask(Fake(resp("", "refusal")), "q", SRC)
    assert a.stop_reason == "refusal" and a.cited == []
