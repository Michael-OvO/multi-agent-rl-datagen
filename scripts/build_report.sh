#!/bin/bash
# Build the Chinese report, and refuse to ship a PDF that lost something.
#
# `-halt-on-error` stops on TeX errors. It does not stop on the two failures that
# actually reach the reader, because XeLaTeX treats both as warnings:
#
#   * a character the font does not have is dropped from the page in silence.
#     Fandol has no 啰 (U+5570); the sentence rendered as "只是变得更" and stopped,
#     and the log said so on a line nobody read. That is the same shape as the
#     API catalog this project truncated past the verb the task needed.
#   * an overfull box runs text into the margin.
#
# So the build greps its own log. A check that only counts overfull boxes is a
# check chosen because it passes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$ROOT/docs/multi_agent_rl_data_generation_zh.tex"
OUT="$ROOT/output/pdf"
BUILD="$ROOT/tmp/pdfs/report-build"
LOG="$BUILD/multi_agent_rl_data_generation_zh.log"

mkdir -p "$OUT" "$BUILD"
latexmk -xelatex -interaction=nonstopmode -halt-on-error \
  -outdir="$BUILD" "$SOURCE"

fail=0

if grep -q "Missing character" "$LOG"; then
  echo
  echo "REFUSING TO SHIP: characters were dropped from the PDF." >&2
  grep -o "There is no [^ ]* (U+[0-9A-F]*) in font [^/]*" "$LOG" | sort -u | sed 's/^/  /' >&2
  echo "  -> the font has no glyph. Rewrite the word, or add a fallback font." >&2
  fail=1
fi

if grep -q "Overfull \\\\hbox" "$LOG"; then
  echo
  echo "REFUSING TO SHIP: text runs into the margin." >&2
  grep "Overfull \\\\hbox" "$LOG" | sed 's/^/  /' >&2
  fail=1
fi

[ "$fail" -eq 0 ] || exit 1

cp "$BUILD/multi_agent_rl_data_generation_zh.pdf" "$OUT/"
echo "wrote $OUT/multi_agent_rl_data_generation_zh.pdf"
