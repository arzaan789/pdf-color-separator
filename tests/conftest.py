import io
import pikepdf
import pytest


@pytest.fixture
def make_pdf():
    """Factory that builds a minimal valid PDF from raw content stream bytes.
    Returns the PDF as bytes."""
    def _make(content_stream: bytes) -> bytes:
        pdf = pikepdf.Pdf.new()
        page_dict = pikepdf.Dictionary(
            Type=pikepdf.Name('/Page'),
            MediaBox=pikepdf.Array([0, 0, 612, 792]),
            Contents=pdf.make_stream(content_stream),
            Resources=pikepdf.Dictionary(
                ProcSet=pikepdf.Array([pikepdf.Name('/PDF'), pikepdf.Name('/Text')]),
            ),
        )
        pdf.pages.append(page_dict)
        buf = io.BytesIO()
        pdf.save(buf)
        return buf.getvalue()
    return _make
