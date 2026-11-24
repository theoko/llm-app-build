"""Episode 1: split the docs into chunks, one per heading."""
import re
from dataclasses import dataclass
from pathlib import Path

HEADING = re.compile(r"^(#{1,3}) +(.+?)\s*(\{.*\})?$")
MAX_CHARS = 2000


@dataclass
class Chunk:
    id: int
    path: str
    heading: str
    text: str


def split_markdown(md: str) -> list[tuple[str, str]]:
    """Return (heading, body) pairs. Headings inside ``` code fences are ignored."""
    sections, heading, lines, in_code = [], "", [], False
    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        m = None if in_code else HEADING.match(line)
        if m:
            sections.append((heading, "\n".join(lines).strip()))
            heading, lines = m.group(2), []
        else:
            lines.append(line)
    sections.append((heading, "\n".join(lines).strip()))
    return [(h, b) for h, b in sections if len(b) >= 50]


def _cap(body: str) -> list[str]:
    """Split a long section on blank lines so no piece is far over MAX_CHARS."""
    parts, cur = [], ""
    for para in body.split("\n\n"):
        if cur and len(cur) + len(para) > MAX_CHARS:
            parts.append(cur)
            cur = ""
        cur = f"{cur}\n\n{para}" if cur else para
    return parts + [cur] if cur else parts


def load(docs_dir: Path) -> list[Chunk]:
    chunks = []
    for f in sorted(docs_dir.rglob("*.md")):
        rel = f.relative_to(docs_dir).as_posix()
        for heading, body in split_markdown(f.read_text(encoding="utf-8")):
            for piece in _cap(body):
                chunks.append(Chunk(len(chunks), rel, heading, piece))
    return chunks
