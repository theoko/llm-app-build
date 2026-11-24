"""Episode 1: answer from the retrieved chunks only, with numbered citations."""
import re
from dataclasses import dataclass, field

import anthropic

from .corpus import Chunk

MODEL = "claude-opus-5-5"
PRICE_IN, PRICE_OUT = 4 / 1e6, 20 / 1e6  # USD per token, Claude Opus 5.5 list price
NO_ANSWER = "I don't know based on the docs."
SYSTEM = (
    "You answer questions about FastAPI using only the numbered sources you are given. "
    "Cite every claim with its source number in square brackets, like [2]. "
    "Keep answers under 120 words and include a short code example when the sources have one. "
    f"If the sources do not contain the answer, reply exactly: {NO_ANSWER}"
)
CITE = re.compile(r"\[(\d+)\]")


@dataclass
class Answer:
    text: str
    sources: list[Chunk]
    cited: list[int] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str = ""

    @property
    def cost_usd(self) -> float:
        # shortcut: Opus 5.5 rates only, wrong if the server fell back to another model.
        return self.input_tokens * PRICE_IN + self.output_tokens * PRICE_OUT


def build_prompt(question: str, sources: list[Chunk]) -> str:
    blocks = [f"[{n}] {c.path} — {c.heading}\n{c.text}" for n, c in enumerate(sources, 1)]
    return "<sources>\n" + "\n\n".join(blocks) + f"\n</sources>\n\nQuestion: {question}"


def ask(client: anthropic.Anthropic, question: str, sources: list[Chunk]) -> Answer:
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low"},
        system=SYSTEM,
        messages=[{"role": "user", "content": build_prompt(question, sources)}],
    )
    usage = (resp.usage.input_tokens, resp.usage.output_tokens)
    if resp.stop_reason == "refusal":
        return Answer("(the model declined to answer)", sources, [], *usage, "refusal")
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    cited = sorted({int(n) for n in CITE.findall(text) if 1 <= int(n) <= len(sources)})
    return Answer(text, sources, cited, *usage, resp.stop_reason)
