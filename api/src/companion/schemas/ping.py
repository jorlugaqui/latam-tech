from typing import Literal

from pydantic import BaseModel


class PingResponse(BaseModel):
    status: Literal["ok"] = "ok"
