from pydantic import BaseModel, Field


class OidcProviderModel(BaseModel):
    """Configuration for a single trusted OIDC / external IdP provider."""

    issuer: str = Field(
        ...,
        description='Expected `iss` claim value, e.g. "https://login.example.com/tenant"',
        example='https://accounts.google.com',
    )
    jwks_uri: str = Field(
        ...,
        description='JWKS endpoint URL, e.g. "https://login.example.com/.well-known/jwks.json"',
        example='https://www.googleapis.com/oauth2/v3/certs',
    )
    audience: str | list[str] | None = Field(
        default=None,
        description='Expected `aud` claim value(s). None skips audience validation.',
        example='my-api-client-id',
    )
    algorithms: list[str] = Field(
        default_factory=lambda: ['RS256'],
        description='Accepted signing algorithms for this provider',
        example=['RS256'],
    )
    require_local_user: bool = Field(
        default=False,
        description=(
            'If True, the `sub` claim must match a local Doorman user record. '
            'When False, any valid OIDC token is accepted regardless of whether '
            'the subject has a local account.'
        ),
    )


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
    oidc_providers: list[OidcProviderModel] | None = Field(
        default=None,
        description=(
            'Trusted OIDC / external IdP providers. When a gateway request carries a JWT whose '
            '`iss` claim matches one of these entries, the gateway fetches the provider\'s JWKS '
            'and validates the token without requiring a local Doorman user account '
            '(unless require_local_user=True).'
        ),
    )
