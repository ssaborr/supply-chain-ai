from pydantic import BaseModel
from typing import Optional

class AnomalyRecordBase(BaseModel):
    anomaly: str
    score: float
    type: str
    timestamp: str
    description: str
    sales_order_id: int

class AnomalyRecordCreate(AnomalyRecordBase):
    pass

class AnomalyRecordOut(AnomalyRecordBase):
    id: str

    class Config:
        populate_by_name = True

class RFMRecordBase(BaseModel):
    customer_id: int
    recency: float
    frequency: float
    monetary: float
    segment: Optional[str] = "Standard"

class RFMRecordCreate(RFMRecordBase):
    pass

class RFMRecordOut(RFMRecordBase):
    id: str

    class Config:
        populate_by_name = True

class DemandForecastBase(BaseModel):
    date: str
    product_id: Optional[int] = None
    sales: Optional[float] = None
    forecast: float

class DemandForecastCreate(DemandForecastBase):
    pass

class DemandForecastOut(DemandForecastBase):
    id: str

    class Config:
        populate_by_name = True
