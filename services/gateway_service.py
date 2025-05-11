"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

import os
from models.response_model import ResponseModel
from utils import api_util, routing_util
from utils import token_util
from utils.gateway_utils import get_headers
from utils.doorman_cache_util import doorman_cache
from utils.token_util import deduct_ai_token, get_token_api_heaeder

import json
import xml.etree.ElementTree as ET
import logging
import re
import time
import httpx

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("doorman.gateway")

class GatewayService:

    timeout = httpx.Timeout(
                connect=float(os.getenv("HTTP_CONNECT_TIMEOUT", 5.0)),
                read=float(os.getenv("HTTP_READ_TIMEOUT", 30.0)),
                write=float(os.getenv("HTTP_WRITE_TIMEOUT", 30.0)),
                pool=float(os.getenv("HTTP_TIMEOUT", 30.0))
            )

    def error_response(request_id, code, message, status=404):
            logger.error(f"{request_id} | REST gateway failed with code {code}")
            return ResponseModel(
                status_code=status,
                response_headers={"request_id": request_id},
                error_code=code,
                error_message=message
            ).dict()

    def parse_response(response):
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return json.loads(response.content)
        elif "application/xml" in content_type or "text/xml" in content_type:
            return ET.fromstring(response.content)
        else:
            try:
                return json.loads(response.content)
            except Exception:
                return ET.fromstring(response.content)

    @staticmethod
    async def rest_gateway(Authorize, request, request_id, start_time, url=None, method=None, retry=0):
        """
        External gateway.
        """
        logger.info(f"{request_id} | REST gateway trying resource: {request.path}")
        current_time = backend_end_time = None
        try:
            if not url and not method:
                match = re.match(r"([^/]+/v\d+)", request.path)
                api_name_version = '/' + match.group(1) if match else ""
                endpoint_uri = re.sub(r"^[^/]+/v\d+/", "", request.path)
                api_key = doorman_cache.get_cache('api_id_cache', api_name_version)
                api = await api_util.get_api(api_key, api_name_version)
                if not api:
                    return GatewayService.error_response(request_id, 'GTW001', 'API does not exist for the requested name and version')
                endpoints = await api_util.get_api_endpoints(api.get('api_id'))
                if not endpoints:
                    return GatewayService.error_response(request_id, 'GTW002', 'No endpoints found for the requested API')
                regex_pattern = re.compile(r"\{[^/]+\}")
                composite = request.method + '/' + endpoint_uri
                if not any(re.fullmatch(regex_pattern.sub(r"([^/]+)", ep), composite) for ep in endpoints):
                    logger.error(f"{endpoints} | REST gateway failed with code GTW003")
                    return GatewayService.error_response(request_id, 'GTW003', 'Endpoint does not exist for the requested API')
                client_key = request.headers.get('client-key')
                if client_key:
                    server = await routing_util.get_routing_info(client_key)
                    if not server:
                        return GatewayService.error_response(request_id, 'GTW007', 'Client key does not exist in routing')
                    logger.info(f"{request_id} | REST gateway to: {server}")
                else:
                    server_index = doorman_cache.get_cache('endpoint_server_cache', api.get('api_id')) or 0
                    api_servers = api.get('api_servers') or []
                    server = api_servers[server_index]
                    doorman_cache.set_cache('endpoint_server_cache', api.get('api_id'), (server_index + 1) % len(api_servers))
                    logger.info(f"{request_id} | REST gateway to: {server}")
                url = server.rstrip('/') + '/' + endpoint_uri.lstrip('/')
                method = request.method.upper()
                retry = api.get('api_allowed_retry_count') or 0
                if api.get('api_tokens_enabled'):
                    if not await token_util.deduct_ai_token(api.get('api_token_group'), Authorize.get_jwt_subject()):
                        return GatewayService.error_response(request_id, 'GTW008', 'User does not have any tokens', status=401)
            current_time = time.time() * 1000
            query_params = getattr(request, 'query_params', {})
            allowed_headers = api.get('api_allowed_headers') or []
            headers = await get_headers(request, allowed_headers)
            if api.get('api_tokens_enabled'):
                ai_token_headers = await token_util.get_token_api_header(api.get('api_token_group'))
                if ai_token_headers:
                    headers[ai_token_headers[0]] = ai_token_headers[1]
                user_specific_api_key = await token_util.get_user_api_key(api.get('api_token_group'), Authorize.get_jwt_subject())
                if user_specific_api_key:
                    headers[ai_token_headers[0]] = user_specific_api_key
            content_type = request.headers.get("Content-Type", "").upper()
            logger.info(f"{request_id} | REST gateway to: {url}")
            if api.get('api_authorization_field_swap'):
                headers[api.get('Authorization')] = headers.get(api.get('api_authorization_field_swap'))
            async with httpx.AsyncClient(timeout=GatewayService.timeout) as client:
                if method == "GET":
                    http_response = await client.get(url, params=query_params, headers=headers)
                elif method in ("POST", "PUT", "DELETE"):
                    if content_type in ["application/json", "text/json"]:
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
                    return GatewayService.error_response(request_id, 'GTW004', 'Method not supported', status=405)
            if "application/json" in http_response.headers.get("Content-Type", "").lower():
                response_content = http_response.json()
            else:
                response_content = http_response.text
            backend_end_time = time.time() * 1000
            if http_response.status_code in [500, 502, 503, 504] and retry > 0:
                logger.error(f"{request_id} | REST gateway failed retrying")
                return await GatewayService.rest_gateway(Authorize, request, request_id, start_time, url, method, retry - 1)
            if http_response.status_code == 404:
                return GatewayService.error_response(request_id, 'GTW005', 'Endpoint does not exist in backend service')
            logger.info(f"{request_id} | REST gateway status code: {http_response.status_code}")
            response_headers = {"request_id": request_id}
            for key, value in http_response.headers.items():
                if key.lower() in allowed_headers:
                    response_headers[key] = value
            return ResponseModel(
                status_code=http_response.status_code,
                response_headers=response_headers,
                response=response_content
            ).dict()
        except httpx.TimeoutException:
            return ResponseModel(
                status_code=504,
                response_headers={"request_id": request_id},
                error_code="GTW010",
                error_message="Gateway timeout"
            ).dict()
        except Exception:
            logger.error(f"{request_id} | REST gateway failed with code GTW006")
            return GatewayService.error_response(request_id, 'GTW006', 'Internal server error', status=500)
        finally:
            if current_time:
                logger.info(f"{request_id} | Gateway time {current_time - start_time}ms")
            if backend_end_time and current_time:
                logger.info(f"{request_id} | Backend time {backend_end_time - current_time}ms")


    @staticmethod
    async def soap_gateway(path, Authorize, request, request_id, start_time, url=None, retry=0):
        """
        External SOAP gateway.
        """
        logger.info(f"{request_id} | SOAP gateway trying resource: {path}")
        current_time = backend_end_time = None
        try:
            if not url:
                match = re.match(r"([^/]+/v\d+)", path)
                api_name_version = '/' + match.group(1) if match else ""
                endpoint_uri = re.sub(r"^[^/]+/v\d+/", "", path)
                api_key = doorman_cache.get_cache('api_id_cache', api_name_version)
                api = await api_util.get_api(api_key, api_name_version)
                if not api:
                    return GatewayService.error_response(request_id, 'GTW001', 'API does not exist for the requested name and version')
                endpoints = await api_util.get_api_endpoints(api.get('api_id'))
                logger.info(f"{request_id} | SOAP gateway endpoints: {endpoints}")
                if not endpoints:
                    return GatewayService.error_response(request_id, 'GTW002', 'No endpoints found for the requested API')
                regex_pattern = re.compile(r"\{[^/]+\}")
                composite = 'POST/' + endpoint_uri
                if not any(re.fullmatch(regex_pattern.sub(r"([^/]+)", ep), composite) for ep in endpoints):
                    return GatewayService.error_response(request_id, 'GTW003', 'Endpoint does not exist for the requested API')
                client_key = request.headers.get('client-key')
                if client_key:
                    server = await routing_util.get_routing_info(client_key)
                    if not server:
                        return GatewayService.error_response(request_id, 'GTW007', 'Client key does not exist in routing')
                    logger.info(f"{request_id} | SOAP gateway to: {server}")
                else:
                    server_index = doorman_cache.get_cache('endpoint_server_cache', api.get('api_id')) or 0
                    api_servers = api.get('api_servers') or []
                    server = api_servers[server_index]
                    doorman_cache.set_cache('endpoint_server_cache', api.get('api_id'), (server_index + 1) % len(api_servers))
                    logger.info(f"{request_id} | SOAP gateway to: {server}")
                url = server.rstrip('/') + '/' + endpoint_uri.lstrip('/')
                logger.info(f"{request_id} | SOAP gateway to: {url}")
                retry = api.get('api_allowed_retry_count') or 0
                if api.get('api_tokens_enabled'):
                    if not await token_util.deduct_ai_token(api, Authorize.get_jwt_subject()):
                        return GatewayService.error_response(request_id, 'GTW008', 'User does not have any tokens', status=401)
            current_time = time.time() * 1000
            query_params = getattr(request, 'query_params', {})
            incoming_content_type = request.headers.get("Content-Type", "").lower()
            if incoming_content_type == "application/xml":
                content_type = "text/xml; charset=utf-8"
            elif incoming_content_type in ["application/soap+xml", "text/xml"]:
                content_type = incoming_content_type
            else:
                content_type = "text/xml; charset=utf-8"
            allowed_headers = api.get('api_allowed_headers') or []
            headers = await get_headers(request, allowed_headers)
            headers["Content-Type"] = content_type
            if "SOAPAction" not in headers:
                headers["SOAPAction"] = '""'
            envelope = (await request.body()).decode("utf-8")
            if api.get('api_authorization_field_swap'):
                headers[api.get('Authorization')] = headers.get(api.get('api_authorization_field_swap'))
            async with httpx.AsyncClient(timeout=GatewayService.timeout) as client:
                http_response = await client.post(url, content=envelope, params=query_params, headers=headers)
            response_content = http_response.text
            logger.info(f"{request_id} | SOAP gateway response: {response_content}")
            backend_end_time = time.time() * 1000
            if http_response.status_code in [500, 502, 503, 504] and retry > 0:
                logger.error(f"{request_id} | SOAP gateway failed retrying")
                return await GatewayService.soap_gateway(path, Authorize, request, request_id, start_time, url, retry - 1)
            if http_response.status_code == 404:
                return GatewayService.error_response(request_id, 'GTW005', 'Endpoint does not exist in backend service')
            logger.info(f"{request_id} | SOAP gateway status code: {http_response.status_code}")
            response_headers = {"request_id": request_id}
            for key, value in http_response.headers.items():
                if key.lower() in allowed_headers:
                    response_headers[key] = value
            return ResponseModel(
                status_code=http_response.status_code,
                response_headers=response_headers,
                response=response_content
            ).dict()
        except httpx.TimeoutException:
            return ResponseModel(
                status_code=504,
                response_headers={"request_id": request_id},
                error_code="GTW010",
                error_message="Gateway timeout"
            ).dict()
        except Exception:
            logger.error(f"{request_id} | SOAP gateway failed with code GTW006")
            return GatewayService.error_response(request_id, 'GTW006', 'Internal server error', status=500)
        finally:
            if current_time:
                logger.info(f"{request_id} | Gateway time {current_time - start_time}ms")
            if backend_end_time and current_time:
                logger.info(f"{request_id} | Backend time {backend_end_time - current_time}ms")