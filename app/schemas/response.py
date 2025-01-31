# app/schemas/response.py

from pydantic import BaseModel
from typing import List, Optional

class PredictionResponse(BaseModel):
    id: int
    answer: Optional[int]  # или другой тип, в зависимости от вашей логики
    reasoning: str
    sources: List[str]
