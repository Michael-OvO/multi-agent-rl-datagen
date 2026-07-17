#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$ROOT/docs/multi_agent_rl_data_generation_zh.tex"
OUT="$ROOT/output/pdf"
BUILD="$ROOT/tmp/pdfs/report-build"

mkdir -p "$OUT" "$BUILD"
latexmk -xelatex -interaction=nonstopmode -halt-on-error \
  -outdir="$BUILD" "$SOURCE"
cp "$BUILD/multi_agent_rl_data_generation_zh.pdf" "$OUT/"

echo "wrote $OUT/multi_agent_rl_data_generation_zh.pdf"
