from __future__ import annotations

import uvicorn

from agent_toolbox.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "agent_toolbox.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
