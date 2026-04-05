import io
import logging
import pikepdf

from models import Color

logger = logging.getLogger(__name__)

# Operators that draw using the current fill color
_TEXT_OPS = {'Tj', 'TJ', "'", '"'}
_PATH_FILL_OPS = {'f', 'F', 'f*'}
_PATH_BOTH_OPS = {'B', 'B*', 'b', 'b*'}
# Operators that draw using the current stroke color
_PATH_STROKE_OPS = {'S', 's'}


def extract_colors(pdf_bytes: bytes) -> set[Color]:
    """Return the set of unique colors used in text and path objects across all pages."""
    colors: set[Color] = set()
    try:
        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                try:
                    colors.update(_extract_from_page(page))
                except Exception as exc:
                    logger.warning("Skipping page due to parse error: %s", exc)
    except pikepdf.PdfError as exc:
        raise ValueError(f"Cannot open PDF: {exc}") from exc
    return colors


def _extract_from_page(page) -> set[Color]:
    colors: set[Color] = set()
    fill_color = Color(0, 0, 0)
    stroke_color = Color(0, 0, 0)

    for operands, operator in pikepdf.parse_content_stream(page):
        try:
            op = str(operator)
        except Exception:
            continue

        if op == 'rg':
            r, g, b = (float(o) for o in operands)
            fill_color = Color(round(r * 255), round(g * 255), round(b * 255))
        elif op == 'RG':
            r, g, b = (float(o) for o in operands)
            stroke_color = Color(round(r * 255), round(g * 255), round(b * 255))
        elif op == 'g':
            v = round(float(operands[0]) * 255)
            fill_color = Color(v, v, v)
        elif op == 'G':
            v = round(float(operands[0]) * 255)
            stroke_color = Color(v, v, v)
        elif op == 'k':
            c, m, y, k = (float(o) for o in operands)
            fill_color = _cmyk_to_rgb(c, m, y, k)
        elif op == 'K':
            c, m, y, k = (float(o) for o in operands)
            stroke_color = _cmyk_to_rgb(c, m, y, k)
        elif op in _TEXT_OPS or op in _PATH_FILL_OPS or op in _PATH_BOTH_OPS:
            colors.add(fill_color)
        elif op in _PATH_STROKE_OPS:
            colors.add(stroke_color)

    return colors


def _cmyk_to_rgb(c: float, m: float, y: float, k: float) -> Color:
    r = round(255 * (1 - c) * (1 - k))
    g = round(255 * (1 - m) * (1 - k))
    b = round(255 * (1 - y) * (1 - k))
    return Color(r, g, b)
