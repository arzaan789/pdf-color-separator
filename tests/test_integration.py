import io
import sys
sys.path.insert(0, 'src')

import pikepdf
from models import Color, Action
from pdf_parser import extract_colors
from pdf_editor import apply_mapping


def _make_two_color_pdf() -> bytes:
    """Build a PDF with red text and blue text on the same page."""
    content = (
        b"1 0 0 rg\n(Red text) Tj\n"
        b"0 0 1 rg\n(Blue text) Tj\n"
    )
    pdf = pikepdf.Pdf.new()
    from pikepdf import Dictionary, Name, Array, Page
    page_dict = Dictionary(
        Type=Name('/Page'),
        MediaBox=Array([0, 0, 612, 792]),
        Contents=pdf.make_stream(content),
        Resources=Dictionary(
            ProcSet=Array([Name('/PDF'), Name('/Text')]),
        ),
    )
    pdf.pages.append(Page(page_dict))
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def _tj_contents(pdf_bytes: bytes) -> list[bytes]:
    """Return the raw bytes content of every Tj operand from the first page."""
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        instructions = list(pikepdf.parse_content_stream(pdf.pages[0]))
    return [bytes(ops[0]) for ops, op in instructions if str(op) == 'Tj']


def test_red_layer_blue_text_is_emptied():
    """Red layer: red→black, blue→delete. Blue Tj should be empty string."""
    pdf_bytes = _make_two_color_pdf()
    colors = extract_colors(pdf_bytes)
    assert Color(255, 0, 0) in colors
    assert Color(0, 0, 255) in colors

    mapping = {
        Color(255, 0, 0): Action.KEEP_BLACK,
        Color(0, 0, 255): Action.DELETE,
    }
    result = apply_mapping(pdf_bytes, mapping)

    contents = _tj_contents(result)
    assert b'Red text' in contents, "Red text should be preserved"
    assert b'' in contents, "Blue text Tj should be replaced with empty string"
    assert b'Blue text' not in contents, "Blue text content should be removed"


def test_blue_layer_red_text_is_emptied():
    """Blue layer: blue→black, red→delete. Red Tj should be empty string."""
    pdf_bytes = _make_two_color_pdf()
    mapping = {
        Color(255, 0, 0): Action.DELETE,
        Color(0, 0, 255): Action.KEEP_BLACK,
    }
    result = apply_mapping(pdf_bytes, mapping)

    contents = _tj_contents(result)
    assert b'Blue text' in contents, "Blue text should be preserved"
    assert b'' in contents, "Red text Tj should be replaced with empty string"
    assert b'Red text' not in contents, "Red text content should be removed"


def test_both_layers_are_valid_pdfs():
    pdf_bytes = _make_two_color_pdf()
    for mapping in [
        {Color(255, 0, 0): Action.KEEP_BLACK, Color(0, 0, 255): Action.DELETE},
        {Color(255, 0, 0): Action.DELETE, Color(0, 0, 255): Action.KEEP_BLACK},
    ]:
        result = apply_mapping(pdf_bytes, mapping)
        with pikepdf.open(io.BytesIO(result)) as pdf:
            assert len(pdf.pages) == 1
