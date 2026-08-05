from __future__ import annotations

import json
import os
import time
from abc import ABC
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderUnavailable(ValueError):
    pass


class BaseProvider(ABC):
    name = "Public Data Provider"
    delayed_status = "Delayed"

    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds
        contact = os.getenv("GBB_DATA_CONTACT", "gbb-terminal-local@example.com")
        self.user_agent = f"GBB Terminal open-source research app {contact}"

    def request_bytes(self, url: str, attempts: int = 3) -> bytes:
        request = Request(url, headers={"User-Agent": self.user_agent, "Accept-Encoding": "identity"})
        for attempt in range(attempts):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    return response.read()
            except (HTTPError, URLError, TimeoutError) as error:
                if attempt == attempts - 1:
                    raise ProviderUnavailable(f"{self.name} is unavailable: {error}.") from error
                time.sleep(0.5 * 2**attempt)
        raise ProviderUnavailable(f"{self.name} is unavailable.")

    def request_json(self, url: str) -> dict:
        return json.loads(self.request_bytes(url))

    def status(self) -> dict:
        return {"provider": self.name, "configured": True, "status": self.delayed_status}

