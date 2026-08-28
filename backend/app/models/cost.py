"""
Normalized cost data models, mapped from Cost Explorer API responses.
"""
from datetime import date
from pydantic import BaseModel


class DailyCost(BaseModel):
    date: date
    service: str
    amount_usd: float


class CostSummary(BaseModel):
    total_usd: float
    period_start: date
    period_end: date
    by_service: dict[str, float]
