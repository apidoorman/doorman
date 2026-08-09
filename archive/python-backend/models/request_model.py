from pydantic import BaseModel


class RequestModel(BaseModel):
    method: str
    path: str
    headers: dict[str, str]
    query_params: dict[str, str]
    identity: str | None = None
    body: str | None = None
