from pydantic import BaseModel, Field


class ResponseModel(BaseModel):
    status_code: int | None = Field(None)

    response_headers: dict | None = Field(None)

    response: dict | list | str | None = Field(None)
    message: str | None = Field(None, min_length=1, max_length=255)

    error_code: str | None = Field(None, min_length=1, max_length=255)
    error_message: str | None = Field(None, min_length=1, max_length=255)
