import io
import logging
import pikepdf

from models import Color, Action

logger = logging.getLogger(__name__)

_TEXT_OPS = {'Tj', 'TJ', "'", '"'}
_PATH_FILL_OPS = {'f', 'F', 'f*'}
_PATH_STROKE_OPS = {'S', 's'}
_PATH_BOTH_OPS = {'B', 'B*', 'b', 'b*'}


def apply_mapping(pdf_bytes: bytes, mapping: dict) -> bytes:
    """Apply color→action mapping to all pages. Returns bytes of the modified PDF.
    The original PDF bytes are never modified."""
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            try:
                _process_page(pdf, page, mapping)
            except Exception as exc:
                logger.warning("Skipping page due to processing error: %s", exc)
        buf = io.BytesIO()
        pdf.save(buf)
        return buf.getvalue()


def _process_page(pdf, page, mapping: dict) -> None:
    instructions = list(pikepdf.parse_content_stream(page))
    new_instructions = []
    fill_color = Color(0, 0, 0)
    stroke_color = Color(0, 0, 0)

    for operands, operator in instructions:
        try:
            op = str(operator)
        except Exception:
            new_instructions.append((operands, operator))
            continue

        # --- Track current color state ---
        if op == 'rg':
            r, g, b = (float(o) for o in operands)
            fill_color = Color(round(r * 255), round(g * 255), round(b * 255))
            new_instructions.append((operands, operator))
        elif op == 'RG':
            r, g, b = (float(o) for o in operands)
            stroke_color = Color(round(r * 255), round(g * 255), round(b * 255))
            new_instructions.append((operands, operator))
        elif op == 'g':
            v = round(float(operands[0]) * 255)
            fill_color = Color(v, v, v)
            new_instructions.append((operands, operator))
        elif op == 'G':
            v = round(float(operands[0]) * 255)
            stroke_color = Color(v, v, v)
            new_instructions.append((operands, operator))
        elif op == 'k':
            c, m, y, k = (float(o) for o in operands)
            fill_color = _cmyk_to_rgb(c, m, y, k)
            new_instructions.append((operands, operator))
        elif op == 'K':
            c, m, y, k = (float(o) for o in operands)
            stroke_color = _cmyk_to_rgb(c, m, y, k)
            new_instructions.append((operands, operator))

        # --- Apply actions to drawing operators ---
        elif op in _TEXT_OPS:
            action = mapping.get(fill_color, Action.KEEP)
            new_instructions.extend(_handle_text(operands, operator, op, action))

        elif op in _PATH_FILL_OPS:
            action = mapping.get(fill_color, Action.KEEP)
            new_instructions.extend(_handle_path_fill(operands, operator, action))

        elif op in _PATH_STROKE_OPS:
            action = mapping.get(stroke_color, Action.KEEP)
            new_instructions.extend(_handle_path_stroke(operands, operator, action))

        elif op in _PATH_BOTH_OPS:
            fill_action = mapping.get(fill_color, Action.KEEP)
            stroke_action = mapping.get(stroke_color, Action.KEEP)
            new_instructions.extend(_handle_path_both(operands, operator, fill_action, stroke_action))

        else:
            new_instructions.append((operands, operator))

    new_stream = pikepdf.unparse_content_stream(new_instructions)
    page['/Contents'] = pdf.make_stream(new_stream)


def _black_rg():
    return ([pikepdf.Real(0), pikepdf.Real(0), pikepdf.Real(0)], pikepdf.Operator('rg'))


def _black_RG():
    return ([pikepdf.Real(0), pikepdf.Real(0), pikepdf.Real(0)], pikepdf.Operator('RG'))


def _handle_text(operands, operator, op_name: str, action: Action) -> list:
    if action == Action.KEEP:
        return [(operands, operator)]
    if action == Action.KEEP_BLACK:
        return [_black_rg(), (operands, operator)]
    # DELETE: replace string content with empty string
    if op_name == 'Tj':
        return [([pikepdf.String(b'')], operator)]
    # TJ, ', " — operand is an array
    return [([pikepdf.Array([pikepdf.String(b'')])], operator)]


def _handle_path_fill(operands, operator, action: Action) -> list:
    if action == Action.KEEP:
        return [(operands, operator)]
    if action == Action.KEEP_BLACK:
        return [_black_rg(), (operands, operator)]
    # DELETE
    return [([], pikepdf.Operator('n'))]


def _handle_path_stroke(operands, operator, action: Action) -> list:
    if action == Action.KEEP:
        return [(operands, operator)]
    if action == Action.KEEP_BLACK:
        return [_black_RG(), (operands, operator)]
    # DELETE
    return [([], pikepdf.Operator('n'))]


def _handle_path_both(operands, operator, fill_action: Action, stroke_action: Action) -> list:
    # If either color is deleted, suppress the entire drawing command
    if fill_action == Action.DELETE or stroke_action == Action.DELETE:
        return [([], pikepdf.Operator('n'))]
    result = []
    if fill_action == Action.KEEP_BLACK:
        result.append(_black_rg())
    if stroke_action == Action.KEEP_BLACK:
        result.append(_black_RG())
    result.append((operands, operator))
    return result


def _cmyk_to_rgb(c: float, m: float, y: float, k: float) -> Color:
    r = round(255 * (1 - c) * (1 - k))
    g = round(255 * (1 - m) * (1 - k))
    b = round(255 * (1 - y) * (1 - k))
    return Color(r, g, b)
