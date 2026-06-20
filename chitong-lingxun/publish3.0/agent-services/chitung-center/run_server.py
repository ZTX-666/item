from __future__ import annotations

import uvicorn

from chitung_center.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "chitung_center.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
