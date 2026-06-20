#!/usr/bin/env python3
"""
Depth Anything V2 Small HTTP 服务（云服务器部署）。

启动:
  uvicorn depth_api:app --host 0.0.0.0 --port 8090

环境变量:
  DEPTH_API_KEY     可选；设置后请求头须带 X-API-Key
  DEPTH_CONFIG      可选；config_depth.yaml 路径
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from depth_core import (
    DepthBundle,
    decode_image_bytes,
    load_depth_config,
    load_depth_model,
    run_depth_predict,
)

API_KEY = os.environ.get("DEPTH_API_KEY", "").strip()
CONFIG_PATH = os.environ.get("DEPTH_CONFIG", "").strip() or None

_bundle: DepthBundle | None = None


def _get_bundle() -> DepthBundle:
    if _bundle is None:
        raise RuntimeError("深度模型未加载")
    return _bundle


def _check_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bundle
    cfg = load_depth_config(CONFIG_PATH) if CONFIG_PATH else load_depth_config()
    _bundle = load_depth_model(cfg)
    yield
    _bundle = None


app = FastAPI(
    title="Depth Anything V2 Small API",
    description="工地监控辅助：单张图相对深度估计（非米制）。",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class DepthJsonRequest(BaseModel):
    image_base64: str | None = Field(default=None, description="图片 Base64")
    image_url: str | None = Field(default=None, description="图片 URL")
    return_vis: bool = Field(default=True, description="是否返回可视化拼接图 Base64")
    boxes: list[dict[str, Any]] | None = Field(
        default=None,
        description="可选检测框列表（含 bbox_xyxy），用于框内深度统计",
    )


async def _fetch_url(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        if len(resp.content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="图片超过 10MB")
        return resp.content


def _predict_response(image_bgr, *, return_vis: bool, boxes: list | None) -> dict[str, Any]:
    payload = run_depth_predict(
        _get_bundle(),
        image_bgr,
        boxes=boxes,
        return_vis=return_vis,
    )
    slim = {k: v for k, v in payload.items() if not k.endswith("_base64")}
    b64 = {k: v for k, v in payload.items() if k.endswith("_base64")}
    return {"ok": True, **slim, **b64}


@app.get("/health")
async def health() -> dict[str, str]:
    b = _bundle
    return {
        "status": "ok",
        "service": "depth-anything-v2-small",
        "device": b.device if b else "not_loaded",
    }


@app.post("/depth", dependencies=[Depends(_check_api_key)])
async def depth_upload(
    file: UploadFile = File(...),
    return_vis: bool = True,
) -> dict[str, Any]:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="空文件")
    try:
        image_bgr = decode_image_bytes(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _predict_response(image_bgr, return_vis=return_vis, boxes=None)


@app.post("/depth/json", dependencies=[Depends(_check_api_key)])
async def depth_json(body: DepthJsonRequest) -> dict[str, Any]:
    if bool(body.image_base64) == bool(body.image_url):
        raise HTTPException(status_code=400, detail="请提供 image_base64 或 image_url 之一")
    if body.image_url:
        import base64

        data = await _fetch_url(body.image_url)
    else:
        import base64

        raw = body.image_base64 or ""
        if "," in raw:
            raw = raw.split(",", 1)[1]
        try:
            data = base64.b64decode(raw)
        except Exception as e:
            raise HTTPException(status_code=400, detail="image_base64 无效") from e
    try:
        image_bgr = decode_image_bytes(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _predict_response(image_bgr, return_vis=body.return_vis, boxes=body.boxes)
