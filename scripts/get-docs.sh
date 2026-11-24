#!/bin/sh
# Fetch the FastAPI docs (MIT License) at the commit this series pins.
set -e
COMMIT=05e6df7e906c3decba377c37548019973f40bf15
cd "$(dirname "$0")/.." && mkdir -p corpus-src && cd corpus-src
[ -d .git ] || { git init -q && git remote add origin https://github.com/fastapi/fastapi; }
git sparse-checkout set docs/en/docs
git fetch -q --depth 1 origin "$COMMIT" && git checkout -q FETCH_HEAD
