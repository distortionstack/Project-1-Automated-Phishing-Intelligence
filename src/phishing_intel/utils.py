from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

try:
    import requests
except ImportError:
    requests = None


def http_get(
    url: str,
    timeout: int = 5,
    headers: dict[str, str] | None = None,
    verify: bool = True,
) -> Any:
    if requests is not None:
        return requests.get(url, timeout=timeout, headers=headers, verify=verify)

    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=timeout) as resp:
        status_code = getattr(resp, "status", resp.getcode())
        content = resp.read()
        encoding = resp.headers.get_content_charset() or "utf-8"

    class SimpleResponse:
        def __init__(self, body: bytes, status: int, enc: str):
            self.content = body
            self.status_code = status
            self.text = body.decode(enc, errors="replace")

        def json(self):
            return json.loads(self.text)

    return SimpleResponse(content, status_code, encoding)
