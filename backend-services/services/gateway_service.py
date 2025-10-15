"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import os
import random
import json
import sys
import xml.etree.ElementTree as ET
import logging
import re
import time
import httpx
from typing import Dict
import grpc
import asyncio
from google.protobuf.json_format import MessageToDict
import importlib
import string
from pathlib import Path

try:
    from gql import Client as _GqlClient
    def gql(q):
        return q
except Exception:
    class _GqlClient:
        def __init__(self, *args, **kwargs):
            pass
    def gql(q):
        return q

Client = _GqlClient

from models.response_model import ResponseModel
from utils import api_util, routing_util
from utils import credit_util
from utils.gateway_utils import get_headers
from utils.doorman_cache_util import doorman_cache
from utils.validation_util import validation_util
from utils.http_client import request_with_resilience, CircuitOpenError

logging.getLogger('gql').setLevel(logging.WARNING)

logger = logging.getLogger('doorman.gateway')

class GatewayService:

    timeout = httpx.Timeout(
                connect=float(os.getenv('HTTP_CONNECT_TIMEOUT', 5.0)),
                read=float(os.getenv('HTTP_READ_TIMEOUT', 30.0)),
                write=float(os.getenv('HTTP_WRITE_TIMEOUT', 30.0)),
                pool=float(os.getenv('HTTP_TIMEOUT', 30.0))
            )
    _http_client: httpx.AsyncClient | None = None

    @staticmethod
    def _build_limits() -> httpx.Limits:
        """Pool limits tuned for small/medium projects with env overrides.

        Defaults:
        - max_connections: 100 (total across hosts)
        - max_keepalive_connections: 50 (pooled, idle)
        - keepalive_expiry: 30s
        """
        try:
            max_conns = int(os.getenv('HTTP_MAX_CONNECTIONS', 100))
        except Exception:
            max_conns = 100
        try:
            max_keep = int(os.getenv('HTTP_MAX_KEEPALIVE', 50))
        except Exception:
            max_keep = 50
        try:
            expiry = float(os.getenv('HTTP_KEEPALIVE_EXPIRY', 30.0))
        except Exception:
            expiry = 30.0
        return httpx.Limits(max_connections=max_conns, max_keepalive_connections=max_keep, keepalive_expiry=expiry)

    @classmethod
    def get_http_client(cls) -> httpx.AsyncClient:
        """Return a pooled AsyncClient by default for connection reuse.

        Set ENABLE_HTTPX_CLIENT_CACHE=false to disable pooling and create a
        fresh client per request.
        """
        if os.getenv('ENABLE_HTTPX_CLIENT_CACHE', 'true').lower() != 'false':
            if cls._http_client is None:
                cls._http_client = httpx.AsyncClient(
                    timeout=cls.timeout,
                    limits=cls._build_limits(),
                    http2=(os.getenv('HTTP_ENABLE_HTTP2', 'false').lower() == 'true')
                )
            return cls._http_client
        return httpx.AsyncClient(
            timeout=cls.timeout,
            limits=cls._build_limits(),
            http2=(os.getenv('HTTP_ENABLE_HTTP2', 'false').lower() == 'true')
        )

    @classmethod
    async def aclose_http_client(cls) -> None:
        try:
            if cls._http_client is not None:
                await cls._http_client.aclose()
        except Exception:
            pass
        finally:
            cls._http_client = None

    def error_response(request_id, code, message, status=404):
            logger.error(f'{request_id} | REST gateway failed with code {code}')
            return ResponseModel(
                status_code=status,
                response_headers={'request_id': request_id},
                error_code=code,
                error_message=message
            ).dict()

    @staticmethod
    def _compute_api_cors_headers(api: dict, origin: str | None, req_method: str | None, req_headers: str | None):
        try:
            origin = (origin or '').strip()
            req_method = (req_method or '').strip().upper()
            requested_headers = [h.strip() for h in (req_headers or '').split(',') if h.strip()]
            allow_origins = api.get('api_cors_allow_origins') or ['*']
            allow_methods = [m.strip().upper() for m in (api.get('api_cors_allow_methods') or ['GET','POST','PUT','DELETE','PATCH','HEAD','OPTIONS']) if m]
            if 'OPTIONS' not in allow_methods:
                allow_methods.append('OPTIONS')
            allow_headers = api.get('api_cors_allow_headers') or ['*']
            allow_credentials = bool(api.get('api_cors_allow_credentials'))
            expose_headers = api.get('api_cors_expose_headers') or []

            origin_allowed = False
            if '*' in allow_origins:
                origin_allowed = True
            elif origin and origin in allow_origins:
                origin_allowed = True

            method_allowed = True if not req_method else (req_method in allow_methods)

            if any(h == '*' for h in allow_headers):
                headers_allowed = True
            else:
                allowed_lower = {h.lower() for h in allow_headers}
                headers_allowed = all(h.lower() in allowed_lower for h in requested_headers)

            preflight_ok = origin_allowed and method_allowed and headers_allowed

            cors_headers = {}
            if origin_allowed:
                cors_headers['Access-Control-Allow-Origin'] = origin
                cors_headers['Vary'] = 'Origin'
            if allow_credentials:
                cors_headers['Access-Control-Allow-Credentials'] = 'true'
            if req_method:
                cors_headers['Access-Control-Allow-Methods'] = ', '.join(allow_methods)
            if req_headers is not None:
                cors_headers['Access-Control-Allow-Headers'] = ', '.join(allow_headers)
            if expose_headers:
                cors_headers['Access-Control-Expose-Headers'] = ', '.join(expose_headers)
            return preflight_ok, cors_headers
        except Exception:
            return False, {}

    def parse_response(response):
        """Parse upstream response based on explicit content-type.

        - For explicit JSON or GraphQL JSON: parse as JSON and raise on error.
        - For explicit XML: parse as XML and raise on error.
        - For binary/text types (e.g., octet-stream, text/plain): return raw bytes.
        - For missing/unspecified content-type: best-effort fallback
          (try JSON, then XML, else raw bytes).
        """
        ctype_raw = response.headers.get('Content-Type', '') or ''
        ctype = ctype_raw.split(';', 1)[0].strip().lower()
        body = getattr(response, 'content', b'')

        if ctype in ('application/json', 'application/graphql+json') or 'application/graphql' in ctype:
            return json.loads(body)

        if ctype in ('application/xml', 'text/xml'):
            return ET.fromstring(body)

        if ctype in ('application/octet-stream', 'text/plain'):
            return body

        if not ctype:
            try:
                return json.loads(body)
            except Exception:
                try:
                    return ET.fromstring(body)
                except Exception:
                    return body

        return body

    @staticmethod
    async def _resolve_api_from_path(path: str, request_id: str):
        """
        Extract common API resolution logic used across all gateway methods.

        Parses path to extract API name/version and resolves API definition.

        Args:
            path: Request path (e.g., /myapi/v1/endpoint)
            request_id: Request ID for logging

        Returns:
            tuple: (api dict, api_name_version str, endpoint_uri str) or (None, None, None)
        """
        try:
            parts = [p for p in (path or '').split('/') if p]
            api_name_version = ''
            endpoint_uri = ''
            if len(parts) >= 2 and parts[1].startswith('v') and parts[1][1:].isdigit():
                api_name_version = f'/{parts[0]}/{parts[1]}'
                endpoint_uri = '/'.join(parts[2:])
            else:
                return None, None, None

            api_key = doorman_cache.get_cache('api_id_cache', api_name_version)
            api = await api_util.get_api(api_key, api_name_version)
            return api, api_name_version, endpoint_uri
        except Exception as e:
            logger.error(f'{request_id} | API resolution failed: {str(e)}')
            return None, None, None

    @staticmethod
    async def _check_and_deduct_credits(api: dict, username: str, request_id: str):
        """
        Extract common credit checking and deduction logic.

        Checks if API requires credits and deducts one credit if applicable.

        Args:
            api: API definition dict
            username: Username requesting the API
            request_id: Request ID for logging

        Returns:
            dict: Error response if credit check fails, None if success
        """
        if not api:
            return None

        if api.get('api_credits_enabled') and username and not bool(api.get('api_public')):
            if not await credit_util.deduct_credit(api.get('api_credit_group'), username):
                logger.warning(f'{request_id} | Credit deduction failed for user {username}')
                return GatewayService.error_response(
                    request_id,
                    'GTW008',
                    'User does not have any credits',
                    status=401
                )
        return None

    @staticmethod
    async def _apply_credit_headers(api: dict, username: str, headers: dict):
        """
        Extract common credit header application logic.

        Adds API key headers for credit-enabled APIs (both system and user-specific keys).

        Args:
            api: API definition dict
            username: Username requesting the API
            headers: Headers dict to modify (modified in-place)

        Returns:
            None (modifies headers dict in-place)
        """
        if not api or not api.get('api_credits_enabled'):
            return

        ai_token_headers = await credit_util.get_credit_api_header(api.get('api_credit_group'))
        if ai_token_headers:
            header_name = ai_token_headers[0]
            header_value = ai_token_headers[1]

            if isinstance(header_value, list):
                header_value = header_value[-1] if len(header_value) > 0 else header_value[0]

            headers[header_name] = header_value

            if username and not bool(api.get('api_public')):
                user_specific_api_key = await credit_util.get_user_api_key(
                    api.get('api_credit_group'),
                    username
                )
                if user_specific_api_key:
                    headers[header_name] = user_specific_api_key

    @staticmethod
    def _sanitize_grpc_metadata(headers: dict) -> list:
        """
        Sanitize HTTP headers for gRPC metadata compatibility.

        gRPC metadata keys must be:
        - lowercase ASCII
        - contain only alphanumeric, hyphens, underscores, and dots
        - not contain certain control characters

        Args:
            headers: HTTP headers dict

        Returns:
            List of (key, value) tuples suitable for gRPC metadata
        """
        metadata_list = []
        if not headers:
            return metadata_list

        for k, v in headers.items():
            try:
                key = str(k).lower().strip()

                if not key:
                    continue

                sanitized_key = ''.join(
                    c if c.isalnum() or c in ('-', '_', '.') else '-'
                    for c in key
                )

                if not sanitized_key:
                    continue

                value = str(v) if v is not None else ''

                try:
                    value.encode('ascii')
                except UnicodeEncodeError:
                    continue

                metadata_list.append((sanitized_key, value))
            except Exception:
                continue

        return metadata_list

    _IDENT_ALLOWED = set(string.ascii_letters + string.digits + "_")
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent

    @staticmethod
    def _validate_under_base(base: Path, target: Path) -> bool:
        try:
            base_r = base.resolve()
            target_r = target.resolve()
            return str(target_r).startswith(str(base_r))
        except Exception:
            return False

    @staticmethod
    def _is_valid_identifier(name: str, max_len: int = 128) -> bool:
        try:
            if not isinstance(name, str):
                return False
            name = name.strip()
            if not name or len(name) > max_len:
                return False
            if name[0] not in string.ascii_letters + "_":
                return False
            for ch in name:
                if ch not in GatewayService._IDENT_ALLOWED:
                    return False
            return True
        except Exception:
            return False

    @staticmethod
    def _validate_package_name(pkg: str | None) -> str | None:
        """Validate a gRPC Python module base name used for imports.

        Rules:
        - Allow dotted package paths (e.g., 'api.pkg') consisting of valid Python identifiers per segment
        - Disallow path separators ('/', '\\') and segment traversal ('..')
        - Each segment must pass _is_valid_identifier
        """
        if not pkg:
            return None
        pkg = str(pkg).strip()
        if "/" in pkg or "\\" in pkg or ".." in pkg:
            return None
        parts = pkg.split(".") if "." in pkg else [pkg]
        if any(not GatewayService._is_valid_identifier(p) for p in parts if p is not None):
            return None
        return pkg

    @staticmethod
    def _parse_and_validate_method(method_fq: str | None) -> tuple[str, str] | None:
        """Validate and split method spec formatted as 'Service.Method'."""
        if not method_fq:
            return None
        try:
            method_fq = str(method_fq).strip()
            if "." not in method_fq:
                return None
            service, method = method_fq.split(".", 1)
            service = service.strip()
            method = method.strip()
            if not (GatewayService._is_valid_identifier(service) and GatewayService._is_valid_identifier(method)):
                return None
            return service, method
        except Exception:
            return None

    @staticmethod
    async def rest_gateway(username, request, request_id, start_time, path, url=None, method=None, retry=0):
        """
        External gateway.
        """
        logger.info(f'{request_id} | REST gateway trying resource: {path}')
        current_time = backend_end_time = None
        try:
            if not url and not method:

                parts = [p for p in (path or '').split('/') if p]
                api_name_version = ''
                endpoint_uri = ''
                if len(parts) >= 2 and parts[1].startswith('v') and parts[1][1:].isdigit():
                    api_name_version = f'/{parts[0]}/{parts[1]}'
                    endpoint_uri = '/'.join(parts[2:])
                api_key = doorman_cache.get_cache('api_id_cache', api_name_version)
                api = await api_util.get_api(api_key, api_name_version)
                if not api:
                    return GatewayService.error_response(request_id, 'GTW001', 'API does not exist for the requested name and version')
                if api.get('active') is False:
                    return GatewayService.error_response(request_id, 'GTW012', 'API is disabled', status=403)
                endpoints = await api_util.get_api_endpoints(api.get('api_id'))
                if not endpoints:
                    return GatewayService.error_response(request_id, 'GTW002', 'No endpoints found for the requested API')
                regex_pattern = re.compile(r'\{[^/]+\}')
                match_method = 'GET' if str(request.method).upper() == 'HEAD' else request.method
                composite = match_method + '/' + endpoint_uri
                if not any(re.fullmatch(regex_pattern.sub(r'([^/]+)', ep), composite) for ep in endpoints):
                    logger.error(f'{endpoints} | REST gateway failed with code GTW003')
                    return GatewayService.error_response(request_id, 'GTW003', 'Endpoint does not exist for the requested API')
                client_key = request.headers.get('client-key')
                server = await routing_util.pick_upstream_server(api, request.method, endpoint_uri, client_key)
                if not server:
                    return GatewayService.error_response(request_id, 'GTW001', 'No upstream servers configured')
                logger.info(f'{request_id} | REST gateway to: {server}')
                url = server.rstrip('/') + '/' + endpoint_uri.lstrip('/')
                method = request.method.upper()
                retry = api.get('api_allowed_retry_count') or 0

                if api.get('api_credits_enabled') and username and not bool(api.get('api_public')):
                    if not await credit_util.deduct_credit(api.get('api_credit_group'), username):
                        return GatewayService.error_response(request_id, 'GTW008', 'User does not have any credits', status=401)
            else:
                try:
                    parts = [p for p in (path or '').split('/') if p]
                    api_name_version = ''
                    endpoint_uri = ''
                    if len(parts) >= 2 and parts[1].startswith('v') and parts[1][1:].isdigit():
                        api_name_version = f'/{parts[0]}/{parts[1]}'
                        endpoint_uri = '/'.join(parts[2:])
                    api_key = doorman_cache.get_cache('api_id_cache', api_name_version)
                    api = await api_util.get_api(api_key, api_name_version)
                except Exception:
                    api = None
                    endpoint_uri = ''

            current_time = time.time() * 1000
            query_params = getattr(request, 'query_params', {})
            allowed_headers = api.get('api_allowed_headers') or [] if api else []
            headers = await get_headers(request, allowed_headers)
            headers['X-Request-ID'] = request_id
            if api and api.get('api_credits_enabled'):
                ai_token_headers = await credit_util.get_credit_api_header(api.get('api_credit_group'))
                if ai_token_headers:
                    headers[ai_token_headers[0]] = ai_token_headers[1]

                if username and not bool(api.get('api_public')):
                    user_specific_api_key = await credit_util.get_user_api_key(api.get('api_credit_group'), username)
                    if user_specific_api_key:
                        headers[ai_token_headers[0]] = user_specific_api_key
            content_type = request.headers.get('Content-Type', '').upper()
            logger.info(f'{request_id} | REST gateway to: {url}')
            if api and api.get('api_authorization_field_swap'):
                try:
                    swap_from = api.get('api_authorization_field_swap')
                    source_val = None
                    if swap_from:
                        for key_variant in (swap_from, str(swap_from).lower(), str(swap_from).title()):
                            if key_variant in headers:
                                source_val = headers.get(key_variant)
                                break
                    orig_auth = request.headers.get('Authorization') or request.headers.get('authorization')
                    if source_val is not None and str(source_val).strip() != '':
                        headers['Authorization'] = source_val
                    elif orig_auth is not None and str(orig_auth).strip() != '':
                        headers['Authorization'] = orig_auth
                except Exception:
                    pass

            try:
                lookup_method = 'GET' if str(method).upper() == 'HEAD' else method
                endpoint_doc = await api_util.get_endpoint(api, lookup_method, '/' + endpoint_uri.lstrip('/')) if api else None
                endpoint_id = endpoint_doc.get('endpoint_id') if endpoint_doc else None
                if endpoint_id:
                    if 'JSON' in content_type:
                        body = await request.json()
                        await validation_util.validate_rest_request(endpoint_id, body)
                    elif 'XML' in content_type:
                        body = (await request.body()).decode('utf-8')
                        await validation_util.validate_soap_request(endpoint_id, body)
            except Exception as e:
                logger.error(f'{request_id} | Validation error: {e}')
                return GatewayService.error_response(request_id, 'GTW011', str(e), status=400)
            client = GatewayService.get_http_client()
            try:
                if method == 'GET':
                    http_response = await request_with_resilience(
                        client, 'GET', url,
                        api_key=api.get('api_path') if api else (api_name_version or '/api/rest'),
                        headers=headers, params=query_params,
                        retries=retry,
                        api_config=api,
                    )
                elif method == 'HEAD':
                    http_response = await request_with_resilience(
                        client, 'HEAD', url,
                        api_key=api.get('api_path') if api else (api_name_version or '/api/rest'),
                        headers=headers, params=query_params,
                        retries=retry,
                        api_config=api,
                    )
                elif method in ('POST', 'PUT', 'DELETE', 'PATCH'):
                    cl_header = request.headers.get('content-length') or request.headers.get('Content-Length')
                    try:
                        content_length = int(cl_header) if cl_header is not None and str(cl_header).strip() != '' else 0
                    except Exception:
                        content_length = 0

                    if content_length > 0:
                        if 'JSON' in content_type:
                            body = await request.json()
                            http_response = await request_with_resilience(
                                client, method, url,
                                api_key=api.get('api_path') if api else (api_name_version or '/api/rest'),
                                headers=headers, params=query_params, json=body,
                                retries=retry,
                                api_config=api,
                            )
                        else:
                            body = await request.body()
                            http_response = await request_with_resilience(
                                client, method, url,
                                api_key=api.get('api_path') if api else (api_name_version or '/api/rest'),
                                headers=headers, params=query_params, content=body,
                                retries=retry,
                                api_config=api,
                            )
                    else:
                        http_response = await request_with_resilience(
                            client, method, url,
                            api_key=api.get('api_path') if api else (api_name_version or '/api/rest'),
                            headers=headers, params=query_params,
                            retries=retry,
                            api_config=api,
                        )
                else:
                    return GatewayService.error_response(request_id, 'GTW004', 'Method not supported', status=405)
            finally:
                if os.getenv('ENABLE_HTTPX_CLIENT_CACHE', 'true').lower() == 'false':
                    try:
                        await client.aclose()
                    except Exception:
                        pass
            if str(method).upper() == 'HEAD':
                response_content = ''
            else:
                ctype = (http_response.headers.get('Content-Type') or '').lower()
                if 'application/json' in ctype:
                    try:
                        response_content = http_response.json()
                    except Exception as _e:
                        logger.error(f'{request_id} | REST upstream malformed JSON: {str(_e)}')
                        return ResponseModel(
                            status_code=500,
                            response_headers={'request_id': request_id},
                            error_code='GTW006',
                            error_message='Malformed JSON from upstream'
                        ).dict()
                else:
                    response_content = http_response.text
            backend_end_time = time.time() * 1000
            if http_response.status_code == 404:
                return GatewayService.error_response(request_id, 'GTW005', 'Endpoint does not exist in backend service')
            logger.info(f'{request_id} | REST gateway status code: {http_response.status_code}')
            response_headers = {'request_id': request_id}
            allowed_lower = {h.lower() for h in (allowed_headers or [])}
            for key, value in http_response.headers.items():
                if key.lower() in allowed_lower:
                    response_headers[key] = value

            try:
                origin = request.headers.get('origin') or request.headers.get('Origin')
                _, cors_headers = GatewayService._compute_api_cors_headers(api, origin, None, None)
                response_headers.update(cors_headers)
            except Exception:
                pass
            try:
                if current_time and start_time:
                    response_headers['X-Gateway-Time'] = str(int(current_time - start_time))
                if backend_end_time and current_time:
                    response_headers['X-Backend-Time'] = str(int(backend_end_time - current_time))
            except Exception:
                pass
            return ResponseModel(
                status_code=http_response.status_code,
                response_headers=response_headers,
                response=response_content
            ).dict()
        except CircuitOpenError:
            return ResponseModel(
                status_code=503,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='Upstream circuit open'
            ).dict()
        except httpx.TimeoutException:
            try:
                metrics_store.record_upstream_timeout('rest:' + (api.get('api_path') if api else (api_name_version or '/api/rest')))
            except Exception:
                pass
            return ResponseModel(
                status_code=504,
                response_headers={'request_id': request_id},
                error_code='GTW010',
                error_message='Gateway timeout'
            ).dict()
        except Exception:
            logger.error(f'{request_id} | REST gateway failed with code GTW006', exc_info=True)
            return GatewayService.error_response(request_id, 'GTW006', 'Internal server error', status=500)
        finally:
            if current_time:
                logger.info(f'{request_id} | Gateway time {current_time - start_time}ms')
            if backend_end_time and current_time:
                logger.info(f'{request_id} | Backend time {backend_end_time - current_time}ms')

    @staticmethod
    async def soap_gateway(username, request, request_id, start_time, path, url=None, retry=0):
        """
        External SOAP gateway.
        """
        logger.info(f'{request_id} | SOAP gateway trying resource: {path}')
        current_time = backend_end_time = None
        try:
            if not url:

                parts = [p for p in (path or '').split('/') if p]
                api_name_version = ''
                endpoint_uri = ''
                if len(parts) >= 2 and parts[1].startswith('v') and parts[1][1:].isdigit():
                    api_name_version = f'/{parts[0]}/{parts[1]}'
                    endpoint_uri = '/'.join(parts[2:])
                api_key = doorman_cache.get_cache('api_id_cache', api_name_version)
                api = await api_util.get_api(api_key, api_name_version)
                if not api:
                    return GatewayService.error_response(request_id, 'GTW001', 'API does not exist for the requested name and version')
                if api.get('active') is False:
                    return GatewayService.error_response(request_id, 'GTW012', 'API is disabled', status=403)
                endpoints = await api_util.get_api_endpoints(api.get('api_id'))
                logger.info(f'{request_id} | SOAP gateway endpoints: {endpoints}')
                if not endpoints:
                    return GatewayService.error_response(request_id, 'GTW002', 'No endpoints found for the requested API')
                regex_pattern = re.compile(r'\{[^/]+\}')
                composite = 'POST/' + endpoint_uri
                if not any(re.fullmatch(regex_pattern.sub(r'([^/]+)', ep), composite) for ep in endpoints):
                    return GatewayService.error_response(request_id, 'GTW003', 'Endpoint does not exist for the requested API')
                client_key = request.headers.get('client-key')
                server = await routing_util.pick_upstream_server(api, 'POST', endpoint_uri, client_key)
                if not server:
                    return GatewayService.error_response(request_id, 'GTW001', 'No upstream servers configured')
                url = server.rstrip('/') + '/' + endpoint_uri.lstrip('/')
                logger.info(f'{request_id} | SOAP gateway to: {url}')
                retry = api.get('api_allowed_retry_count') or 0
                if api.get('api_credits_enabled') and username and not bool(api.get('api_public')):
                    if not await credit_util.deduct_credit(api.get('api_credit_group'), username):
                        return GatewayService.error_response(request_id, 'GTW008', 'User does not have any credits', status=401)
            else:
                try:
                    parts = [p for p in (path or '').split('/') if p]
                    api_name_version = ''
                    endpoint_uri = ''
                    if len(parts) >= 3:
                        api_name_version = f'/{parts[0]}/{parts[1]}'
                        endpoint_uri = '/' + '/'.join(parts[2:])
                    api_key = doorman_cache.get_cache('api_id_cache', api_name_version)
                    api = await api_util.get_api(api_key, api_name_version)
                except Exception:
                    api = None
                    endpoint_uri = ''
            current_time = time.time() * 1000
            query_params = getattr(request, 'query_params', {})
            incoming_content_type = request.headers.get('Content-Type') or 'application/xml'
            if incoming_content_type == 'application/xml':
                content_type = 'text/xml; charset=utf-8'
            elif incoming_content_type in ['application/soap+xml', 'text/xml']:
                content_type = incoming_content_type
            else:
                content_type = 'text/xml; charset=utf-8'
            allowed_headers = api.get('api_allowed_headers') or [] if api else []
            headers = await get_headers(request, allowed_headers)
            headers['X-Request-ID'] = request_id
            headers['Content-Type'] = content_type
            if 'SOAPAction' not in headers:
                headers['SOAPAction'] = '""'
            envelope = (await request.body()).decode('utf-8')
            if api and api.get('api_authorization_field_swap'):
                try:
                    swap_from = api.get('api_authorization_field_swap')
                    source_val = None
                    if swap_from:
                        for key_variant in (swap_from, str(swap_from).lower(), str(swap_from).title()):
                            if key_variant in headers:
                                source_val = headers.get(key_variant)
                                break
                    orig_auth = request.headers.get('Authorization') or request.headers.get('authorization')
                    if source_val is not None and str(source_val).strip() != '':
                        headers['Authorization'] = source_val
                    elif orig_auth is not None and str(orig_auth).strip() != '':
                        headers['Authorization'] = orig_auth
                except Exception:
                    pass

            try:
                endpoint_doc = await api_util.get_endpoint(api, 'POST', '/' + endpoint_uri.lstrip('/')) if api else None
                endpoint_id = endpoint_doc.get('endpoint_id') if endpoint_doc else None
                if endpoint_id:
                    await validation_util.validate_soap_request(endpoint_id, envelope)
            except Exception as e:
                logger.error(f'{request_id} | Validation error: {e}')
                return GatewayService.error_response(request_id, 'GTW011', str(e), status=400)
            client = GatewayService.get_http_client()
            try:
                http_response = await request_with_resilience(
                    client, 'POST', url,
                    api_key=api.get('api_path') if api else (api_name_version or '/api/soap'),
                    headers=headers, params=query_params, content=envelope,
                    retries=retry,
                    api_config=api,
                )
            finally:
                if os.getenv('ENABLE_HTTPX_CLIENT_CACHE', 'true').lower() == 'false':
                    try:
                        await client.aclose()
                    except Exception:
                        pass
            response_content = http_response.text
            logger.info(f'{request_id} | SOAP gateway response: {response_content}')
            backend_end_time = time.time() * 1000
            if http_response.status_code == 404:
                return GatewayService.error_response(request_id, 'GTW005', 'Endpoint does not exist in backend service')
            logger.info(f'{request_id} | SOAP gateway status code: {http_response.status_code}')
            response_headers = {'request_id': request_id}
            allowed_lower = {h.lower() for h in (allowed_headers or [])}
            for key, value in http_response.headers.items():
                if key.lower() in allowed_lower:
                    response_headers[key] = value

            try:
                origin = request.headers.get('origin') or request.headers.get('Origin')
                _, cors_headers = GatewayService._compute_api_cors_headers(api, origin, None, None)
                response_headers.update(cors_headers)
            except Exception:
                pass
            try:
                if current_time and start_time:
                    response_headers['X-Gateway-Time'] = str(int(current_time - start_time))
                if backend_end_time and current_time:
                    response_headers['X-Backend-Time'] = str(int(backend_end_time - current_time))
            except Exception:
                pass
            return ResponseModel(
                status_code=http_response.status_code,
                response_headers=response_headers,
                response=response_content
            ).dict()
        except CircuitOpenError:
            return ResponseModel(
                status_code=503,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='Upstream circuit open'
            ).dict()
        except httpx.TimeoutException:
            try:
                metrics_store.record_upstream_timeout('soap:' + (api.get('api_path') if api else '/api/soap'))
            except Exception:
                pass
            return ResponseModel(
                status_code=504,
                response_headers={'request_id': request_id},
                error_code='GTW010',
                error_message='Gateway timeout'
            ).dict()
        except Exception:
            logger.error(f'{request_id} | SOAP gateway failed with code GTW006')
            return GatewayService.error_response(request_id, 'GTW006', 'Internal server error', status=500)
        finally:
            if current_time:
                logger.info(f'{request_id} | Gateway time {current_time - start_time}ms')
            if backend_end_time and current_time:
                logger.info(f'{request_id} | Backend time {backend_end_time - current_time}ms')

    @staticmethod
    async def graphql_gateway(username, request, request_id, start_time, path, url=None, retry=0):
        logger.info(f'{request_id} | GraphQL gateway processing request')
        current_time = backend_end_time = None
        try:
            if not url:
                api_name = path.replace('/api/graphql/', '').replace('graphql/', '')
                api_version = request.headers.get('X-API-Version', 'v1')
                api_path = f'{api_name}/{api_version}'.lstrip('/')
                api = doorman_cache.get_cache('api_cache', api_path)
                if not api:
                    api = await api_util.get_api(None, api_path)
                if not api:
                        logger.error(f'{request_id} | API not found: {api_path}')
                        return GatewayService.error_response(request_id, 'GTW001', f'API does not exist: {api_path}')
                if api.get('active') is False:
                    return GatewayService.error_response(request_id, 'GTW012', 'API is disabled', status=403)
                doorman_cache.set_cache('api_cache', api_path, api)
                retry = api.get('api_allowed_retry_count') or 0
                if api.get('api_credits_enabled') and username and not bool(api.get('api_public')):
                    if not await credit_util.deduct_credit(api.get('api_credit_group'), username):
                        return GatewayService.error_response(request_id, 'GTW008', 'User does not have any credits', status=401)
            current_time = time.time() * 1000
            allowed_headers = api.get('api_allowed_headers') or []
            headers = await get_headers(request, allowed_headers)
            headers['X-Request-ID'] = request_id
            headers['Content-Type'] = 'application/json'
            headers['Accept'] = 'application/json'
            if api.get('api_credits_enabled'):
                ai_token_headers = await credit_util.get_credit_api_header(api.get('api_credit_group'))
                if ai_token_headers:
                    headers[ai_token_headers[0]] = ai_token_headers[1]
                if username and not bool(api.get('api_public')):
                    user_specific_api_key = await credit_util.get_user_api_key(api.get('api_credit_group'), username)
                    if user_specific_api_key:
                        headers[ai_token_headers[0]] = user_specific_api_key
            if api.get('api_authorization_field_swap'):
                try:
                    swap_from = api.get('api_authorization_field_swap')
                    source_val = None
                    if swap_from:
                        for key_variant in (swap_from, str(swap_from).lower(), str(swap_from).title()):
                            if key_variant in headers:
                                source_val = headers.get(key_variant)
                                break
                    orig_auth = request.headers.get('Authorization') or request.headers.get('authorization')
                    if source_val is not None and str(source_val).strip() != '':
                        headers['Authorization'] = source_val
                    elif orig_auth is not None and str(orig_auth).strip() != '':
                        headers['Authorization'] = orig_auth
                except Exception:
                    pass
            body = await request.json()
            query = body.get('query')
            variables = body.get('variables', {})

            try:
                endpoint_doc = await api_util.get_endpoint(api, 'POST', '/graphql')
                endpoint_id = endpoint_doc.get('endpoint_id') if endpoint_doc else None
                if endpoint_id:
                    await validation_util.validate_graphql_request(endpoint_id, query, variables)
            except Exception as e:
                return GatewayService.error_response(request_id, 'GTW011', str(e), status=400)

            result = None
            if hasattr(Client, '__aenter__'):
                try:
                    async with Client(transport=None, fetch_schema_from_transport=False) as session:
                        result = await session.execute(gql(query), variable_values=variables)
                except Exception as _e:
                    logger.debug(f'{request_id} | GraphQL Client execution failed; falling back to HTTP: {_e}')

            if result is None:
                client_key = request.headers.get('client-key')
                server = await routing_util.pick_upstream_server(api, 'POST', '/graphql', client_key)
                if not server:
                    logger.error(f'{request_id} | No upstream servers configured for {api_path}')
                    return GatewayService.error_response(request_id, 'GTW001', 'No upstream servers configured')
                url = server.rstrip('/')
                client = GatewayService.get_http_client()
                try:
                    http_resp = await request_with_resilience(
                        client, 'POST', url,
                        api_key=api_path,
                        headers=headers,
                        json={'query': query, 'variables': variables},
                        retries=retry,
                        api_config=api,
                    )
                except AttributeError:
                    http_resp = await client.post(
                        url,
                        json={'query': query, 'variables': variables},
                        headers=headers,
                    )
                try:
                    data = http_resp.json()
                except Exception as je:
                    data = {
                        'errors': [{
                            'message': f'Invalid JSON from upstream: {str(je)}',
                            'extensions': {'code': 'BAD_RESPONSE'}
                        }]}
                status = getattr(http_resp, 'status_code', 200)
                if status != 200 and 'errors' not in data:
                    data = {'errors': [{
                        'message': data.get('message') or f'HTTP {status}',
                        'extensions': {'code': f'HTTP_{status}'}
                    }]}
                result = data

            backend_end_time = time.time() * 1000
            logger.info(f'{request_id} | GraphQL gateway status code: 200')
            response_headers = {'request_id': request_id}
            allowed_lower = {h.lower() for h in (allowed_headers or [])}
            for key, value in headers.items():
                if key.lower() in allowed_lower:
                    response_headers[key] = value

            try:
                origin = request.headers.get('origin') or request.headers.get('Origin')
                _, cors_headers = GatewayService._compute_api_cors_headers(api, origin, None, None)
                response_headers.update(cors_headers)
            except Exception:
                pass
            try:
                if current_time and start_time:
                    response_headers['X-Gateway-Time'] = str(int(current_time - start_time))
                if backend_end_time and current_time:
                    response_headers['X-Backend-Time'] = str(int(backend_end_time - current_time))
            except Exception:
                pass
            return ResponseModel(status_code=200, response_headers=response_headers, response=result).dict()
        except CircuitOpenError:
            return ResponseModel(
                status_code=503,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='Upstream circuit open'
            ).dict()
        except httpx.TimeoutException:
            try:
                metrics_store.record_upstream_timeout('graphql:' + (api.get('api_path') if api else '/api/graphql'))
            except Exception:
                pass
            return ResponseModel(
                status_code=504,
                response_headers={'request_id': request_id},
                error_code='GTW010',
                error_message='Gateway timeout'
            ).dict()
        except Exception as e:
            logger.error(f'{request_id} | GraphQL gateway failed with code GTW006: {str(e)}')
            error_msg = str(e)[:255] if len(str(e)) > 255 else str(e)
            return GatewayService.error_response(request_id, 'GTW006', error_msg, status=500)
        finally:
            if current_time:
                logger.info(f'{request_id} | Gateway time {current_time - start_time}ms')
            if backend_end_time and current_time:
                logger.info(f'{request_id} | Backend time {backend_end_time - current_time}ms')

    @staticmethod
    async def grpc_gateway(username, request, request_id, start_time, path, api_name=None, url=None, retry=0):
        logger.info(f'{request_id} | gRPC gateway processing request')
        current_time = backend_end_time = None
        try:
            if not url:
                if api_name is None:
                    path_parts = path.strip('/').split('/')
                    if len(path_parts) < 1:
                        logger.error(f'{request_id} | Invalid API path format: {path}')
                        return GatewayService.error_response(request_id, 'GTW001', 'Invalid API path format', status=404)
                    api_name = path_parts[-1]
                api_version = request.headers.get('X-API-Version', 'v1')
                api_path = f'{api_name}/{api_version}'
                logger.info(f'{request_id} | Processing gRPC request for API: {api_path}')

                try:
                    body = await request.json()
                    if not isinstance(body, dict):
                        logger.error(f'{request_id} | Invalid request body format')
                        return GatewayService.error_response(request_id, 'GTW011', 'Invalid request body format', status=400)
                except json.JSONDecodeError:
                    logger.error(f'{request_id} | Invalid JSON in request body')
                    return GatewayService.error_response(request_id, 'GTW011', 'Invalid JSON in request body', status=400)

                parsed = GatewayService._parse_and_validate_method(body.get('method'))
                if not parsed:
                    return GatewayService.error_response(request_id, 'GTW011', 'Invalid gRPC method. Use Service.Method with alphanumerics/underscore.', status=400)
                _service_name_preview, _method_name_preview = parsed
                pkg_override_raw = (body.get('package') or '').strip()
                if pkg_override_raw:
                    if GatewayService._validate_package_name(pkg_override_raw) is None:
                        return GatewayService.error_response(request_id, 'GTW011', 'Invalid gRPC package. Use letters, digits, underscore only.', status=400)

                api = doorman_cache.get_cache('api_cache', api_path)
                if not api:
                    api = await api_util.get_api(None, api_path)
                if api:
                    try:
                        endpoint_doc = await api_util.get_endpoint(api, 'POST', '/grpc')
                        endpoint_id = endpoint_doc.get('endpoint_id') if endpoint_doc else None
                        if endpoint_id:
                            await validation_util.validate_grpc_request(endpoint_id, body.get('message'))
                    except Exception as e:
                        return GatewayService.error_response(request_id, 'GTW011', str(e), status=400)
                api_pkg_raw = None
                try:
                    api_pkg_raw = (api.get('api_grpc_package') or '').strip() if api else None
                except Exception:
                    api_pkg_raw = None
                pkg_override = (body.get('package') or '').strip() or None
                api_pkg = GatewayService._validate_package_name(api_pkg_raw) if api_pkg_raw else None
                pkg_override_valid = GatewayService._validate_package_name(pkg_override) if pkg_override else None
                default_base = f'{api_name}_{api_version}'.replace('-', '_')
                if not GatewayService._is_valid_identifier(default_base):
                    default_base = ''.join(ch if ch in GatewayService._IDENT_ALLOWED else '_' for ch in default_base)
                module_base = (api_pkg or pkg_override_valid or default_base)
                try:
                    logger.info(
                        f"{request_id} | gRPC module_base resolved: module_base={module_base} "
                        f"api_pkg={api_pkg_raw!r} pkg_override={pkg_override_raw!r} default_base={default_base}"
                    )
                except Exception:
                    pass

                try:
                    allowed_pkgs = api.get('api_grpc_allowed_packages') if api else None
                    allowed_svcs = api.get('api_grpc_allowed_services') if api else None
                    allowed_methods = api.get('api_grpc_allowed_methods') if api else None

                    service_name, method_name = _service_name_preview, _method_name_preview

                    if allowed_pkgs and isinstance(allowed_pkgs, list):
                        if module_base not in allowed_pkgs:
                            return GatewayService.error_response(
                                request_id, 'GTW013', 'gRPC package not allowed', status=403
                            )
                    if allowed_svcs and isinstance(allowed_svcs, list):
                        if service_name not in allowed_svcs:
                            return GatewayService.error_response(
                                request_id, 'GTW013', 'gRPC service not allowed', status=403
                            )
                    if allowed_methods and isinstance(allowed_methods, list):
                        method_fq = f"{service_name}.{method_name}"
                        if method_fq not in allowed_methods:
                            return GatewayService.error_response(
                                request_id, 'GTW013', 'gRPC method not allowed', status=403
                            )
                except Exception:
                    return GatewayService.error_response(
                        request_id, 'GTW013', 'gRPC target not allowed', status=403
                    )
                proto_rel = Path(module_base.replace('.', '/'))
                proto_filename = f'{proto_rel.name}.proto'
                project_root = GatewayService._PROJECT_ROOT
                proto_dir = project_root / 'proto'
                proto_path = proto_dir / proto_rel.with_suffix('.proto')
                if not GatewayService._validate_under_base(project_root, proto_path):
                    return GatewayService.error_response(request_id, 'GTW012', 'Invalid path for proto resolution', status=400)

                generated_dir = project_root / 'generated'
                gen_dir_str = str(generated_dir)
                proj_root_str = str(project_root)
                if proj_root_str not in sys.path:
                    sys.path.insert(0, proj_root_str)
                if gen_dir_str not in sys.path:
                    sys.path.insert(0, gen_dir_str)
                try:
                    logger.info(f"{request_id} | sys.path updated for gRPC import. project_root={proj_root_str}, generated_dir={gen_dir_str}")
                except Exception:
                    pass

                pb2 = None
                pb2_grpc = None
                try:
                    pb2_name = f'{module_base}_pb2'
                    pb2_grpc_name = f'{module_base}_pb2_grpc'
                    try:
                        pb2 = importlib.import_module(pb2_name)
                        pb2_grpc = importlib.import_module(pb2_grpc_name)
                    except ModuleNotFoundError:
                        gen_pb2_name = f'generated.{module_base}_pb2'
                        gen_pb2_grpc_name = f'generated.{module_base}_pb2_grpc'
                        pb2 = importlib.import_module(gen_pb2_name)
                        pb2_grpc = importlib.import_module(gen_pb2_grpc_name)
                    logger.info(f"{request_id} | Successfully imported gRPC modules: {pb2.__name__} and {pb2_grpc.__name__}")
                except ModuleNotFoundError as mnf_exc:
                    logger.warning(f"{request_id} | gRPC modules not found, will attempt proto generation: {str(mnf_exc)}")
                except ImportError as imp_exc:
                    logger.error(f"{request_id} | ImportError loading gRPC modules (likely broken import in generated file): {str(imp_exc)}")
                    mod_pb2 = f'{module_base}_pb2'
                    mod_pb2_grpc = f'{module_base}_pb2_grpc'
                    if mod_pb2 in sys.modules:
                        del sys.modules[mod_pb2]
                    if mod_pb2_grpc in sys.modules:
                        del sys.modules[mod_pb2_grpc]
                    return GatewayService.error_response(
                        request_id,
                        'GTW012',
                        f'Failed to import gRPC modules. Proto files may need regeneration. Error: {str(imp_exc)[:100]}',
                        status=404
                    )
                except Exception as import_exc:
                    logger.error(f"{request_id} | Unexpected error importing gRPC modules: {type(import_exc).__name__}: {str(import_exc)}")
                    return GatewayService.error_response(
                        request_id,
                        'GTW012',
                        f'Unexpected error importing gRPC modules: {type(import_exc).__name__}',
                        status=500
                    )

                if pb2 is None or pb2_grpc is None:
                    try:
                        proto_dir.mkdir(exist_ok=True)
                        try:
                            logger.info(f"{request_id} | gRPC generated check: proto_path={proto_path} exists={proto_path.exists()} generated_dir={generated_dir} pb2={module_base}_pb2.py={ (generated_dir / (module_base + '_pb2.py')).exists() }")
                        except Exception:
                            pass
                        method_fq = body.get('method', '')
                        parsed_m = GatewayService._parse_and_validate_method(method_fq)
                        if not parsed_m:
                            raise ValueError('Invalid method format')
                        service_name, method_name = parsed_m
                        module_name = module_base
                        proto_content = (
                            'syntax = "proto3";\n'
                            f'package {module_name};\n'
                            f'service {service_name} {{\n'
                            '  rpc Create (CreateRequest) returns (CreateReply) {}\n'
                            '  rpc Read (ReadRequest) returns (ReadReply) {}\n'
                            '  rpc Update (UpdateRequest) returns (UpdateReply) {}\n'
                            '  rpc Delete (DeleteRequest) returns (DeleteReply) {}\n'
                            '}\n'
                            'message CreateRequest { string name = 1; }\n'
                            'message CreateReply { string message = 1; }\n'
                            'message ReadRequest { int32 id = 1; }\n'
                            'message ReadReply { string message = 1; }\n'
                            'message UpdateRequest { int32 id = 1; string name = 2; }\n'
                            'message UpdateReply { string message = 1; }\n'
                            'message DeleteRequest { int32 id = 1; }\n'
                            'message DeleteReply { bool ok = 1; }\n'
                        )
                        proto_path.write_text(proto_content, encoding='utf-8')
                        generated_dir = project_root / 'generated'
                        generated_dir.mkdir(exist_ok=True)
                        try:
                            from grpc_tools import protoc as _protoc
                            code = _protoc.main([
                                'protoc', f'--proto_path={str(proto_dir)}', f'--python_out={str(generated_dir)}', f'--grpc_python_out={str(generated_dir)}', str(proto_path)
                            ])
                            if code != 0:
                                raise RuntimeError(f'protoc returned {code}')
                            init_path = generated_dir / '__init__.py'
                            if not init_path.exists():
                                init_path.write_text('"""Generated gRPC code."""\n', encoding='utf-8')
                        except Exception as ge:
                            logger.error(f'{request_id} | On-demand proto generation failed: {ge}')
                            if os.getenv('DOORMAN_TEST_MODE', '').lower() == 'true':
                                pb2 = type('PB2', (), {})
                                pb2_grpc = type('SVC', (), {})
                            else:
                                return GatewayService.error_response(request_id, 'GTW012', f'Proto file not found for API: {api_path}', status=404)
                    except Exception as ge:
                        logger.error(f'{request_id} | Proto file not found and generation skipped: {ge}')
                        if os.getenv('DOORMAN_TEST_MODE', '').lower() != 'true':
                            return GatewayService.error_response(request_id, 'GTW012', f'Proto file not found for API: {api_path}', status=404)
                api = doorman_cache.get_cache('api_cache', api_path)
                if not api:
                    api = await api_util.get_api(None, api_path)
                    if not api:
                        logger.error(f'{request_id} | API not found: {api_path}')
                        return GatewayService.error_response(request_id, 'GTW001', f'API does not exist: {api_path}', status=404)
                doorman_cache.set_cache('api_cache', api_path, api)
                client_key = request.headers.get('client-key')
                server = await routing_util.pick_upstream_server(api, 'POST', '/grpc', client_key)
                if not server:
                    logger.error(f'{request_id} | No upstream servers configured for {api_path}')
                    return GatewayService.error_response(request_id, 'GTW001', 'No upstream servers configured', status=404)
                url = server.rstrip('/')
                if url.startswith('grpc://'):
                    url = url[7:]
                retry = api.get('api_allowed_retry_count') or 0
                if api.get('api_credits_enabled') and username and not bool(api.get('api_public')):
                    if not await credit_util.deduct_credit(api.get('api_credit_group'), username):
                        return GatewayService.error_response(request_id, 'GTW008', 'User does not have any credits', status=401)
            current_time = time.time() * 1000
            try:
                if not url:
                    pass
                else:
                    api_version = request.headers.get('X-API-Version', 'v1')
                    if not api_name:
                        path_parts = (path or '').strip('/').split('/')
                        api_name = path_parts[-1] if path_parts else None
                    if api_name:
                        api_path = f'{api_name}/{api_version}'
                        api = doorman_cache.get_cache('api_cache', api_path) or await api_util.get_api(None, api_path)
                        try:
                            api_pkg_raw = (api.get('api_grpc_package') or '').strip() if api else None
                        except Exception:
                            api_pkg_raw = None
                        pkg_override = (body.get('package') or '').strip() or None
                        api_pkg = GatewayService._validate_package_name(api_pkg_raw) if api_pkg_raw else None
                        pkg_override_valid = GatewayService._validate_package_name(pkg_override) if pkg_override else None
                        default_base = f'{api_name}_{api_version}'.replace('-', '_')
                        if not GatewayService._is_valid_identifier(default_base):
                            default_base = ''.join(ch if ch in GatewayService._IDENT_ALLOWED else '_' for ch in default_base)
                        module_base = (api_pkg or pkg_override_valid or default_base)
                        try:
                            allowed_pkgs = api.get('api_grpc_allowed_packages') if api else None
                            allowed_svcs = api.get('api_grpc_allowed_services') if api else None
                            allowed_methods = api.get('api_grpc_allowed_methods') if api else None

                            prev_parsed = GatewayService._parse_and_validate_method(body.get('method'))
                            if prev_parsed:
                                svc_name, mth_name = prev_parsed
                            else:
                                svc_name, mth_name = None, None

                            if allowed_pkgs and isinstance(allowed_pkgs, list):
                                if module_base not in allowed_pkgs:
                                    return GatewayService.error_response(
                                        request_id, 'GTW013', 'gRPC package not allowed', status=403
                                    )
                            if svc_name and allowed_svcs and isinstance(allowed_svcs, list):
                                if svc_name not in allowed_svcs:
                                    return GatewayService.error_response(
                                        request_id, 'GTW013', 'gRPC service not allowed', status=403
                                    )
                            if svc_name and mth_name and allowed_methods and isinstance(allowed_methods, list):
                                if f"{svc_name}.{mth_name}" not in allowed_methods:
                                    return GatewayService.error_response(
                                        request_id, 'GTW013', 'gRPC method not allowed', status=403
                                    )
                        except Exception:
                            return GatewayService.error_response(
                                request_id, 'GTW013', 'gRPC target not allowed', status=403
                            )
            except Exception:
                pass
            allowed_headers = (api or {}).get('api_allowed_headers') or []
            headers = await get_headers(request, allowed_headers)
            headers['X-Request-ID'] = request_id
            try:
                body = await request.json()
                if not isinstance(body, dict):
                    logger.error(f'{request_id} | Invalid request body format')
                    return GatewayService.error_response(request_id, 'GTW011', 'Invalid request body format', status=400)
            except json.JSONDecodeError:
                logger.error(f'{request_id} | Invalid JSON in request body')
                return GatewayService.error_response(request_id, 'GTW011', 'Invalid JSON in request body', status=400)
            if 'method' not in body:
                logger.error(f'{request_id} | Missing method in request body')
                return GatewayService.error_response(request_id, 'GTW011', 'Missing method in request body', status=400)
            if 'message' not in body:
                logger.error(f'{request_id} | Missing message in request body')
                return GatewayService.error_response(request_id, 'GTW011', 'Missing message in request body', status=400)
            parsed_method = GatewayService._parse_and_validate_method(body.get('method'))
            if not parsed_method:
                return GatewayService.error_response(request_id, 'GTW011', 'Invalid gRPC method. Use Service.Method with alphanumerics/underscore.', status=400)
            pkg_override = (body.get('package') or '').strip() or None
            if pkg_override and GatewayService._validate_package_name(pkg_override) is None:
                return GatewayService.error_response(request_id, 'GTW011', 'Invalid gRPC package. Use letters, digits, underscore only.', status=400)
            try:
                svc_name, mth_name = parsed_method
                allowed_pkgs = api.get('api_grpc_allowed_packages') if api else None
                allowed_svcs = api.get('api_grpc_allowed_services') if api else None
                allowed_methods = api.get('api_grpc_allowed_methods') if api else None
                if allowed_pkgs and isinstance(allowed_pkgs, list) and module_base not in allowed_pkgs:
                    return GatewayService.error_response(request_id, 'GTW013', 'gRPC package not allowed', status=403)
                if allowed_svcs and isinstance(allowed_svcs, list) and svc_name not in allowed_svcs:
                    return GatewayService.error_response(request_id, 'GTW013', 'gRPC service not allowed', status=403)
                if allowed_methods and isinstance(allowed_methods, list) and f"{svc_name}.{mth_name}" not in allowed_methods:
                    return GatewayService.error_response(request_id, 'GTW013', 'gRPC method not allowed', status=403)
            except Exception:
                return GatewayService.error_response(request_id, 'GTW013', 'gRPC target not allowed', status=403)
            proto_rel = Path(module_base.replace('.', '/'))
            proto_filename = f'{proto_rel.name}.proto'

            try:
                endpoint_doc = await api_util.get_endpoint(api, 'POST', '/grpc')
                endpoint_id = endpoint_doc.get('endpoint_id') if endpoint_doc else None
                if endpoint_id:
                    await validation_util.validate_grpc_request(endpoint_id, body.get('message'))
            except Exception as e:
                return GatewayService.error_response(request_id, 'GTW011', str(e), status=400)
            proto_path = (GatewayService._PROJECT_ROOT / 'proto' / proto_rel.with_suffix('.proto'))
            use_imported = False
            try:
                if 'pb2' in locals() and 'pb2_grpc' in locals():
                    use_imported = (pb2 is not None and pb2_grpc is not None)
            except Exception:
                use_imported = False
            module_name = module_base
            generated_dir = GatewayService._PROJECT_ROOT / 'generated'
            gen_dir_str = str(generated_dir)
            proj_root_str = str(GatewayService._PROJECT_ROOT)
            if proj_root_str not in sys.path:
                sys.path.insert(0, proj_root_str)
            if gen_dir_str not in sys.path:
                sys.path.insert(0, gen_dir_str)
            try:
                logger.info(f"{request_id} | sys.path prepared for import: project_root={proj_root_str}, generated_dir={gen_dir_str}")
            except Exception:
                pass
            parts = module_name.split('.') if '.' in module_name else [module_name]
            package_dir = generated_dir.joinpath(*parts[:-1]) if len(parts) > 1 else generated_dir
            pb2_module = None
            service_module = None
            if use_imported:
                pb2_module = pb2
                service_module = pb2_grpc
                logger.info(f"{request_id} | Using imported gRPC modules for {module_name}")
            else:
                if not proto_path.exists():
                    if os.getenv('DOORMAN_TEST_MODE', '').lower() == 'true':
                        try:
                            pb2_module = importlib.import_module(f'{module_name}_pb2')
                            service_module = importlib.import_module(f'{module_name}_pb2_grpc')
                            use_imported = True
                        except Exception:
                            logger.error(f'{request_id} | Proto file not found: {str(proto_path)}')
                            return GatewayService.error_response(request_id, 'GTW012', f'Proto file not found for API: {api_path}', status=404)
                if not use_imported:
                    pb2_path = package_dir / f"{parts[-1]}_pb2.py"
                    pb2_grpc_path = package_dir / f"{parts[-1]}_pb2_grpc.py"
                    if not (pb2_path.is_file() and pb2_grpc_path.is_file()):
                        logger.error(f"{request_id} | Generated modules not found for '{module_name}' pb2={pb2_path} exists={pb2_path.is_file()} pb2_grpc={pb2_grpc_path} exists={pb2_grpc_path.is_file()}")
                        if isinstance(url, str) and url.startswith(('http://', 'https://')):
                            try:
                                client = GatewayService.get_http_client()
                                http_url = url.rstrip('/') + '/grpc'
                                http_response = await client.post(http_url, json=body, headers=headers)
                            finally:
                                if os.getenv('ENABLE_HTTPX_CLIENT_CACHE', 'false').lower() != 'true':
                                    try:
                                        await client.aclose()
                                    except Exception:
                                        pass
                            if http_response.status_code == 404:
                                return GatewayService.error_response(request_id, 'GTW005', 'Endpoint does not exist in backend service')
                            response_headers = {'request_id': request_id}
                            try:
                                if current_time and start_time:
                                    response_headers['X-Gateway-Time'] = str(int(current_time - start_time))
                            except Exception:
                                pass
                            return ResponseModel(
                                status_code=http_response.status_code,
                                response_headers=response_headers,
                                response=(http_response.json() if http_response.headers.get('Content-Type','').startswith('application/json') else http_response.text)
                            ).dict()
                        return GatewayService.error_response(request_id, 'GTW012', f'Generated gRPC modules not found for package: {module_name}', status=404)
                if not use_imported:
                    try:
                        if GatewayService._validate_package_name(module_name) is None:
                            return GatewayService.error_response(request_id, 'GTW012', 'Invalid gRPC module name', status=400)
                        import_name_pb2 = f'{module_name}_pb2'
                        import_name_grpc = f'{module_name}_pb2_grpc'
                        logger.info(f"{request_id} | Importing generated modules: {import_name_pb2} and {import_name_grpc}")
                        try:
                            pb2_module = importlib.import_module(import_name_pb2)
                            service_module = importlib.import_module(import_name_grpc)
                        except ModuleNotFoundError:
                            alt_pb2 = f'generated.{module_name}_pb2'
                            alt_grpc = f'generated.{module_name}_pb2_grpc'
                            logger.info(f"{request_id} | Retrying import via generated package: {alt_pb2} and {alt_grpc}")
                            pb2_module = importlib.import_module(alt_pb2)
                            service_module = importlib.import_module(alt_grpc)
                    except ImportError as e:
                        logger.error(f'{request_id} | Failed to import gRPC module: {str(e)}', exc_info=True)
                        if isinstance(url, str) and url.startswith(('http://', 'https://')):
                            try:
                                client = GatewayService.get_http_client()
                                http_url = url.rstrip('/') + '/grpc'
                                http_response = await client.post(http_url, json=body, headers=headers)
                            finally:
                                if os.getenv('ENABLE_HTTPX_CLIENT_CACHE', 'false').lower() != 'true':
                                    try:
                                        await client.aclose()
                                    except Exception:
                                        pass
                            if http_response.status_code == 404:
                                return GatewayService.error_response(request_id, 'GTW005', 'Endpoint does not exist in backend service')
                            response_headers = {'request_id': request_id}
                            try:
                                if current_time and start_time:
                                    response_headers['X-Gateway-Time'] = str(int(current_time - start_time))
                            except Exception:
                                pass
                            return ResponseModel(
                                status_code=http_response.status_code,
                                response_headers=response_headers,
                                response=(http_response.json() if http_response.headers.get('Content-Type','').startswith('application/json') else http_response.text)
                            ).dict()
                        return GatewayService.error_response(request_id, 'GTW012', f'Failed to import gRPC module: {str(e)}', status=404)
            parsed = GatewayService._parse_and_validate_method(body.get('method'))
            if not parsed:
                return GatewayService.error_response(request_id, 'GTW011', 'Invalid gRPC method. Use Service.Method with alphanumerics/underscore.', status=400)
            service_name, method_name = parsed
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                try:
                    client = GatewayService.get_http_client()
                    http_url = url.rstrip('/') + '/grpc'
                    http_response = await client.post(http_url, json=body, headers=headers)
                finally:
                    if os.getenv('ENABLE_HTTPX_CLIENT_CACHE', 'false').lower() != 'true':
                        try:
                            await client.aclose()
                        except Exception:
                            pass
                if http_response.status_code == 404:
                    return GatewayService.error_response(request_id, 'GTW005', 'Endpoint does not exist in backend service')
                response_headers = {'request_id': request_id}
                try:
                    if current_time and start_time:
                        response_headers['X-Gateway-Time'] = str(int(current_time - start_time))
                except Exception:
                    pass
                return ResponseModel(
                    status_code=http_response.status_code,
                    response_headers=response_headers,
                    response=(http_response.json() if http_response.headers.get('Content-Type','').startswith('application/json') else http_response.text)
                ).dict()

            logger.info(f"{request_id} | Connecting to gRPC upstream: {url}")
            channel = grpc.aio.insecure_channel(url)
            try:
                await asyncio.wait_for(channel.channel_ready(), timeout=2.0)
            except Exception:
                pass
            request_class_name = f'{method_name}Request'
            reply_class_name = f'{method_name}Reply'

            try:
                logger.info(f"{request_id} | Resolving message types: {request_class_name} and {reply_class_name} from pb2_module={getattr(pb2_module, '__name__', 'unknown')}")

                if pb2_module is None:
                    logger.error(f'{request_id} | pb2_module is None - cannot resolve message types')
                    return GatewayService.error_response(
                        request_id,
                        'GTW012',
                        'Internal error: protobuf module not loaded',
                        status=500
                    )

                try:
                    request_class = getattr(pb2_module, request_class_name)
                    reply_class = getattr(pb2_module, reply_class_name)
                except AttributeError as attr_err:
                    logger.error(f'{request_id} | Message types not found in pb2_module: {str(attr_err)}')
                    return GatewayService.error_response(
                        request_id,
                        'GTW006',
                        f'Message types {request_class_name}/{reply_class_name} not found in protobuf module',
                        status=500
                    )

                try:
                    request_message = request_class()
                    logger.info(f'{request_id} | Successfully created request message of type {request_class_name}')
                except Exception as create_err:
                    logger.error(f'{request_id} | Failed to instantiate request message: {type(create_err).__name__}: {str(create_err)}')
                    return GatewayService.error_response(
                        request_id,
                        'GTW006',
                        f'Failed to create request message: {type(create_err).__name__}',
                        status=500
                    )

            except Exception as e:
                logger.error(f'{request_id} | Unexpected error in message type resolution: {type(e).__name__}: {str(e)}')
                return GatewayService.error_response(
                    request_id,
                    'GTW012',
                    f'Unexpected error resolving message types: {type(e).__name__}',
                    status=500
                )
            for key, value in body['message'].items():
                try:
                    setattr(request_message, key, value)
                except Exception:
                    pass
            attempts = max(1, int(retry) + 1)
            env_max_retries = 0
            try:
                env_max_retries = int(os.getenv('GRPC_MAX_RETRIES', '0'))
            except Exception:
                env_max_retries = 0
            attempts = max(attempts, env_max_retries + 1)

            base_ms = 0
            max_ms = 0
            jitter = 0.5
            try:
                base_ms = int(os.getenv('GRPC_RETRY_BASE_MS', '100'))
                max_ms = int(os.getenv('GRPC_RETRY_MAX_MS', '1000'))
            except Exception:
                base_ms, max_ms = 100, 1000

            stream_mode = str((body.get('stream') or body.get('streaming') or '')).lower()
            idempotent_override = body.get('idempotent')
            if idempotent_override is not None:
                is_idempotent = bool(idempotent_override)
            else:
                is_idempotent = not (stream_mode.startswith('client') or stream_mode.startswith('bidi') or stream_mode.startswith('bi'))

            retryable = {
                grpc.StatusCode.UNAVAILABLE,
                grpc.StatusCode.DEADLINE_EXCEEDED,
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                grpc.StatusCode.ABORTED,
            }

            last_exc = None
            retries_made = 0
            final_code_name = 'OK'
            got_response = False
            try:
                logger.info(f"{request_id} | gRPC entering attempts={attempts} stream_mode={stream_mode or 'unary'} method={service_name}.{method_name}")
            except Exception:
                pass
            for attempt in range(attempts):
                try:
                    full_method = f'/{module_base}.{service_name}/{method_name}'
                    try:
                        logger.info(f"{request_id} | gRPC attempt={attempt+1}/{attempts} calling {full_method}")
                    except Exception:
                        pass
                    req_ser = getattr(request_message, 'SerializeToString', None)
                    if not callable(req_ser):
                        req_ser = (lambda _m: b'')
                    metadata_list = GatewayService._sanitize_grpc_metadata(headers or {})
                    if stream_mode.startswith('server'):
                        call = channel.unary_stream(
                            full_method,
                            request_serializer=req_ser,
                            response_deserializer=reply_class.FromString,
                        )
                        items = []
                        max_items = int(body.get('max_items') or 50)
                        async for msg in call(request_message, metadata=metadata_list):
                            d = {}
                            try:
                                for field in msg.DESCRIPTOR.fields:
                                    d[field.name] = getattr(msg, field.name)
                            except Exception:
                                pass
                            items.append(d)
                            if len(items) >= max_items:
                                break
                        response = type('R', (), {'DESCRIPTOR': type('D', (), {'fields': []})(), 'ok': True, '_items': items})()
                        got_response = True
                    elif stream_mode.startswith('client'):
                        try:
                            stream = channel.stream_unary(
                                full_method,
                                request_serializer=req_ser,
                                response_deserializer=reply_class.FromString,
                            )
                        except AttributeError:
                            stream = None
                        async def _gen_client():
                            msgs = body.get('messages') or []
                            if not msgs:
                                yield request_message
                                return
                            for itm in msgs:
                                try:
                                    msg = request_class()
                                    if isinstance(itm, dict):
                                        for k, v in itm.items():
                                            try:
                                                setattr(msg, k, v)
                                            except Exception:
                                                pass
                                    else:
                                        msg = request_message
                                    yield msg
                                except Exception:
                                    yield request_message
                        if stream is not None:
                            try:
                                response = await stream(_gen_client(), metadata=metadata_list)
                            except TypeError:
                                response = await stream(_gen_client())
                            got_response = True
                        else:
                            unary = channel.unary_unary(
                                full_method,
                                request_serializer=req_ser,
                                response_deserializer=reply_class.FromString,
                            )
                            try:
                                response = await unary(request_message, metadata=metadata_list)
                            except TypeError:
                                response = await unary(request_message)
                            got_response = True
                    elif stream_mode.startswith('bidi') or stream_mode.startswith('bi'):
                        try:
                            bidi = channel.stream_stream(
                                full_method,
                                request_serializer=req_ser,
                                response_deserializer=reply_class.FromString,
                            )
                        except AttributeError:
                            bidi = None
                        async def _gen_bidi():
                            msgs = body.get('messages') or []
                            if not msgs:
                                yield request_message
                                return
                            for itm in msgs:
                                try:
                                    msg = request_class()
                                    if isinstance(itm, dict):
                                        for k, v in itm.items():
                                            try:
                                                setattr(msg, k, v)
                                            except Exception:
                                                pass
                                    else:
                                        msg = request_message
                                    yield msg
                                except Exception:
                                    yield request_message
                        items = []
                        max_items = int(body.get('max_items') or 50)
                        if bidi is not None:
                            try:
                                async for msg in bidi(_gen_bidi(), metadata=metadata_list):
                                    d = {}
                                    try:
                                        for field in msg.DESCRIPTOR.fields:
                                            d[field.name] = getattr(msg, field.name)
                                    except Exception:
                                        pass
                                    items.append(d)
                                    if len(items) >= max_items:
                                        break
                            except TypeError:
                                async for msg in bidi(_gen_bidi()):
                                    d = {}
                                    try:
                                        for field in msg.DESCRIPTOR.fields:
                                            d[field.name] = getattr(msg, field.name)
                                    except Exception:
                                        pass
                                    items.append(d)
                                    if len(items) >= max_items:
                                        break
                        response = type('R', (), {'DESCRIPTOR': type('D', (), {'fields': []})(), 'ok': True, '_items': items})()
                        got_response = True
                    else:
                        unary = channel.unary_unary(
                            full_method,
                            request_serializer=req_ser,
                            response_deserializer=reply_class.FromString,
                        )
                        try:
                            response = await unary(request_message, metadata=metadata_list)
                        except TypeError:
                            response = await unary(request_message)
                        got_response = True
                    last_exc = None
                    try:
                        logger.info(f"{request_id} | gRPC unary success; stream_mode={stream_mode or 'unary'}")
                    except Exception:
                        pass
                    break
                except Exception as e2:
                    last_exc = e2
                    try:
                        code = getattr(e2, 'code', lambda: None)()
                        cname = str(getattr(code, 'name', '') or 'UNKNOWN')
                        logger.info(f"{request_id} | gRPC primary call raised: {cname}")
                    except Exception:
                        logger.info(f"{request_id} | gRPC primary call raised non-grpc exception")
                    final_code_name = str(code.name) if getattr(code, 'name', None) else 'ERROR'
                    if attempt < attempts - 1 and is_idempotent and code in retryable:
                        retries_made += 1
                        delay = min(max_ms, base_ms * (2 ** attempt)) / 1000.0
                        jitter_factor = 1.0 + (random.random() * jitter - (jitter / 2.0))
                        await asyncio.sleep(max(0.01, delay * jitter_factor))
                        continue
                    try:
                        alt_method = f'/{service_name}/{method_name}'
                        req_ser = getattr(request_message, 'SerializeToString', None)
                        if not callable(req_ser):
                            req_ser = (lambda _m: b'')
                        if stream_mode.startswith('server'):
                            call2 = channel.unary_stream(
                                alt_method,
                                request_serializer=req_ser,
                                response_deserializer=reply_class.FromString,
                            )
                            items = []
                            max_items = int(body.get('max_items') or 50)
                            async for msg in call2(request_message, metadata=metadata_list):
                                d = {}
                                try:
                                    for field in msg.DESCRIPTOR.fields:
                                        d[field.name] = getattr(msg, field.name)
                                except Exception:
                                    pass
                                items.append(d)
                                if len(items) >= max_items:
                                    break
                            response = type('R', (), {'DESCRIPTOR': type('D', (), {'fields': []})(), 'ok': True, '_items': items})()
                            got_response = True
                        elif stream_mode.startswith('client'):
                            try:
                                stream2 = channel.stream_unary(
                                    alt_method,
                                    request_serializer=req_ser,
                                    response_deserializer=reply_class.FromString,
                                )
                            except AttributeError:
                                stream2 = None
                            async def _gen_client_alt():
                                msgs = body.get('messages') or []
                                if not msgs:
                                    yield request_message
                                    return
                                for itm in msgs:
                                    try:
                                        msg = request_class()
                                        if isinstance(itm, dict):
                                            for k, v in itm.items():
                                                try:
                                                    setattr(msg, k, v)
                                                except Exception:
                                                    pass
                                        else:
                                            msg = request_message
                                        yield msg
                                    except Exception:
                                        yield request_message
                            if stream2 is not None:
                                try:
                                    response = await stream2(_gen_client_alt(), metadata=metadata_list)
                                except TypeError:
                                    response = await stream2(_gen_client_alt())
                                got_response = True
                            else:
                                unary2 = channel.unary_unary(
                                    alt_method,
                                    request_serializer=req_ser,
                                    response_deserializer=reply_class.FromString,
                                )
                                try:
                                    response = await unary2(request_message, metadata=metadata_list)
                                except TypeError:
                                    response = await unary2(request_message)
                                got_response = True
                        elif stream_mode.startswith('bidi') or stream_mode.startswith('bi'):
                            try:
                                bidi2 = channel.stream_stream(
                                    alt_method,
                                    request_serializer=req_ser,
                                    response_deserializer=reply_class.FromString,
                                )
                            except AttributeError:
                                bidi2 = None
                            async def _gen_bidi_alt():
                                msgs = body.get('messages') or []
                                if not msgs:
                                    yield request_message
                                    return
                                for itm in msgs:
                                    try:
                                        msg = request_class()
                                        if isinstance(itm, dict):
                                            for k, v in itm.items():
                                                try:
                                                    setattr(msg, k, v)
                                                except Exception:
                                                    pass
                                        else:
                                            msg = request_message
                                        yield msg
                                    except Exception:
                                        yield request_message
                            items = []
                            max_items = int(body.get('max_items') or 50)
                            if bidi2 is not None:
                                try:
                                    async for msg in bidi2(_gen_bidi_alt(), metadata=metadata_list):
                                        d = {}
                                        try:
                                            for field in msg.DESCRIPTOR.fields:
                                                d[field.name] = getattr(msg, field.name)
                                        except Exception:
                                            pass
                                        items.append(d)
                                        if len(items) >= max_items:
                                            break
                                except TypeError:
                                    async for msg in bidi2(_gen_bidi_alt()):
                                        d = {}
                                        try:
                                            for field in msg.DESCRIPTOR.fields:
                                                d[field.name] = getattr(msg, field.name)
                                        except Exception:
                                            pass
                                        items.append(d)
                                        if len(items) >= max_items:
                                            break
                            response = type('R', (), {'DESCRIPTOR': type('D', (), {'fields': []})(), 'ok': True, '_items': items})()
                            got_response = True
                        else:
                            unary2 = channel.unary_unary(
                                alt_method,
                                request_serializer=req_ser,
                                response_deserializer=reply_class.FromString,
                            )
                            try:
                                response = await unary2(request_message, metadata=metadata_list)
                            except TypeError:
                                response = await unary2(request_message)
                            got_response = True
                        last_exc = None
                        break
                    except Exception as e3:
                        last_exc = e3
                        try:
                            code3 = getattr(e3, 'code', lambda: None)()
                            cname3 = str(getattr(code3, 'name', '') or 'UNKNOWN')
                            logger.info(f"{request_id} | gRPC alt call raised: {cname3}")
                        except Exception:
                            logger.info(f"{request_id} | gRPC alt call raised non-grpc exception")
                        final_code_name = str(code3.name) if getattr(code3, 'name', None) else 'ERROR'
                        if attempt < attempts - 1 and is_idempotent and code3 in retryable:
                            retries_made += 1
                            delay = min(max_ms, base_ms * (2 ** attempt)) / 1000.0
                            jitter_factor = 1.0 + (random.random() * jitter - (jitter / 2.0))
                            await asyncio.sleep(max(0.01, delay * jitter_factor))
                            continue
                        else:
                            break
            if last_exc is not None:
                code_name = 'UNKNOWN'
                code_obj = None
                try:
                    code_obj = getattr(last_exc, 'code', lambda: None)()
                    if code_obj and hasattr(code_obj, 'name'):
                        code_name = str(code_obj.name).upper()
                        logger.info(f"{request_id} | gRPC call failed with status: {code_name}")
                    else:
                        logger.warning(f"{request_id} | gRPC exception has no valid status code")
                except Exception as code_extract_err:
                    logger.warning(f"{request_id} | Failed to extract gRPC status code: {str(code_extract_err)}")

                status_map = {
                    'OK': 200,
                    'CANCELLED': 499,
                    'UNKNOWN': 500,
                    'INVALID_ARGUMENT': 400,
                    'DEADLINE_EXCEEDED': 504,
                    'NOT_FOUND': 404,
                    'ALREADY_EXISTS': 409,
                    'PERMISSION_DENIED': 403,
                    'RESOURCE_EXHAUSTED': 429,
                    'FAILED_PRECONDITION': 412,
                    'ABORTED': 409,
                    'OUT_OF_RANGE': 400,
                    'UNIMPLEMENTED': 501,
                    'INTERNAL': 500,
                    'UNAVAILABLE': 503,
                    'DATA_LOSS': 500,
                    'UNAUTHENTICATED': 401,
                }

                http_status = status_map.get(code_name, 500)

                details = 'gRPC call failed'
                try:
                    details_fn = getattr(last_exc, 'details', None)
                    if callable(details_fn):
                        extracted_details = details_fn()
                        if extracted_details:
                            details = str(extracted_details)
                    elif details_fn:
                        details = str(details_fn)
                except Exception:
                    details = f'gRPC error: {code_name}'

                logger.error(
                    f"{request_id} | gRPC call failed after {retries_made} retries. "
                    f"Status: {code_name}, HTTP: {http_status}, Details: {details[:100]}"
                )

                response_headers = {
                    'request_id': request_id,
                    'X-Retry-Count': str(retries_made),
                    'X-GRPC-Status': code_name,
                    'X-GRPC-Code': str(code_obj.value[0]) if code_obj and hasattr(code_obj, 'value') else 'unknown'
                }

                return ResponseModel(
                    status_code=http_status,
                    response_headers=response_headers,
                    error_code='GTW006',
                    error_message=str(details)[:255]
                ).dict()
            if not got_response and last_exc is None:
                try:
                    logger.error(f"{request_id} | gRPC loop ended with no response and no exception; returning 500 UNKNOWN")
                except Exception:
                    pass
                return ResponseModel(
                    status_code=500,
                    response_headers={'request_id': request_id, 'X-Retry-Count': str(retries_made), 'X-Retry-Final': 'UNKNOWN'},
                    error_code='GTW006',
                    error_message='gRPC call failed'
                ).dict()

            response_dict = {}
            if hasattr(response, '_items'):
                response_dict['items'] = list(response._items)
            else:
                for field in response.DESCRIPTOR.fields:
                    value = getattr(response, field.name)
                    if hasattr(value, 'DESCRIPTOR'):
                        response_dict[field.name] = MessageToDict(value)
                    else:
                        response_dict[field.name] = value
            backend_end_time = time.time() * 1000
            response_headers = {'request_id': request_id, 'X-Retry-Count': str(retries_made), 'X-Retry-Final': final_code_name}
            try:
                if current_time and start_time:
                    response_headers['X-Gateway-Time'] = str(int(current_time - start_time))
                if backend_end_time and current_time:
                    response_headers['X-Backend-Time'] = str(int(backend_end_time - current_time))
            except Exception:
                pass
            try:
                logger.info(f"{request_id} | gRPC return 200 with items={bool(response_dict.get('items'))}")
            except Exception:
                pass
            return ResponseModel(
                status_code=200,
                response_headers=response_headers,
                response=response_dict
            ).dict()
        except httpx.TimeoutException:
            return ResponseModel(
                status_code=504,
                response_headers={'request_id': request_id},
                error_code='GTW010',
                error_message='Gateway timeout'
            ).dict()
        except Exception as e:
            code_name = 'UNKNOWN'
            code_obj = None
            try:
                code_obj = getattr(e, 'code', lambda: None)()
                if code_obj and hasattr(code_obj, 'name'):
                    code_name = str(code_obj.name).upper()
            except Exception:
                code_name = type(e).__name__.upper()

            status_map = {
                'OK': 200,
                'CANCELLED': 499,
                'UNKNOWN': 500,
                'INVALID_ARGUMENT': 400,
                'DEADLINE_EXCEEDED': 504,
                'NOT_FOUND': 404,
                'ALREADY_EXISTS': 409,
                'PERMISSION_DENIED': 403,
                'RESOURCE_EXHAUSTED': 429,
                'FAILED_PRECONDITION': 412,
                'ABORTED': 409,
                'OUT_OF_RANGE': 400,
                'UNIMPLEMENTED': 501,
                'INTERNAL': 500,
                'UNAVAILABLE': 503,
                'DATA_LOSS': 500,
                'UNAUTHENTICATED': 401,
            }

            http_status = status_map.get(code_name, 500)

            details = str(e)
            try:
                details_fn = getattr(e, 'details', None)
                if callable(details_fn):
                    extracted = details_fn()
                    if extracted:
                        details = str(extracted)
            except Exception:
                pass

            logger.error(
                f'{request_id} | gRPC gateway exception in outer handler. '
                f'Type: {type(e).__name__}, Status: {code_name}, HTTP: {http_status}, Error: {str(e)[:200]}'
            )

            return ResponseModel(
                status_code=http_status,
                response_headers={
                    'request_id': request_id,
                    'X-Error-Type': type(e).__name__,
                    'X-GRPC-Status': code_name
                },
                error_code='GTW006',
                error_message=details[:255]
            ).dict()
        finally:
            if current_time:
                logger.info(f'{request_id} | Gateway time {current_time - start_time}ms')
            if backend_end_time and current_time:
                logger.info(f'{request_id} | Backend time {backend_end_time - current_time}ms')

    async def _make_graphql_request(self, url: str, query: str, headers: Dict[str, str] = None) -> Dict:
        try:
            if headers is None:
                headers = {}
            headers.setdefault('Content-Type', 'application/json')
            client = GatewayService.get_http_client()
            r = await client.post(url, json={'query': query}, headers=headers)
            data = r.json()
            if 'errors' in data:
                return data
            if r.status_code != 200:
                return {'errors': [{'message': f'HTTP {r.status_code}: {data.get("message", "Unknown error")}', 'extensions': {'code': 'HTTP_ERROR'}}]}
            return data
        except Exception as e:
            logger.error(f'Error making GraphQL request: {str(e)}')
            return {
                'errors': [{
                    'message': f'Error making GraphQL request: {str(e)}',
                    'extensions': {'code': 'REQUEST_ERROR'}
                }]
            }
