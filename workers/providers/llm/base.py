from abc import ABC, abstractmethod
from typing import Any


class EditPlanProvider(ABC):
    name: str

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> dict[str, Any]: ...
