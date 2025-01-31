# app/schemas/request.py

from pydantic import BaseModel

class PredictionRequest(BaseModel):
    id: int
    query: str

