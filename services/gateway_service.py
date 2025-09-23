"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from models.response_model import ResponseModel
from utils import api_util, routing_util
from utils import token_util
from utils.pygate_cache_util import pygate_cache
from utils.token_util import deduct_ai_token

import logging
import re
import time
import httpx

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

class GatewayService:

    @staticmethod
    async def rest_gateway(Authorize, request, request_id, start_time, url=None, method=None, retry=0):
        """
        External gateway.
        """
        response = None
        logger.info(f"{request_id} | REST gateway trying resource: {request.path}")
        current_time = backend_end_time = None
        def error_response(code, message, status=404):
            logger.error(f"{request_id} | REST gateway failed with code {code}")
            return ResponseModel(
                status_code=status,
                response_headers={"request_id": request_id},
                error_code=code,
                error_message=message
            ).dict()
        try:
            if not url and not method:
                match = re.match(r"([^/]+/v\d+)", request.path)
                api_name_version = '/' + match.group(1) if match else ""
                endpoint_uri = re.sub(r"^[^/]+/v\d+/", "", request.path)
                api_key = pygate_cache.get_cache('api_id_cache', api_name_version)
                api = await api_util.get_api(api_key, api_name_version)
                if not api:
                    return error_response('GTW001', 'API does not exist for the requested name and version')
                endpoints = await api_util.get_api_endpoints(api.get('api_id'))
                if not endpoints:
                    return error_response('GTW002', 'No endpoints found for the requested API')
                regex_pattern = re.compile(r"\{[^/]+\}")
                composite = request.method + '/' + endpoint_uri
                if not any(re.fullmatch(regex_pattern.sub(r"([^/]+)", ep), composite) for ep in endpoints):
                    return error_response('GTW003', 'Endpoint does not exist for the requested API')
                client_key = request.headers.get('client-key')
                if client_key:
                    server = await routing_util.get_routing_info(client_key)
                    if not server:
                        return error_response('GTW007', 'Client key does not exist in routing')
                    logger.info(f"{request_id} | REST gateway to: {server}")
                else:
                    server_index = pygate_cache.get_cache('endpoint_server_cache', api.get('api_id')) or 0
                    api_servers = api.get('api_servers') or []
                    server = api_servers[server_index]
                    pygate_cache.set_cache('endpoint_server_cache', api.get('api_id'), (server_index + 1) % len(api_servers))
                    logger.info(f"{request_id} | REST gateway to: {server}")
                url = server + request.path
                method = request.method.upper()
                retry = api.get('api_allowed_retry_count') or 0
                if api.get('api_tokens_enabled'):
                    if not await token_util.deduct_ai_token(api, Authorize.get_jwt_subject()):
                        return error_response('GTW008', 'User does not have any tokens', status=401)
            current_time = time.time() * 1000
            query_params = getattr(request, 'query_params', {})
            allowed_headers = api.get('api_allowed_headers') or []
            headers = {key: value for key, value in request.headers.items() if key in allowed_headers}
            async with httpx.AsyncClient() as client:
                if method == 'GET':
                    response = await client.get(url, params=query_params, headers=headers)
                elif method == 'POST':
                    body = await request.json()
                    response = await client.post(url, json=body, params=query_params, headers=headers)
                elif method == 'PUT':
                    body = await request.json()
                    response = await client.put(url, json=body, params=query_params, headers=headers)
                elif method == 'DELETE':
                    response = await client.delete(url, params=query_params, headers=headers)
                else:
                    return error_response('GTW004', 'Method not supported', status=405)
            try:
                response_content = response.json()
            except Exception:
                response_content = response.text
            backend_end_time = time.time() * 1000
            if response.status_code in [500, 502, 503, 504] and retry > 0:
                logger.error(f"{request_id} | REST gateway failed retrying")
                return await GatewayService.rest_gateway(request, request_id, start_time, url, method, retry - 1)
            if response.status_code == 404:
                return error_response('GTW005', 'Endpoint does not exist in backend service')
            logger.info(f"{request_id} | REST gateway status code: {response.status_code}")
            response_headers = {"request_id": request_id}
            for key, value in response.headers.items():
                if key.lower() in allowed_headers:
                    response_headers[key] = value
            return ResponseModel(
                status_code=response.status_code,
                response_headers=response_headers,
                response=response_content
            ).dict()
        except Exception:
            logger.error(f"{request_id} | REST gateway failed with code GTW006")
            return error_response('GTW006', 'Internal server error', status=500)
        finally:
            if current_time:
                logger.info(f"{request_id} | Gateway time {current_time - start_time}ms")
            if backend_end_time and current_time:
                logger.info(f"{request_id} | Backend time {backend_end_time - current_time}ms")
