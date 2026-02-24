# Conversion Instructions — Markdown -> Word (.docx)

This document explains how to convert the final Product and Platform markdown reports to `.docx` files suitable for submission. Two methods are provided: (A) local using Docker+Pandoc and (B) automated via GitHub Actions.

## Prerequisites (local)
- Docker installed and running (macOS: use Docker Desktop)
- The repository checked out with the final markdown files present at:
  - `docs/Product_Report_Final.md`
  - `docs/Platform_Report_Final.md`
- Optional: `docs/docx-reference.docx` — a Word template with preferred styles. If omitted, Pandoc's default styling is used.

## Local conversion (recommended for immediate use)
Run the helper script from the repo root (zsh):

```bash
# Convert both reports
./scripts/convert_md_to_docx.sh all

# Convert product only
./scripts/convert_md_to_docx.sh product

# Convert platform only
./scripts/convert_md_to_docx.sh platform
```

The script uses the `pandoc/latex` Docker image, mounts the repo and runs Pandoc to produce `.docx` files in `docs/`.

## GitHub Actions (CI) conversion
A GitHub Action is included at `.github/workflows/generate-docx.yml`. It runs when manually dispatched or on push to files under `docs/**` and will:
1. Run a Docker container with Pandoc
2. Convert the two final markdown files to `.docx`
3. Upload the resulting `.docx` files as workflow artifacts

To run manually:
- On GitHub, go to Actions → "Generate Docs (.docx)" → Run workflow.
- After completion, download the `docs-docx` artifact.

## Reference DOCX (optional)
You can supply a `docs/docx-reference.docx` to control default styles, fonts, heading styles, and a title page layout. Place your institution template at that path before running the conversion script or trigger the workflow.

## Metadata / Title page
The `Product_Report_Final.md` and `Platform_Report_Final.md` include a title page block at the top. Edit these fields directly in the markdown if you want:
- Project title
- Student name / ID
- Module and assessor info
- Date

## Troubleshooting
- If Docker is not available, install Pandoc locally (macOS: `brew install pandoc`) and run `pandoc` with similar arguments.
- If the generated .docx loses some CSS-like formatting, provide `docx-reference.docx` with preferred styles.

