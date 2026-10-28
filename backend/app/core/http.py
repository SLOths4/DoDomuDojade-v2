from functools import lru_cache

import httpx

from app.core.config import get_settings


@lru_cache
def http_client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(15.0, connect=5.0),
        headers={"User-Agent": get_settings().user_agent},
        follow_redirects=True,
    )
