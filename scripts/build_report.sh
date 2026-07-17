#!/bin/bash
# Build the reports, and refuse to ship a PDF that lost something.
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
#
# Both gates run against every report. The English one uses Latin Modern, which
# has every glyph it asks for, so its "Missing character" check will realistically
# never fire -- that is not a reason to skip it. A gate you drop from the document
# least likely to trip it is a gate you have only ever run where it passes.
#
#   ./scripts/build_report.sh            # every report
#   ./scripts/build_report.sh zh         # just docs/*_zh.tex
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/output/pdf"
STEM="multi_agent_rl_data_generation"

targets=("$@")
[ ${#targets[@]} -eq 0 ] && targets=(zh en)

mkdir -p "$OUT"
fail=0

for lang in "${targets[@]}"; do
  source_tex="$ROOT/docs/${STEM}_${lang}.tex"
  build="$ROOT/tmp/pdfs/report-build-${lang}"
  log="$build/${STEM}_${lang}.log"

  if [ ! -f "$source_tex" ]; then
    echo "no such report: $source_tex" >&2
    exit 1
  fi

  echo "=== building ${STEM}_${lang} ==="
  mkdir -p "$build"
  latexmk -xelatex -interaction=nonstopmode -halt-on-error \
    -outdir="$build" "$source_tex"

  if grep -q "Missing character" "$log"; then
    echo
    echo "REFUSING TO SHIP ($lang): characters were dropped from the PDF." >&2
    grep -o "There is no [^ ]* (U+[0-9A-F]*) in font [^/]*" "$log" | sort -u | sed 's/^/  /' >&2
    echo "  -> the font has no glyph. Rewrite the word, or add a fallback font." >&2
    fail=1
  fi

  if grep -q "Overfull \\\\hbox" "$log"; then
    echo
    echo "REFUSING TO SHIP ($lang): text runs into the margin." >&2
    grep "Overfull \\\\hbox" "$log" | sed 's/^/  /' >&2
    fail=1
  fi

  [ "$fail" -eq 0 ] || exit 1

  cp "$build/${STEM}_${lang}.pdf" "$OUT/"
  echo "wrote $OUT/${STEM}_${lang}.pdf"
  echo
done
