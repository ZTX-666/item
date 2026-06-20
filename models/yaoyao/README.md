# 耀耀慧读 RapidOCR 模型（随仓库分发）

本目录包含耀耀慧读 OCR worker 使用的 **PP-OCRv4** ONNX 模型，避免同事 clone 后还要联网下载。

## 文件

| 文件 | 用途 | 约大小 |
| --- | --- | --- |
| `ch_PP-OCRv4_det_infer.onnx` | 文本检测 | ~4.5 MB |
| `ch_PP-OCRv4_rec_infer.onnx` | 文本识别 | ~10 MB |
| `ch_ppocr_mobile_v2.0_cls_infer.onnx` | 方向分类 | ~0.6 MB |

## 配置

在 `agent-toolbox/.env` 中设置：

```ini
YAOYAO_MODEL_DIR=J:\path\to\item\models\yaoyao\rapidocr
```

`rapid_ocr_worker.py` 会读取该目录；未配置时回退到 RapidOCR 包内默认路径（需联网下载）。

## 来源

- HuggingFace: [SWHL/RapidOCR](https://huggingface.co/SWHL/RapidOCR)
- 与 `rapidocr_onnxruntime` 默认 `config.yaml` 文件名一致

## Git LFS

`.onnx` 文件通过 Git LFS 托管。clone 后执行：

```powershell
git lfs install
git lfs pull
```
