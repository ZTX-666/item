"""Yaoyao OCR Engine — persistent subprocess worker with reqId routing,
health check, auto-restart, and dual-phase recognition fallback.

Python rewrite of PaddlePdfOcrApp/Services/OcrEngineService.cs.
Maintains equivalent capability: long-running RapidOCR worker process
communicating via stdin/stdout JSON protocol.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

from PIL import Image

from ..config import settings

_WORKER_SCRIPT = Path(__file__).resolve().parent.parent / "third_party" / "yaoyao" / "rapid_ocr_worker.py"

# Default timeout for a single OCR recognition call.
_DEFAULT_TIMEOUT = 60

# Minimum useful text length — shorter results trigger fallback.
_MIN_USEFUL_LEN = 2


class OcrEngineService:
    """Manages a persistent RapidOCR worker subprocess.

    Thread-safe via _lock.  The worker process is started on first use
    and kept alive.  If it crashes or becomes unresponsive, the next
    call auto-restarts it.
    """

    def __init__(
        self,
        python_bin: str | None = None,
        worker_timeout: int | None = None,
        fast_mode: bool = True,
    ) -> None:
        self._python_bin = python_bin or settings.yaoyao_python_bin
        self._worker_timeout = worker_timeout or settings.yaoyao_worker_timeout
        self._fast_mode = fast_mode
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._stdin = None
        self._stdout = None

    # ── public API ──────────────────────────────────────────────

    def recognize(
        self,
        image: Image.Image,
        region: dict[str, Any] | None = None,
    ) -> str:
        """Recognize text from a PIL image, optionally cropping to *region*.

        *region* keys: x, y, width, height, angle (degrees).

        Dual-phase fallback:
        1. Fast mode on original crop.
        2. If result is too short, slow mode with +16px padding.
        """
        if region:
            crop = self._crop_and_rotate(image, region, padding=0)
        else:
            crop = image

        first_text = self._recognize_image(crop, fast_mode=self._fast_mode)
        if _is_useful(first_text):
            return first_text

        # Fallback: expand crop + disable fast mode.
        if region:
            crop2 = self._crop_and_rotate(image, region, padding=16)
        else:
            crop2 = crop
        second_text = self._recognize_image(crop2, fast_mode=False)
        return second_text if _is_useful(second_text) else first_text

    def recognize_file(self, image_path: str | Path, fast_mode: bool = True) -> str:
        """Convenience: recognize a file path directly (no cropping)."""
        path = Path(image_path)
        if not path.exists() or path.stat().st_size <= 0:
            raise ValueError("Input image is empty or missing.")
        with Image.open(path) as img:
            return self._recognize_image(img.copy(), fast_mode=fast_mode)

    def shutdown(self) -> None:
        """Stop the worker process."""
        with self._lock:
            self._stop_worker_unlocked()

    # ── worker management ───────────────────────────────────────

    def _ensure_worker(self) -> None:
        if self._is_healthy():
            return
        self._stop_worker_unlocked()
        self._start_worker()

    def _is_healthy(self) -> bool:
        return (
            self._proc is not None
            and self._proc.poll() is None
            and self._stdin is not None
            and self._stdout is not None
        )

    def _start_worker(self) -> None:
        if not self._python_bin or not Path(self._python_bin).exists():
            # Fall back to current Python if the configured binary is missing.
            self._python_bin = sys.executable

        self._proc = subprocess.Popen(
            [self._python_bin, str(_WORKER_SCRIPT), "--server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._stdin = self._proc.stdin
        self._stdout = self._proc.stdout

        # Wait for READY signal (15s).
        import select as _select

        # On Windows select() doesn't work on pipes; use a thread-based readline with timeout.
        ready_line = self._readline_timeout(15)
        if ready_line is None or ready_line.strip() != "READY":
            stderr_text = ""
            if self._proc.stderr:
                try:
                    stderr_text = self._proc.stderr.read(4096)
                except Exception:
                    pass
            self._stop_worker_unlocked()
            raise RuntimeError(f"OCR worker failed to start: {ready_line} {stderr_text}")

    def _readline_timeout(self, timeout: float) -> str | None:
        """Read a line from stdout with timeout, using a daemon thread."""
        result: list[str | None] = [None]

        def _reader() -> None:
            try:
                result[0] = self._stdout.readline()
            except Exception:
                result[0] = None

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        t.join(timeout=timeout)
        return result[0]

    def _stop_worker_unlocked(self) -> None:
        if self._stdin:
            try:
                payload = json.dumps({
                    "id": str(uuid.uuid4()),
                    "cmd": "shutdown",
                    "image": "",
                })
                self._stdin.write(payload + "\n")
                self._stdin.flush()
            except Exception:
                pass

        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass

        for attr in ("_stdin", "_stdout"):
            stream = getattr(self, attr)
            if stream:
                try:
                    stream.close()
                except Exception:
                    pass
                setattr(self, attr, None)
        self._proc = None

    # ── core recognition ────────────────────────────────────────

    def _recognize_image(self, image: Image.Image, fast_mode: bool = True) -> str:
        """Send an image to the worker and wait for the result."""
        with self._lock:
            self._ensure_worker()
            if not self._stdin or not self._stdout:
                raise RuntimeError("OCR worker is not ready.")

            # Save image to temp file.
            import tempfile

            tmp_path: Path | None = None
            try:
                # Upscale tiny crops.
                final_img = image
                min_size = 96
                if image.width < min_size or image.height < min_size:
                    scale = max(min_size / image.width, min_size / image.height)
                    new_size = (int(image.width * scale), int(image.height * scale))
                    final_img = image.resize(new_size, Image.Resampling.BICUBIC)

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = Path(tmp.name)
                final_img.save(tmp_path, "PNG")

                if tmp_path.stat().st_size <= 0:
                    raise ValueError("Cropped image is empty; adjust region.")

                req_id = uuid.uuid4().hex
                payload = json.dumps({
                    "id": req_id,
                    "cmd": "recognize",
                    "image": str(tmp_path),
                    "fast_mode": fast_mode,
                })
                self._stdin.write(payload + "\n")
                self._stdin.flush()

                # Read responses until we find our reqId.
                deadline_loops = self._worker_timeout
                while deadline_loops > 0:
                    line = self._readline_timeout(self._worker_timeout)
                    if line is None:
                        self._stop_worker_unlocked()
                        raise TimeoutError(
                            f"OCR timed out: worker did not respond within {self._worker_timeout}s."
                        )

                    try:
                        resp = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if resp.get("id") != req_id:
                        continue

                    if not resp.get("ok"):
                        raise RuntimeError(resp.get("error", "OCR processing failed."))

                    return resp.get("text", "")
                # If we exhaust the loop, treat as timeout.
                self._stop_worker_unlocked()
                raise TimeoutError(
                    f"OCR timed out: no matching response within {self._worker_timeout}s."
                )
            finally:
                if tmp_path and tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except Exception:
                        pass

    # ── image processing ────────────────────────────────────────

    def _crop_and_rotate(
        self,
        image: Image.Image,
        region: dict[str, Any],
        padding: int = 0,
    ) -> Image.Image:
        """Crop a region from the image and optionally rotate.

        Mirrors OcrEngineService.CreateCropPreview + BuildCropRect.
        Coordinates are in original-image pixel space.
        """
        x = int(round(region.get("x", 0))) - padding
        y = int(round(region.get("y", 0))) - padding
        w = int(round(region.get("width", image.width))) + padding * 2
        h = int(round(region.get("height", image.height))) + padding * 2

        # Clamp to image bounds.
        x = max(0, min(x, image.width - 1))
        y = max(0, min(y, image.height - 1))
        w = max(1, min(w, image.width - x))
        h = max(1, min(h, image.height - y))

        if w <= 0 or h <= 0:
            raise ValueError("Region is invalid: crop size is 0.")

        cropped = image.crop((x, y, x + w, y + h))

        angle = region.get("angle", 0.0)
        if abs(angle) > 0.01:
            cropped = cropped.rotate(-angle, expand=True, fillcolor=(255, 255, 255))

        return cropped


def _is_useful(text: str | None) -> bool:
    if not text:
        return False
    return len(text.strip()) >= _MIN_USEFUL_LEN


# ── module-level singleton ──────────────────────────────────────

_engine_instance: OcrEngineService | None = None
_engine_lock = threading.Lock()


def get_engine() -> OcrEngineService:
    global _engine_instance
    if _engine_instance is None:
        with _engine_lock:
            if _engine_instance is None:
                _engine_instance = OcrEngineService()
    return _engine_instance
