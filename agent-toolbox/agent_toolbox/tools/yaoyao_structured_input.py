"""Yaoyao Structured Input — batch OCR orchestration across PDF pages.

Python rewrite of PaddlePdfOcrApp/Services/OcrWorkflowService.cs.
Orchestrates PDF rendering + region-based OCR + field mapping.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from ..config import settings
from .yaoyao_ocr_engine import get_engine
from .yaoyao_pdf_render import PdfPageData, get_pdf_render_service


@dataclass
class PageRecognitionResult:
    """Mirrors PaddlePdfOcrApp.Models.PageRecognitionResult."""
    page_number: int
    values: dict[str, str] = field(default_factory=dict)


@dataclass
class FieldCandidate:
    """A single recognized field with confidence metadata."""
    field_name: str
    value: str
    confidence: float = 0.0
    source_region: str = ""
    page_number: int = 1


@dataclass
class StructuredExtractResult:
    """Complete result of a structured extraction operation."""
    draft_id: str
    preview_image_path: str | None = None
    pages: list[PageRecognitionResult] = field(default_factory=list)
    field_candidates: list[FieldCandidate] = field(default_factory=list)
    page_count: int = 0
    elapsed_seconds: float = 0.0


class OcrWorkflowService:
    """Batch OCR orchestration with progress reporting and cancellation.

    Equivalent to PaddlePdfOcrApp.Services.OcrWorkflowService.
    """

    def __init__(self) -> None:
        self._pdf_render = get_pdf_render_service()
        self._ocr_engine = get_engine()

    def recognize_single_page(
        self,
        page: PdfPageData,
        regions: list[dict[str, Any]],
    ) -> PageRecognitionResult:
        """Recognize all regions on a single rendered page."""
        result = PageRecognitionResult(page_number=page.page_index + 1)
        for region in regions:
            name = region.get("name", f"region_{region.get('x', 0)}_{region.get('y', 0)}")
            try:
                text = self._ocr_engine.recognize(page.image, region)
                result.values[name] = text
            except Exception as exc:
                result.values[name] = f"[recognition_failed]{exc}"
        return result

    def recognize_all_pages(
        self,
        pdf_path: str | Path,
        regions: list[dict[str, Any]],
        render_width: int = 2000,
        render_height: int = 2800,
        progress_callback: Callable[[int, int], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
        max_pages: int = 0,
    ) -> list[PageRecognitionResult]:
        """Recognize regions across all pages of a PDF.

        *progress_callback* receives (current_page, total_pages).
        *cancel_check* returns True if the operation should be cancelled.
        *max_pages* limits the number of pages (0 = all).
        """
        results: list[PageRecognitionResult] = []

        # Render and recognize the first page to get page count.
        first_page = self._pdf_render.render_page(pdf_path, 0, render_width, render_height)
        page_count = first_page.page_count
        if max_pages > 0:
            page_count = min(page_count, max_pages)

        first_result = self.recognize_single_page(first_page, regions)
        results.append(first_result)
        if progress_callback:
            progress_callback(1, page_count)

        for page_index in range(1, page_count):
            if cancel_check and cancel_check():
                break

            try:
                page = self._pdf_render.render_page(pdf_path, page_index, render_width, render_height)
                page_result = self.recognize_single_page(page, regions)
            except Exception as exc:
                page_result = PageRecognitionResult(page_number=page_index + 1)
                for region in regions:
                    name = region.get("name", "region")
                    page_result.values[name] = f"[recognition_failed]{exc}"

            results.append(page_result)
            if progress_callback:
                progress_callback(page_index + 1, page_count)

        return results

    def structured_extract(
        self,
        file_path: str | Path,
        regions: list[dict[str, Any]] | None = None,
        page_index: int | None = None,
        template_id: str | None = None,
        case_id: int | None = None,
        render_width: int = 2000,
        render_height: int = 2800,
    ) -> StructuredExtractResult:
        """Full structured extraction pipeline.

        If *regions* is None or empty, performs full-page OCR (no region cropping).
        If *page_index* is specified, only processes that page; otherwise all pages.
        """
        start_time = time.time()
        draft_id = f"draft_{uuid.uuid4().hex[:12]}"
        path = Path(file_path)

        is_image = path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}

        field_candidates: list[FieldCandidate] = []
        pages: list[PageRecognitionResult] = []
        preview_path: str | None = None
        page_count = 1

        if is_image:
            # Direct image OCR.
            with Image.open(path) as img:
                img_copy = img.copy()
                preview_path = self._save_preview_image(img_copy, draft_id, 1)
                if regions:
                    page_result = PageRecognitionResult(page_number=1)
                    for region in regions:
                        name = region.get("name", "field")
                        try:
                            text = self._ocr_engine.recognize(img_copy, region)
                            page_result.values[name] = text
                            field_candidates.append(FieldCandidate(
                                field_name=name,
                                value=text,
                                confidence=0.85,
                                source_region=f"{region.get('x',0)},{region.get('y',0)}",
                                page_number=1,
                            ))
                        except Exception as exc:
                            page_result.values[name] = f"[recognition_failed]{exc}"
                    pages.append(page_result)
                else:
                    text = self._ocr_engine.recognize_file(path, fast_mode=False)
                    page_result = PageRecognitionResult(page_number=1)
                    page_result.values["full_text"] = text
                    field_candidates.append(FieldCandidate(
                        field_name="full_text",
                        value=text,
                        confidence=0.8,
                        page_number=1,
                    ))
                    pages.append(page_result)
        else:
            # PDF OCR.
            if page_index is not None:
                page_data = self._pdf_render.render_page(path, page_index, render_width, render_height)
                page_count = page_data.page_count
                preview_path = self._save_preview_image(page_data.image, draft_id, page_index + 1)
                if regions:
                    page_result = self.recognize_single_page(page_data, regions)
                else:
                    text = self._ocr_engine.recognize_file(
                        self._save_temp_image(page_data.image), fast_mode=False
                    )
                    page_result = PageRecognitionResult(page_number=page_index + 1)
                    page_result.values["full_text"] = text
                pages.append(page_result)

                for name, value in page_result.values.items():
                    if not name.startswith("[") and value and not value.startswith("["):
                        field_candidates.append(FieldCandidate(
                            field_name=name,
                            value=value,
                            confidence=0.85,
                            page_number=page_index + 1,
                        ))
            else:
                all_pages = self.recognize_all_pages(
                    path, regions or [], render_width, render_height,
                    max_pages=50,
                )
                if all_pages:
                    preview_page = self._pdf_render.render_page(path, 0, render_width, render_height)
                    preview_path = self._save_preview_image(preview_page.image, draft_id, 1)
                pages.extend(all_pages)
                page_count = len(all_pages)
                for pr in all_pages:
                    for name, value in pr.values.items():
                        if not name.startswith("[") and value and not value.startswith("["):
                            field_candidates.append(FieldCandidate(
                                field_name=name,
                                value=value,
                                confidence=0.85,
                                page_number=pr.page_number,
                            ))

        elapsed = time.time() - start_time

        return StructuredExtractResult(
            draft_id=draft_id,
            preview_image_path=preview_path,
            pages=pages,
            field_candidates=field_candidates,
            page_count=page_count,
            elapsed_seconds=round(elapsed, 2),
        )

    def _save_temp_image(self, image: Image.Image) -> Path:
        """Save a PIL Image to a temp file for file-based OCR."""
        import tempfile

        tmp = Path(tempfile.mktemp(suffix=".png"))
        image.save(tmp, "PNG")
        return tmp

    def _save_preview_image(self, image: Image.Image, draft_id: str, page_number: int) -> str:
        previews_dir = settings.yaoyao_work_dir / "previews"
        previews_dir.mkdir(parents=True, exist_ok=True)
        preview_path = previews_dir / f"{draft_id}_p{page_number}.jpg"
        image.save(preview_path, "JPEG", quality=85)
        return str(preview_path)


# ── module-level singleton ──────────────────────────────────────

_workflow_service: OcrWorkflowService | None = None


def get_workflow_service() -> OcrWorkflowService:
    global _workflow_service
    if _workflow_service is None:
        _workflow_service = OcrWorkflowService()
    return _workflow_service
