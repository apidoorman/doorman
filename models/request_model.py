from pydantic import BaseModel
from typing import Dict, Optional

class RequestModel(BaseModel):
    method: str
    path: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    identity: Optional[str] = None
    body: Optional[str] = None