"""Demo world: payments-mock.

A trivial service shop-api depends on. When it is stopped, shop-api logs
"connection refused to payments-mock:9002" and checkout errors climb.

Run with: python -m world.payments_mock
"""

from __future__ import annotations

import time

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="payments-mock (demo world)", version="1.0.0")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "payments-mock"}


@app.get("/charge")
async def charge(amount: float = 10.0) -> dict[str, object]:
    return {"status": "charged", "amount": amount, "timestamp": time.time()}


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=9002, log_level="info")


if __name__ == "__main__":
    main()
