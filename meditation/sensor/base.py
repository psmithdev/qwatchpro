"""Sensor adapter abstract base class and sample dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional


@dataclass
class SensorSample:
    timestamp: float  # time.time()
    hr_bpm: int
    rr_ms: Optional[float] = None  # None when HR-only (e.g., QWatch)
    source: str = "unknown"


class SensorAdapter(ABC):
    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def stream(self) -> AsyncIterator[SensorSample]:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...
