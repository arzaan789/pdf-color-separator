import io
import sys
sys.path.insert(0, 'src')

import pikepdf
from models import Color, Action
from pdf_editor import apply_mapping


def _get_instructions(pdf_bytes: bytes) -> list:
    """Parse content stream instructions from the first page."""
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        return list(pikepdf.parse_content_stream(pdf.pages[0]))


def _op_names(instructions) -> list[str]:
    return [str(op) for _, op in instructions]


def _last_rg_before_tj(instructions) -> list[float] | None:
    """Return the operands of the last rg operator before the first Tj."""
    rg_ops = []
    for operands, operator in instructions:
        op = str(operator)
        if op == 'rg':
            rg_ops.append([float(o) for o in operands])
        elif op == 'Tj':
            return rg_ops[-1] if rg_ops else None
    return None


def test_keep_black_inserts_black_rg_before_text(make_pdf):
    pdf_bytes = make_pdf(b"1 0 0 rg\n(Hello) Tj\n")
    mapping = {Color(255, 0, 0): Action.KEEP_BLACK}

    result = apply_mapping(pdf_bytes, mapping)

    instructions = _get_instructions(result)
    last_rg = _last_rg_before_tj(instructions)
    assert last_rg == [0.0, 0.0, 0.0], f"Expected black rg, got {last_rg}"


def test_delete_replaces_text_with_empty_string(make_pdf):
    pdf_bytes = make_pdf(b"1 0 0 rg\n(Hello) Tj\n")
    mapping = {Color(255, 0, 0): Action.DELETE}

    result = apply_mapping(pdf_bytes, mapping)

    instructions = _get_instructions(result)
    tj_instructions = [(ops, op) for ops, op in instructions if str(op) == 'Tj']
    assert tj_instructions, "Tj operator should still be present"
    ops, _ = tj_instructions[0]
    assert bytes(ops[0]) == b'', f"Expected empty string operand, got {ops[0]}"


def test_delete_replaces_path_fill_with_n(make_pdf):
    pdf_bytes = make_pdf(b"1 0 0 rg\n0 0 100 100 re\nf\n")
    mapping = {Color(255, 0, 0): Action.DELETE}

    result = apply_mapping(pdf_bytes, mapping)

    ops = _op_names(_get_instructions(result))
    assert 'n' in ops, "Expected 'n' operator for deleted fill path"
    assert 'f' not in ops, "Original 'f' should be replaced"


def test_keep_leaves_operators_unchanged(make_pdf):
    pdf_bytes = make_pdf(b"0 0 1 rg\n(World) Tj\n")
    mapping = {Color(0, 0, 255): Action.KEEP}

    result = apply_mapping(pdf_bytes, mapping)

    instructions = _get_instructions(result)
    last_rg = _last_rg_before_tj(instructions)
    assert last_rg == [0.0, 0.0, 1.0], f"Expected blue preserved, got {last_rg}"


def test_unmapped_color_defaults_to_keep(make_pdf):
    pdf_bytes = make_pdf(b"0 1 0 rg\n(Green) Tj\n")
    mapping = {}  # no mapping at all

    result = apply_mapping(pdf_bytes, mapping)

    instructions = _get_instructions(result)
    last_rg = _last_rg_before_tj(instructions)
    assert last_rg == [0.0, 1.0, 0.0], f"Unmapped color should be kept, got {last_rg}"


def test_apply_mapping_returns_valid_pdf_bytes(make_pdf):
    pdf_bytes = make_pdf(b"1 0 0 rg\n(Test) Tj\n")
    mapping = {Color(255, 0, 0): Action.KEEP_BLACK}

    result = apply_mapping(pdf_bytes, mapping)

    # Should be loadable by pikepdf without error
    with pikepdf.open(io.BytesIO(result)) as pdf:
        assert len(pdf.pages) == 1
