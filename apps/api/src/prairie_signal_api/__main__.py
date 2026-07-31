"""Run the development API with ``python -m prairie_signal_api``."""

from __future__ import annotations

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "prairie_signal_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        access_log=False,
    )
