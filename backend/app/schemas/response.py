from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str = "Success"
    data: Optional[T] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    project: str
    version: str = "0.1.0"
    database_connected: bool
