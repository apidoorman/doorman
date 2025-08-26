from pydantic import BaseModel, Field
from typing import Optional


class SecuritySettingsModel(BaseModel):
    enable_auto_save: Optional[bool] = Field(default=None)
    auto_save_frequency_seconds: Optional[int] = Field(default=None, ge=60, description="How often to auto-save memory dump (seconds)")
    dump_path: Optional[str] = Field(default=None, description="Path to write encrypted memory dumps")

