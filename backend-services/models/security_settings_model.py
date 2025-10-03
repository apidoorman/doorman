# External imports
from pydantic import BaseModel, Field
from typing import Optional, List

class SecuritySettingsModel(BaseModel):
    enable_auto_save: Optional[bool] = Field(default=None)
    auto_save_frequency_seconds: Optional[int] = Field(default=None, ge=60, description='How often to auto-save memory dump (seconds)')
    dump_path: Optional[str] = Field(default=None, description='Path to write encrypted memory dumps')
    ip_whitelist: Optional[List[str]] = Field(default=None, description='List of allowed IPs/CIDRs. If non-empty, only these are allowed.')
    ip_blacklist: Optional[List[str]] = Field(default=None, description='List of blocked IPs/CIDRs')
    trust_x_forwarded_for: Optional[bool] = Field(default=None, description='If true, use X-Forwarded-For header for client IP')
