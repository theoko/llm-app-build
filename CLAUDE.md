---
repo: supportbot (llm-app-build)
owner: theoko
---
# supportbot

Code for a no-host YouTube build series: one LLM support assistant over the FastAPI docs, one episode per release, tagged `epNN`.

## NON-NEGOTIABLES
- Everything shown in a video comes from a real run saved under `runs/` or from the tagged source. Never invent model output.
- Each episode's code must run at its tag; tests use a fake client and no network (`.venv/bin/pytest -q`).
- No API keys in the repo. The SDK reads `ANTHROPIC_API_KEY` or an `ant auth login` profile.
- Nothing is pushed or made public without the owner's yes. The public repo github.com/theoko/llm-app-build (created 2026-11-24, main + tag ep01) holds episode 1 only; later work stays local until he says push.
- Credit the FastAPI docs (MIT) in README and in every video description.
