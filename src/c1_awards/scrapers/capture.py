from __future__ import annotations

import hashlib
import json
from pathlib import Path


class JsonResponseCapture:
    """Persist JSON/XHR responses so scraper breakage can be debugged offline."""

    def __init__(self, raw_dir: Path, prefix: str):
        self.raw_dir = raw_dir
        self.prefix = prefix
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.count = 0

    async def capture(self, response) -> None:
        try:
            content_type = (response.headers.get("content-type") or "").lower()
            if "json" not in content_type:
                return
            body = await response.body()
            # Validate JSON; if invalid, skip instead of dumping arbitrary bodies.
            parsed = json.loads(body.decode("utf-8", errors="replace"))
            digest = hashlib.sha1(response.url.encode("utf-8")).hexdigest()[:10]
            self.count += 1
            path = self.raw_dir / f"{self.prefix}-{self.count:03d}-{digest}.json"
            path.write_text(
                json.dumps(
                    {"url": response.url, "status": response.status, "body": parsed},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            # Capture is diagnostic; it should never break the actual search.
            return
