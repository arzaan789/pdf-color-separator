# PDF Color Separator

A macOS desktop app for **RISO printing color separation**. Open a multi-color PDF, assign each ink color an action (keep as black, delete, or keep as-is), preview the result live, and export one PDF per ink layer.

![PDF Color Separator screenshot placeholder]

## Download

Download the latest `.app` from the [Releases](../../releases) page. Unzip and drag to your Applications folder.

> **macOS note:** On first launch, right-click the app and choose **Open** to bypass the Gatekeeper warning (the app is not notarized).

## Usage

1. Click **Open PDF** and select your file
2. The detected ink colors appear in the left sidebar
3. *(Optional)* Drag the **Tolerance** slider to merge similar shades into one group
4. *(Optional)* Click **Pick Color**, then click anywhere on the preview to auto-select that color in the list
5. Select one or more colors (Cmd+click / Shift+click for multi-select)
6. Choose an action: **Keep → Black**, **Delete**, or **Keep as-is**
7. Click **Apply** to preview the result
8. Click **Export Layer** to save the modified PDF
9. Reconfigure for the next layer and repeat

## What it handles

- RGB, grayscale, and CMYK color operators in text and path objects
- Multi-page PDFs
- Mixed text + shape documents

## Out of scope (v1)

- Raster images inside the PDF (handle separately with Ghostscript)
- Gradients, patterns, spot colors

## Run from source

```bash
git clone https://github.com/arzaan789/pdf-color-separator.git
cd pdf-color-separator
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

**Requirements:** Python 3.11+, macOS (cross-platform capable)

## Build the app yourself

```bash
pip install pyinstaller
pyinstaller PDF\ Color\ Separator.spec
# Output: dist/PDF Color Separator.app
```
