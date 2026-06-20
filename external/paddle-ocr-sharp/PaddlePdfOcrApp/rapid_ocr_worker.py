import argparse
import json
import tempfile
import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps
from rapidocr_onnxruntime import RapidOCR


def _collect_text_and_score(result) -> tuple[str, float]:
    if not result:
        return "", 0.0

    texts: list[str] = []
    score_sum = 0.0
    score_count = 0
    for item in result:
        if len(item) >= 2 and item[1]:
            texts.append(str(item[1]))
        if len(item) >= 3:
            try:
                score_sum += float(item[2])
                score_count += 1
            except Exception:
                pass

    text = "".join(texts).strip()
    avg_score = (score_sum / score_count) if score_count > 0 else 0.0
    return text, avg_score


def _build_variants(image: Image.Image, fast_mode: bool) -> list[Image.Image]:
    # Generate several enhanced variants for form-like text.
    gray = ImageOps.grayscale(image)
    enhanced = ImageOps.autocontrast(gray)
    if fast_mode:
        # High-speed mode: only keep the two most useful variants.
        return [image, enhanced]

    upscaled = enhanced.resize((enhanced.width * 2, enhanced.height * 2), Image.Resampling.BICUBIC)
    sharpened = upscaled.filter(ImageFilter.SHARPEN)
    threshold = enhanced.point(lambda p: 255 if p > 165 else 0, mode="1").convert("L")
    threshold_upscaled = threshold.resize((threshold.width * 2, threshold.height * 2), Image.Resampling.BICUBIC)

    # Keep order: original first, then progressively stronger enhancement.
    return [image, enhanced, sharpened, threshold_upscaled]


def _recognize_best(engine: RapidOCR, image_path: Path, fast_mode: bool) -> str:
    with Image.open(image_path) as img:
        variants = _build_variants(img.copy(), fast_mode)

    best_text = ""
    best_score = -1.0
    best_len = -1

    for variant in variants:
        tmp_file = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_file = Path(tmp.name)
            variant.save(tmp_file)
            result, _ = engine(str(tmp_file))
            text, score = _collect_text_and_score(result)
            if not text:
                continue

            # Prefer higher confidence, then longer non-empty text.
            text_len = len(text)
            if score > best_score or (abs(score - best_score) < 1e-6 and text_len > best_len):
                best_text = text
                best_score = score
                best_len = text_len
        finally:
            if tmp_file and tmp_file.exists():
                tmp_file.unlink(missing_ok=True)

    return best_text


def run_server() -> int:
    engine = RapidOCR()
    print("READY", flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
            req_id = req.get("id", "")
            cmd = req.get("cmd", "recognize")
            if cmd == "shutdown":
                print(json.dumps({"id": req_id, "ok": True}), flush=True)
                return 0

            image_path = Path(req["image"])
            if not image_path.exists() or image_path.stat().st_size <= 0:
                print(json.dumps({"id": req_id, "ok": False, "error": "輸入圖像為空或不存在。"}), flush=True)
                continue

            fast_mode = bool(req.get("fast_mode", True))
            text = _recognize_best(engine, image_path, fast_mode)
            print(json.dumps({"id": req_id, "ok": True, "text": text}, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({"id": "", "ok": False, "error": str(exc)}, ensure_ascii=False), flush=True)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--image")
    parser.add_argument("--out")
    args = parser.parse_args()

    if args.server:
        return run_server()

    if not args.image or not args.out:
        print("ERROR: --image and --out are required in non-server mode", file=sys.stderr)
        return 2

    image_path = Path(args.image)
    out_path = Path(args.out)
    if not image_path.exists() or image_path.stat().st_size <= 0:
        out_path.write_text("ERROR:輸入圖像為空或不存在。", encoding="utf-8")
        return 2

    try:
        engine = RapidOCR()
        best_text = _recognize_best(engine, image_path, False)
        if not best_text:
            out_path.write_text("", encoding="utf-8")
            return 0

        out_path.write_text(best_text, encoding="utf-8")
        return 0
    except Exception as exc:
        out_path.write_text(f"ERROR:{exc}", encoding="utf-8")
        return 1


if __name__ == "__main__":
    sys.exit(main())
