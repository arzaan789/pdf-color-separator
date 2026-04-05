import sys
sys.path.insert(0, 'src')

from models import Color
from pdf_parser import extract_colors


def test_extracts_rgb_fill_color(make_pdf):
    # 1 0 0 rg = red fill; Tj = text draw
    pdf_bytes = make_pdf(b"1 0 0 rg\n(Hello) Tj\n")
    colors = extract_colors(pdf_bytes)
    assert Color(255, 0, 0) in colors


def test_extracts_rgb_stroke_color(make_pdf):
    # 0 0 1 RG = blue stroke; S = stroke path
    pdf_bytes = make_pdf(b"0 0 1 RG\n0 0 100 100 re\nS\n")
    colors = extract_colors(pdf_bytes)
    assert Color(0, 0, 255) in colors


def test_extracts_grayscale_fill(make_pdf):
    # 0.5 g = 50% gray fill; f = fill path
    pdf_bytes = make_pdf(b"0.5 g\n0 0 100 100 re\nf\n")
    colors = extract_colors(pdf_bytes)
    assert Color(128, 128, 128) in colors


def test_extracts_cmyk_fill(make_pdf):
    # 0 1 1 0 k = C=0 M=1 Y=1 K=0 → red in RGB
    pdf_bytes = make_pdf(b"0 1 1 0 k\n(Hi) Tj\n")
    colors = extract_colors(pdf_bytes)
    assert Color(255, 0, 0) in colors


def test_multiple_colors_in_one_page(make_pdf):
    content = (
        b"1 0 0 rg\n(Red) Tj\n"
        b"0 0 1 rg\n(Blue) Tj\n"
    )
    pdf_bytes = make_pdf(content)
    colors = extract_colors(pdf_bytes)
    assert Color(255, 0, 0) in colors
    assert Color(0, 0, 255) in colors


def test_returns_set(make_pdf):
    # Same color used twice → appears once
    content = b"1 0 0 rg\n(A) Tj\n1 0 0 rg\n(B) Tj\n"
    pdf_bytes = make_pdf(content)
    colors = extract_colors(pdf_bytes)
    assert isinstance(colors, set)
    red_count = sum(1 for c in colors if c == Color(255, 0, 0))
    assert red_count == 1
