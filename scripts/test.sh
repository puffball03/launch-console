#!/bin/sh
# Runs the back-end and front-end suites; fails if either fails.
set -e
echo "== Back end (pytest) =="
cd /app/backend && .venv/bin/pytest
echo "== Front end (vitest) =="
cd /app/frontend && node node_modules/vitest/vitest.mjs run
