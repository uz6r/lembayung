from pydantic import BaseModel


class Slot(BaseModel):
    id: str
    time: str
    status: str | None = "AVAILABLE"


class AvailabilityResponse(BaseModel):
    data: list[Slot]
