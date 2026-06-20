#!/usr/bin/env python3
"""
HiAgent 插件：工地人+机械检测 HTTP 服务（默认单模型 unified，一次推理）。

部署到云服务器后，在 HiAgent 中注册为「API 类型插件」，填写本服务的 HTTPS 地址与 openapi.yaml。

本地启动:
  uvicorn hiagent_api:app --host 0.0.0.0 --port 8080

环境变量:
  HIAGENT_API_KEY   可选；设置后请求头须带 X-API-Key
  VLM_CONFIG        可选；config.yaml 路径
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from detect_core import (
    DetectBundle,
    decode_image_bytes,
    load_config,
    load_models,
    run_detect_response,
    vlm_image_style,
)

API_KEY = os.environ.get("HIAGENT_API_KEY", "").strip()
CONFIG_PATH = os.environ.get("VLM_CONFIG", "").strip() or None

_bundle: DetectBundle | None = None
_cfg: dict | None = None


def _get_bundle() -> DetectBundle:
    if _bundle is None:
        raise RuntimeError("模型未加载")
    return _bundle


def _check_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bundle, _cfg
    _cfg = load_config(CONFIG_PATH) if CONFIG_PATH else load_config()
    _bundle = load_models(_cfg)
    yield
    _bundle = None
    _cfg = None


app = FastAPI(
    title="VLM-Detection HiAgent Plugin",
    description="输入一张工地现场图，默认返回一张合并标注图（人绿框+机械橙框），供大模型 few-shot 省 token。",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class DetectJsonRequest(BaseModel):
    image_base64: str | None = Field(default=None, description="图片 Base64（与 image_url 二选一）")
    image_url: str | None = Field(default=None, description="图片公网 URL（与 image_base64 二选一）")
    conf: float | None = Field(default=None, ge=0.0, le=1.0, description="置信度阈值")
    imgsz: int | None = Field(default=None, ge=320, le=1280, description="推理尺寸")


async def _fetch_url(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        if len(resp.content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="图片超过 5MB（HiAgent 单图限制）")
        return resp.content


def _triple_response(
    image_bgr,
    *,
    source_name: str,
    conf: float | None,
    imgsz: int | None,
) -> dict[str, Any]:
    payload = run_detect_response(
        _get_bundle(),
        image_bgr,
        source_name=source_name,
        conf=conf,
        imgsz=imgsz,
        cfg=_cfg,
    )
    return {"ok": True, **payload}


@app.get("/health")
async def health() -> dict[str, str]:
    b = _bundle
    return {
        "status": "ok",
        "service": "vlm-detection-hiagent",
        "mode": b.mode if b else "not_loaded",
        "vlm_image": vlm_image_style(_cfg) if _cfg else "unknown",
    }


@app.post("/v1/detect/triple", dependencies=[Depends(_check_api_key)])
async def detect_triple_multipart(
    file: UploadFile = File(..., description="待检测图片"),
    conf: float | None = None,
    imgsz: int | None = None,
) -> dict[str, Any]:
    """multipart 上传单张图片；默认返回 1 张合并标注图（config output.vlm_image=combined）。"""
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片超过 5MB")
    try:
        image_bgr = decode_image_bytes(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _triple_response(image_bgr, source_name=file.filename or "upload", conf=conf, imgsz=imgsz)


@app.post("/v1/detect/triple/json", dependencies=[Depends(_check_api_key)])
async def detect_triple_json(body: DetectJsonRequest) -> dict[str, Any]:
    """JSON 请求：image_base64 或 image_url 二选一。"""
    if bool(body.image_base64) == bool(body.image_url):
        raise HTTPException(status_code=400, detail="请提供 image_base64 或 image_url 之一")

    if body.image_url:
        try:
            data = await _fetch_url(body.image_url)
        except httpx.HTTPError as e:
            raise HTTPException(status_code=400, detail=f"拉取图片失败: {e}") from e
        source_name = body.image_url.rsplit("/", 1)[-1] or "url"
    else:
        import base64

        raw = body.image_base64 or ""
        if "," in raw:
            raw = raw.split(",", 1)[1]
        try:
            data = base64.b64decode(raw, validate=False)
        except Exception as e:
            raise HTTPException(status_code=400, detail="image_base64 无效") from e
        source_name = "base64"

    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片超过 5MB")

    try:
        image_bgr = decode_image_bytes(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return _triple_response(image_bgr, source_name=source_name, conf=body.conf, imgsz=body.imgsz)
