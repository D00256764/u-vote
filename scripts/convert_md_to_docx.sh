#!/usr/bin/env bash
# Local helper to convert final markdown reports to .docx using Docker + Pandoc
# Usage: ./scripts/convert_md_to_docx.sh [product|platform|all]

set -euo pipefail
MODE=${1:-all}
ROOT=$(cd "$(dirname "$0")/.." && pwd)

convert() {
  local src="$1"
  local out="$2"
  echo "Converting $src -> $out"
  docker run --rm -v "$ROOT":/workspace -w /workspace pandoc/latex:2.21 \
    pandoc "$src" -o "$out" --reference-doc=docs/docx-reference.docx || return 1
}

case "$MODE" in
  product)
    convert docs/Product_Report_Final.md docs/Product_Report_Final.docx
    ;;
  platform)
    convert docs/Platform_Report_Final.md docs/Platform_Report_Final.docx
    ;;
  all)
    convert docs/Product_Report_Final.md docs/Product_Report_Final.docx
    convert docs/Platform_Report_Final.md docs/Platform_Report_Final.docx
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac

echo "Done. Output files are in docs/"
