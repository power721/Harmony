#!/usr/bin/env bash
set -euo pipefail

rm -rf dist
uv build
uv run --with twine twine upload dist/*
