from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path

from ..models import AwardResult, Cabin


class ScraperError(RuntimeError):
    pass


class BaseScraper(ABC):
    program_name: str

    def __init__(self, *, profile_dir: Path, raw_dir: Path, headless: bool = False):
        self.profile_dir = profile_dir
        self.raw_dir = raw_dir
        self.headless = headless
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    async def search(
        self,
        origin: str,
        destination: str,
        travel_date: date,
        cabin: Cabin,
    ) -> list[AwardResult]:
        raise NotImplementedError
