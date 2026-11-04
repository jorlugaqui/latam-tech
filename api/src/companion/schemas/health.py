from typing import Literal

from pydantic import BaseModel, ConfigDict


class LiveStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["ok"] = "ok"


class ReadyStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["ready", "not_ready"]
