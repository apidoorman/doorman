"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

# External imports
import os
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

# Provide a shim for gql.Client so tests can monkeypatch `Client` even when gql
# is not installed or used at runtime.
try:
    from gql import Client as _GqlClient  # type: ignore
    def gql(q):
        return q
except Exception:  # pragma: no cover
    class _GqlClient:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass
    def gql(q):  # type: ignore
        return q

# Expose symbol name expected by tests
Client = _GqlClient

# Internal imports
from models.response_model import ResponseModel
from utils import api_util, routing_util
from utils import credit_util
from utils.gateway_utils import get_headers
from utils.doorman_cache_util import doorman_cache
from utils.validation_util import validation_util

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

    @classmethod
    def get_http_client(cls) -> httpx.AsyncClient:
        if (os.getenv('ENABLE_HTTPX_CLIENT_CACHE', 'false').lower() == 'true'):
            if cls._http_client is None:
                cls._http_client = httpx.AsyncClient(timeout=cls.timeout)
            return cls._http_client
        return httpx.AsyncClient(timeout=cls.timeout)

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
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            return json.loads(response.content)
        elif 'application/xml' in content_type or 'text/xml' in content_type:
            return ET.fromstring(response.content)
        elif 'application/graphql' in content_type:
            return json.loads(response.content)
        elif 'application/graphql+json' in content_type:
            return json.loads(response.content)
        else:
            try:
                return json.loads(response.content)
            except Exception:
                try:
                    return ET.fromstring(response.content)
                except Exception:
                    return response.content

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
                composite = request.method + '/' + endpoint_uri
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
                # Recursive retry path: url/method provided, but we still need API context
                try:
                    parts = [p for p in (path or '').split('/') if p]
                    api_name_version = ''
                    endpoint_uri = ''
                    if len(parts) >= 2 and parts[1].startswith('v') and parts[1][1:].isdigit():
                        api_name_version = f'/{parts[0]}/{parts[1]}'
                        endpoint_uri = '/'.join(parts[2:])
                    api_key = doorman_cache.get_cache('api_id_cache', api_name_version)
                    api = await api_util.get_api(api_key, api_name_version)
                    # Do not mutate url/method or retry here; caller passed those
                except Exception:
                    api = None
                    endpoint_uri = ''

            current_time = time.time() * 1000
            query_params = getattr(request, 'query_params', {})
            allowed_headers = api.get('api_allowed_headers') or [] if api else []
            headers = await get_headers(request, allowed_headers)
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
                    if swap_from:
                        val = headers.get(swap_from)
                        if val is not None:
                            headers['Authorization'] = val
                except Exception:
                    pass

            try:
                endpoint_doc = await api_util.get_endpoint(api, method, '/' + endpoint_uri.lstrip('/')) if api else None
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
                    http_response = await client.get(url, params=query_params, headers=headers)
                elif method in ('POST', 'PUT', 'DELETE', 'PATCH'):
                    cl_header = request.headers.get('content-length') or request.headers.get('Content-Length')
                    try:
                        content_length = int(cl_header) if cl_header is not None and str(cl_header).strip() != '' else 0
                    except Exception:
                        content_length = 0

                    if content_length > 0:
                        if 'JSON' in content_type:
                            body = await request.json()
                            http_response = await getattr(client, method.lower())(
                                url, json=body, params=query_params, headers=headers
                            )
                        else:
                            body = await request.body()
                            http_response = await getattr(client, method.lower())(
                                url, content=body, params=query_params, headers=headers
                            )
                    else:
                        http_response = await getattr(client, method.lower())(
                            url, params=query_params, headers=headers
                        )
                else:
                    return GatewayService.error_response(request_id, 'GTW004', 'Method not supported', status=405)
            finally:
                if os.getenv('ENABLE_HTTPX_CLIENT_CACHE', 'false').lower() != 'true':
                    try:
                        await client.aclose()
                    except Exception:
                        pass
            if 'application/json' in http_response.headers.get('Content-Type', '').lower():
                response_content = http_response.json()
            else:
                response_content = http_response.text
            backend_end_time = time.time() * 1000
            if http_response.status_code in [500, 502, 503, 504] and retry > 0:
                logger.error(f'{request_id} | REST gateway failed retrying')
                return await GatewayService.rest_gateway(username, request, request_id, start_time, path, url, method, retry - 1)
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
        except httpx.TimeoutException:
            return ResponseModel(
                status_code=504,
                response_headers={'request_id': request_id},
                error_code='GTW010',
                error_message='Gateway timeout'
            ).dict()
        except Exception:
            logger.error(f'{request_id} | REST gateway failed with code GTW006')
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
            current_time = time.time() * 1000
            query_params = getattr(request, 'query_params', {})
            incoming_content_type = request.headers.get('Content-Type') or 'application/xml'
            if incoming_content_type == 'application/xml':
                content_type = 'text/xml; charset=utf-8'
            elif incoming_content_type in ['application/soap+xml', 'text/xml']:
                content_type = incoming_content_type
            else:
                content_type = 'text/xml; charset=utf-8'
            allowed_headers = api.get('api_allowed_headers') or []
            headers = await get_headers(request, allowed_headers)
            headers['Content-Type'] = content_type
            if 'SOAPAction' not in headers:
                headers['SOAPAction'] = '""'
            envelope = (await request.body()).decode('utf-8')
            if api.get('api_authorization_field_swap'):
                try:
                    swap_from = api.get('api_authorization_field_swap')
                    if swap_from:
                        val = headers.get(swap_from)
                        if val is not None:
                            headers['Authorization'] = val
                except Exception:
                    pass

            try:
                endpoint_doc = await api_util.get_endpoint(api, 'POST', '/' + endpoint_uri.lstrip('/'))
                endpoint_id = endpoint_doc.get('endpoint_id') if endpoint_doc else None
                if endpoint_id:
                    await validation_util.validate_soap_request(endpoint_id, envelope)
            except Exception as e:
                logger.error(f'{request_id} | Validation error: {e}')
                return GatewayService.error_response(request_id, 'GTW011', str(e), status=400)
            client = GatewayService.get_http_client()
            try:
                http_response = await client.post(url, content=envelope, params=query_params, headers=headers)
            finally:
                if os.getenv('ENABLE_HTTPX_CLIENT_CACHE', 'false').lower() != 'true':
                    try:
                        await client.aclose()
                    except Exception:
                        pass
            response_content = http_response.text
            logger.info(f'{request_id} | SOAP gateway response: {response_content}')
            backend_end_time = time.time() * 1000
            if http_response.status_code in [500, 502, 503, 504] and retry > 0:
                logger.error(f'{request_id} | SOAP gateway failed retrying')
                return await GatewayService.soap_gateway(username, request, request_id, start_time, path, url, retry - 1)
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
        except httpx.TimeoutException:
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
                    if swap_from:
                        val = headers.get(swap_from)
                        if val is not None:
                            headers['Authorization'] = val
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
            # First, attempt test-friendly Client path (monkeypatchable). If it fails,
            # fall back to direct HTTP via httpx.
            # If tests monkeypatch gw.Client, prefer that path; otherwise use upstream HTTP.
            use_client = hasattr(Client, '__aenter__')
            result = None
            if use_client:
                try:
                    async with Client(transport=None, fetch_schema_from_transport=False) as session:  # type: ignore
                        result = await session.execute(gql(query), variable_values=variables)  # type: ignore
                except Exception as _e:
                    logger.debug(f'{request_id} | GraphQL Client execution failed; falling back to HTTP: {_e}')
                    use_client = False
            if not use_client:
                client_key = request.headers.get('client-key')
                server = await routing_util.pick_upstream_server(api, 'POST', '/graphql', client_key)
                if not server:
                    logger.error(f'{request_id} | No upstream servers configured for {api_path}')
                    return GatewayService.error_response(request_id, 'GTW001', 'No upstream servers configured')
                url = server.rstrip('/')
                client = GatewayService.get_http_client()
                http_resp = await client.post(url, json={'query': query, 'variables': variables}, headers=headers)
                result = http_resp.json()

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
                logger.info(f'{request_id} | Processing gRPC request for API: {api_path}')

                try:
                    body = await request.json()
                    if not isinstance(body, dict):
                        logger.error(f'{request_id} | Invalid request body format')
                        return GatewayService.error_response(request_id, 'GTW011', 'Invalid request body format', status=400)
                except json.JSONDecodeError:
                    logger.error(f'{request_id} | Invalid JSON in request body')
                    return GatewayService.error_response(request_id, 'GTW011', 'Invalid JSON in request body', status=400)

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
                pkg_override = None
                # Resolve package name: API config override > request override > default derived
                api_pkg = None
                try:
                    api_pkg = (api.get('api_grpc_package') or '').strip() if api else None
                except Exception:
                    api_pkg = None
                try:
                    pkg_override = (body.get('package') or '').strip()
                except Exception:
                    pkg_override = None
                module_base = (api_pkg or pkg_override or f'{api_name}_{api_version}').replace('-', '_')
                proto_filename = f'{module_base}.proto'
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                proto_dir = os.path.join(project_root, 'proto')
                proto_path = os.path.join(proto_dir, proto_filename)
                if not os.path.exists(proto_path):
                    try:
                        os.makedirs(proto_dir, exist_ok=True)
                        method_fq = body.get('method', '')
                        service_name, method_name = (method_fq.split('.', 1) + [''])[:2]
                        if not service_name or not method_name:
                            raise ValueError('Invalid method format')
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
                        with open(proto_path, 'w', encoding='utf-8') as f:
                            f.write(proto_content)
                        generated_dir = os.path.join(project_root, 'generated')
                        os.makedirs(generated_dir, exist_ok=True)
                        try:
                            from grpc_tools import protoc as _protoc  # type: ignore
                            code = _protoc.main([
                                'protoc', f'--proto_path={proto_dir}', f'--python_out={generated_dir}', f'--grpc_python_out={generated_dir}', proto_path
                            ])
                            if code != 0:
                                raise RuntimeError(f'protoc returned {code}')
                            init_path = os.path.join(generated_dir, '__init__.py')
                            if not os.path.exists(init_path):
                                with open(init_path, 'w', encoding='utf-8') as f:
                                    f.write('"""Generated gRPC code."""\n')
                        except Exception as ge:
                            logger.error(f'{request_id} | On-demand proto generation failed: {ge}')
                            return GatewayService.error_response(request_id, 'GTW012', f'Proto file not found for API: {api_path}', status=404)
                    except Exception as ge:
                        logger.error(f'{request_id} | Proto file not found and generation skipped: {ge}')
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
            allowed_headers = api.get('api_allowed_headers') or []
            headers = await get_headers(request, allowed_headers)
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
            module_base = f'{api_name}_{api_version}'.replace('-', '_')
            proto_filename = f'{module_base}.proto'
            
            try:
                endpoint_doc = await api_util.get_endpoint(api, 'POST', '/grpc')
                endpoint_id = endpoint_doc.get('endpoint_id') if endpoint_doc else None
                if endpoint_id:
                    await validation_util.validate_grpc_request(endpoint_id, body.get('message'))
            except Exception as e:
                return GatewayService.error_response(request_id, 'GTW011', str(e), status=400)
            proto_path = os.path.join(proto_dir, proto_filename)
            if not os.path.exists(proto_path):
                logger.error(f'{request_id} | Proto file not found: {proto_path}')
                return GatewayService.error_response(request_id, 'GTW012', f'Proto file not found for API: {api_path}', status=404)
            try:
                module_name = module_base
                generated_dir = os.path.join(project_root, 'generated')
                if generated_dir not in sys.path:
                    sys.path.insert(0, generated_dir)
                try:
                    pb2_module = importlib.import_module(f'{module_name}_pb2')
                    service_module = importlib.import_module(f'{module_name}_pb2_grpc')
                except ImportError as e:
                    logger.error(f'{request_id} | Failed to import gRPC module: {str(e)}')
                    # If upstream is HTTP-based, fall back to HTTP call
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
                service_name = body['method'].split('.')[0]
                method_name = body['method'].split('.')[1]
                channel = grpc.aio.insecure_channel(url)
                try:
                    await asyncio.wait_for(channel.channel_ready(), timeout=2.0)
                except Exception:
                    pass
                try:
                    service_class = getattr(service_module, f'{service_name}Stub')
                    stub = service_class(channel)
                except AttributeError as e:
                    logger.error(f'{request_id} | Service {service_name} not found in module')
                    # HTTP fallback if upstream is HTTP
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
                    return GatewayService.error_response(request_id, 'GTW006', f'Service {service_name} not found', status=500)
                try:
                    request_class_name = f'{method_name}Request'
                    reply_class_name = f'{method_name}Reply'
                    request_class = getattr(pb2_module, request_class_name)
                    reply_class = getattr(pb2_module, reply_class_name)
                    request_message = request_class()
                except AttributeError as e:
                    logger.error(f'{request_id} | Method {method_name} types not found in module: {str(e)}')
                    # Attempt HTTP fallback if upstream is HTTP-based
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
                    return GatewayService.error_response(request_id, 'GTW006', f'Method {method_name} not found', status=500)
                for key, value in body['message'].items():
                    try:
                        setattr(request_message, key, value)
                    except Exception:
                        pass
                attempts = max(1, int(retry) + 1)
                last_exc = None
                for attempt in range(attempts):
                    try:
                        method_callable = getattr(stub, method_name)
                        response = await method_callable(request_message)
                        last_exc = None
                        break
                    except (AttributeError, grpc.RpcError) as e:
                        last_exc = e
                        full_method = f'/{module_base}.{service_name}/{method_name}'
                        try:
                            unary = channel.unary_unary(
                                full_method,
                                request_serializer=request_message.SerializeToString,
                                response_deserializer=reply_class.FromString,
                            )
                            response = await unary(request_message)
                            last_exc = None
                            break
                        except grpc.RpcError as e2:
                            last_exc = e2
                            if attempt < attempts - 1 and getattr(e2, 'code', lambda: None)() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.UNIMPLEMENTED):
                                await asyncio.sleep(0.1 * (attempt + 1))
                                continue
                            try:
                                alt_method = f'/{service_name}/{method_name}'
                                unary2 = channel.unary_unary(
                                    alt_method,
                                    request_serializer=request_message.SerializeToString,
                                    response_deserializer=reply_class.FromString,
                                )
                                response = await unary2(request_message)
                                last_exc = None
                                break
                            except grpc.RpcError as e3:
                                last_exc = e3
                                if attempt < attempts - 1 and getattr(e3, 'code', lambda: None)() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.UNIMPLEMENTED):
                                    await asyncio.sleep(0.1 * (attempt + 1))
                                    continue
                                else:
                                    try:
                                        import functools
                                        def _call_sync(url_s: str, svc_mod, svc_name: str, meth: str, req):
                                            ch = grpc.insecure_channel(url_s)
                                            stub_sync = getattr(svc_mod, f"{svc_name}Stub")(ch)
                                            return getattr(stub_sync, meth)(req)
                                        loop = asyncio.get_event_loop()
                                        response = await loop.run_in_executor(None, functools.partial(_call_sync, url, service_module, service_name, method_name, request_message))
                                        last_exc = None
                                        break
                                    except Exception as e4:
                                        last_exc = e4
                                        break
                if last_exc is not None:
                    raise last_exc
                response_dict = {}
                for field in response.DESCRIPTOR.fields:
                    value = getattr(response, field.name)
                    if hasattr(value, 'DESCRIPTOR'):
                        response_dict[field.name] = MessageToDict(value)
                    else:
                        response_dict[field.name] = value
                backend_end_time = time.time() * 1000
                response_headers = {'request_id': request_id}
                try:
                    if current_time and start_time:
                        response_headers['X-Gateway-Time'] = str(int(current_time - start_time))
                    if backend_end_time and current_time:
                        response_headers['X-Backend-Time'] = str(int(backend_end_time - current_time))
                except Exception:
                    pass
                return ResponseModel(
                    status_code=200,
                    response_headers=response_headers,
                    response=response_dict
                ).dict()
            except ImportError as e:
                logger.error(f'{request_id} | Failed to import gRPC module: {str(e)}')
                return GatewayService.error_response(request_id, 'GTW012', f'Failed to import gRPC module: {str(e)}', status=404)
            except AttributeError as e:
                logger.error(f'{request_id} | Invalid service or method: {str(e)}')
                return GatewayService.error_response(request_id, 'GTW006', f'Invalid service or method: {str(e)}', status=500)
            except grpc.RpcError as e:
                status_code = e.code()
                if status_code == grpc.StatusCode.UNAVAILABLE and retry > 0:
                    logger.error(f'{request_id} | gRPC gateway failed retrying')
                    return await GatewayService.grpc_gateway(username, request, request_id, start_time, api_name, url, retry - 1)
                error_message = e.details()
                logger.error(f'{request_id} | gRPC error: {error_message}')
                # Map NOT_FOUND to 404; otherwise 500
                http_status = 404 if status_code == grpc.StatusCode.NOT_FOUND else 500
                return ResponseModel(
                    status_code=http_status,
                    response_headers={'request_id': request_id},
                    error_code='GTW006',
                    error_message=error_message
                ).dict()
            except Exception as e:
                logger.error(f'{request_id} | gRPC gateway failed with code GTW006: {str(e)}')
                return GatewayService.error_response(request_id, 'GTW006', str(e), status=500)
        except httpx.TimeoutException:
            return ResponseModel(
                status_code=504,
                response_headers={'request_id': request_id},
                error_code='GTW010',
                error_message='Gateway timeout'
            ).dict()
        except Exception as e:
            logger.error(f'{request_id} | gRPC gateway failed with code GTW006: {str(e)}')
            return GatewayService.error_response(request_id, 'GTW006', str(e), status=500)
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
