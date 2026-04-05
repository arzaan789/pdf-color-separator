import fitz  # PyMuPDF
from PyQt6.QtGui import QImage, QPixmap


def render_page(pdf_bytes: bytes, page_number: int = 0, dpi: int = 150) -> QPixmap:
    """Render a single page of a PDF to a QPixmap.

    Args:
        pdf_bytes: PDF file contents as bytes.
        page_number: Zero-based page index.
        dpi: Render resolution (150 is good for preview).

    Returns:
        QPixmap of the rendered page.

    Raises:
        ValueError: If page_number is out of range.
    """
    with fitz.open(stream=pdf_bytes, filetype='pdf') as doc:
        if page_number >= len(doc):
            raise ValueError(
                f"Page {page_number} out of range — PDF has {len(doc)} page(s)"
            )
        page = doc[page_number]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format.Format_RGB888,
        )
        return QPixmap.fromImage(img)
