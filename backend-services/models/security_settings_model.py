from pydantic import BaseModel, Field


class SecuritySettingsModel(BaseModel):
    enable_auto_save: bool | None = Field(default=None)
    auto_save_frequency_seconds: int | None = Field(
        default=None, ge=60, description='How often to auto-save memory dump (seconds)'
    )
    dump_path: str | None = Field(default=None, description='Path to write encrypted memory dumps')
    ip_whitelist: list[str] | None = Field(
        default=None, description='List of allowed IPs/CIDRs. If non-empty, only these are allowed.'
    )
    ip_blacklist: list[str] | None = Field(default=None, description='List of blocked IPs/CIDRs')
    trust_x_forwarded_for: bool | None = Field(
        default=None, description='If true, use X-Forwarded-For header for client IP'
    )
    xff_trusted_proxies: list[str] | None = Field(
        default=None,
        description='IPs/CIDRs of proxies allowed to set client IP headers (XFF/X-Real-IP). Empty means trust all when enabled.',
    )
    allow_localhost_bypass: bool | None = Field(
        default=None,
        description='Allow direct localhost (::1/127.0.0.1) to bypass IP allow/deny lists when no forwarding headers are present',
    )
