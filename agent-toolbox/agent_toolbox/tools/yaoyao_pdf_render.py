"""Yaoyao PDF Render Service — render PDF pages to PIL Images.

Python rewrite of PaddlePdfOcrApp/Services/PdfRenderService.cs.
Uses pypdfium2 (PDFium binding) instead of C# Docnet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


@dataclass
class PdfPageData:
    """Mirrors PaddlePdfOcrApp.Models.PdfPageData."""
    image: Image.Image
    width: int
    height: int
    page_index: int
    page_count: int


class PdfRenderService:
    """Render PDF pages to PIL Images at a target size.

    Equivalent to PaddlePdfOcrApp.Services.PdfRenderService.
    """

    def render_page(
        self,
        pdf_path: str | Path,
        page_index: int,
        render_width: int,
        render_height: int,
    ) -> PdfPageData:
        if render_width <= 0 or render_height <= 0:
            raise ValueError("Render dimensions must be positive.")

        import pypdfium2 as pdfium

        path = str(pdf_path)
        pdf = pdfium.PdfDocument(path)

        page_count = len(pdf)
        if page_count <= 0:
            pdf.close()
            raise ValueError("PDF has no readable pages.")

        if page_index < 0 or page_index >= page_count:
            pdf.close()
            raise IndexError(f"Page index {page_index} out of range (0..{page_count - 1}).")

        page = pdf[page_index]

        # Get source dimensions (in PDF points).
        source_width = max(1, page.get_width())
        source_height = max(1, page.get_height())

        # Calculate scale to fit within render box, maintaining aspect ratio.
        scale = min(render_width / source_width, render_height / source_height)
        target_width = max(1, int(round(source_width * scale)))
        target_height = max(1, int(round(source_height * scale)))

        # Render at the target scale.
        # pypdfium2 scale is relative to PDF points (1.0 = 72 DPI).
        pil_image = page.render(scale=scale).to_pil()

        page.close()
        pdf.close()

        return PdfPageData(
            image=pil_image,
            width=pil_image.width,
            height=pil_image.height,
            page_index=page_index,
            page_count=page_count,
        )

    def get_page_count(self, pdf_path: str | Path) -> int:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(pdf_path))
        count = len(pdf)
        pdf.close()
        return count

    def render_page_to_file(
        self,
        pdf_path: str | Path,
        page_index: int,
        output_path: str | Path,
        render_width: int = 2000,
        render_height: int = 2800,
        quality: int = 85,
    ) -> str:
        """Render a page and save as JPEG.  Returns the output path."""
        page_data = self.render_page(pdf_path, page_index, render_width, render_height)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        page_data.image.save(out, "JPEG", quality=quality)
        return str(out)


# ── module-level singleton ──────────────────────────────────────

_pdf_render_service: PdfRenderService | None = None


def get_pdf_render_service() -> PdfRenderService:
    global _pdf_render_service
    if _pdf_render_service is None:
        _pdf_render_service = PdfRenderService()
    return _pdf_render_service
