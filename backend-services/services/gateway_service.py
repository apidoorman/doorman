"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

import os
import json
import sys
import xml.etree.ElementTree as ET
import logging
import re
import time
import httpx
import aiohttp
from typing import Dict
import grpc
from google.protobuf.json_format import MessageToDict
import importlib
from models.response_model import ResponseModel
from utils import api_util, routing_util
from utils import token_util
from utils.gateway_utils import get_headers
from utils.doorman_cache_util import doorman_cache
from utils.validation_util import validation_util
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

import logging
logging.getLogger('gql').setLevel(logging.WARNING)

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
        elif "application/graphql" in content_type:
            return json.loads(response.content)
        elif "application/graphql+json" in content_type:
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
        logger.info(f"{request_id} | REST gateway trying resource: {path}")
        current_time = backend_end_time = None
        try:
            if not url and not method:
                match = re.match(r"([^/]+/v\d+)", path)
                api_name_version = '/' + match.group(1) if match else ""
                endpoint_uri = re.sub(r"^[^/]+/v\d+/", "", path)
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
                    if not await token_util.deduct_ai_token(api.get('api_token_group'), username):
                        return GatewayService.error_response(request_id, 'GTW008', 'User does not have any tokens', status=401)
            current_time = time.time() * 1000
            query_params = getattr(request, 'query_params', {})
            allowed_headers = api.get('api_allowed_headers') or []
            headers = await get_headers(request, allowed_headers)
            if api.get('api_tokens_enabled'):
                ai_token_headers = await token_util.get_token_api_header(api.get('api_token_group'))
                if ai_token_headers:
                    headers[ai_token_headers[0]] = ai_token_headers[1]
                user_specific_api_key = await token_util.get_user_api_key(api.get('api_token_group'), username)
                if user_specific_api_key:
                    headers[ai_token_headers[0]] = user_specific_api_key
            content_type = request.headers.get("Content-Type", "").upper()
            logger.info(f"{request_id} | REST gateway to: {url}")
            if api.get('api_authorization_field_swap'):
                headers[api.get('Authorization')] = headers.get(api.get('api_authorization_field_swap'))
            if api.get('validation_enabled'):
                try:
                    if content_type in ["application/json", "text/json"]:
                        body = await request.json()
                        await validation_util.validate_rest_request(api.get('api_id'), body)
                    elif content_type in ["application/xml", "text/xml"]:
                        body = (await request.body()).decode("utf-8")
                        await validation_util.validate_soap_request(api.get('api_id'), body)
                except Exception as e:
                    return GatewayService.error_response(request_id, 'GTW011', str(e), status=400)
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
                return await GatewayService.rest_gateway(username, request, request_id, start_time, path, url, method, retry - 1)
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
    async def soap_gateway(username, request, request_id, start_time, path, url=None, retry=0):
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
                else:
                    server_index = doorman_cache.get_cache('endpoint_server_cache', api.get('api_id')) or 0
                    api_servers = api.get('api_servers') or []
                    server = api_servers[server_index]
                    doorman_cache.set_cache('endpoint_server_cache', api.get('api_id'), (server_index + 1) % len(api_servers))
                url = server.rstrip('/') + '/' + endpoint_uri.lstrip('/')
                logger.info(f"{request_id} | SOAP gateway to: {url}")
                retry = api.get('api_allowed_retry_count') or 0
                if api.get('api_tokens_enabled'):
                    if not await token_util.deduct_ai_token(api, username):
                        return GatewayService.error_response(request_id, 'GTW008', 'User does not have any tokens', status=401)
            current_time = time.time() * 1000
            query_params = getattr(request, 'query_params', {})
            incoming_content_type = request.headers.get("Content-Type") or "application/xml"
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
            if api.get('validation_enabled'):
                try:
                    await validation_util.validate_soap_request(api.get('api_id'), envelope)
                except Exception as e:
                    return GatewayService.error_response(request_id, 'GTW011', str(e), status=400)
            async with httpx.AsyncClient(timeout=GatewayService.timeout) as client:
                http_response = await client.post(url, content=envelope, params=query_params, headers=headers)
            response_content = http_response.text
            logger.info(f"{request_id} | SOAP gateway response: {response_content}")
            backend_end_time = time.time() * 1000
            if http_response.status_code in [500, 502, 503, 504] and retry > 0:
                logger.error(f"{request_id} | SOAP gateway failed retrying")
                return await GatewayService.soap_gateway(username, request, request_id, start_time, path, url, retry - 1)
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

    @staticmethod
    async def graphql_gateway(username, request, request_id, start_time, path, url=None, retry=0):
        logger.info(f"{request_id} | GraphQL gateway processing request")
        current_time = backend_end_time = None
        try:
            if not url:
                api_name = path.replace('/api/graphql/', '').replace('graphql/', '')
                api_version = request.headers.get('X-API-Version', 'v1')
                api_path = f"{api_name}/{api_version}".lstrip('/')
                api = doorman_cache.get_cache('api_cache', api_path)
                if not api:
                    api = await api_util.get_api(None, api_path)
                    if not api:
                        logger.error(f"{request_id} | API not found: {api_path}")
                        return GatewayService.error_response(request_id, 'GTW001', f'API does not exist: {api_path}')
                doorman_cache.set_cache('api_cache', api_path, api)
                if not api.get('api_servers'):
                    logger.error(f"{request_id} | No API servers configured for {api_path}")
                    return GatewayService.error_response(request_id, 'GTW001', 'No API servers configured')
                url = api.get('api_servers', [])[0].rstrip('/')
                retry = api.get('api_allowed_retry_count') or 0
                if api.get('api_tokens_enabled'):
                    if not await token_util.deduct_ai_token(api.get('api_token_group'), username):
                        return GatewayService.error_response(request_id, 'GTW008', 'User does not have any tokens', status=401)
            current_time = time.time() * 1000
            allowed_headers = api.get('api_allowed_headers') or []
            headers = await get_headers(request, allowed_headers)
            headers['Content-Type'] = 'application/json'
            headers['Accept'] = 'application/json'
            if api.get('api_tokens_enabled'):
                ai_token_headers = await token_util.get_token_api_header(api.get('api_token_group'))
                if ai_token_headers:
                    headers[ai_token_headers[0]] = ai_token_headers[1]
                user_specific_api_key = await token_util.get_user_api_key(api.get('api_token_group'), username)
                if user_specific_api_key:
                    headers[ai_token_headers[0]] = user_specific_api_key
            if api.get('api_authorization_field_swap'):
                headers[api.get('Authorization')] = headers.get(api.get('api_authorization_field_swap'))
            body = await request.json()
            query = body.get('query')
            variables = body.get('variables', {})
            if api.get('validation_enabled'):
                try:
                    await validation_util.validate_graphql_request(api.get('api_id'), query, variables)
                except Exception as e:
                    return GatewayService.error_response(request_id, 'GTW011', str(e), status=400)
            transport = AIOHTTPTransport(url=url, headers=headers)
            async with Client(transport=transport, fetch_schema_from_transport=True) as session:
                try:
                    result = await session.execute(gql(query), variable_values=variables)
                    backend_end_time = time.time() * 1000
                    if retry > 0:
                        logger.error(f"{request_id} | GraphQL gateway failed retrying")
                        return await GatewayService.graphql_gateway(username, request, request_id, start_time, path, url, retry - 1)
                    logger.info(f"{request_id} | GraphQL gateway status code: 200")
                    response_headers = {"request_id": request_id}
                    for key, value in headers.items():
                        if key.lower() in allowed_headers:
                            response_headers[key] = value
                    return ResponseModel(
                        status_code=200,
                        response_headers=response_headers,
                        response=result
                    ).dict()
                except Exception as e:
                    if retry > 0:
                        logger.error(f"{request_id} | GraphQL gateway failed retrying")
                        return await GatewayService.graphql_gateway(username, request, request_id, start_time, path, url, retry - 1)
                    error_msg = str(e)[:255] if len(str(e)) > 255 else str(e)
                    return GatewayService.error_response(request_id, 'GTW006', error_msg, status=500)
        except Exception as e:
            logger.error(f"{request_id} | GraphQL gateway failed with code GTW006: {str(e)}")
            error_msg = str(e)[:255] if len(str(e)) > 255 else str(e)
            return GatewayService.error_response(request_id, 'GTW006', error_msg, status=500)
        finally:
            if current_time:
                logger.info(f"{request_id} | Gateway time {current_time - start_time}ms")
            if backend_end_time and current_time:
                logger.info(f"{request_id} | Backend time {backend_end_time - current_time}ms")

    @staticmethod
    async def grpc_gateway(username, request, request_id, start_time, path, api_name=None, url=None, retry=0):
        logger.info(f"{request_id} | gRPC gateway processing request")
        current_time = backend_end_time = None
        try:
            if not url:
                if api_name is None:
                    path_parts = path.strip('/').split('/')
                    if len(path_parts) < 1:
                        logger.error(f"{request_id} | Invalid API path format: {path}")
                        return GatewayService.error_response(request_id, 'GTW001', 'Invalid API path format', status=404)
                    api_name = path_parts[-1]
                api_version = request.headers.get('X-API-Version', 'v1')
                api_path = f"{api_name}/{api_version}"
                logger.info(f"{request_id} | Processing gRPC request for API: {api_path}")
                logger.info(f"{request_id} | Processing gRPC request for API: {api_path}")
                proto_filename = f"{api_name}_{api_version}.proto"
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                proto_dir = os.path.join(project_root, 'proto')
                proto_path = os.path.join(proto_dir, proto_filename)
                if not os.path.exists(proto_path):
                    logger.error(f"{request_id} | Proto file not found: {proto_path}")
                    return GatewayService.error_response(request_id, 'GTW012', f'Proto file not found for API: {api_path}', status=404)
                api = doorman_cache.get_cache('api_cache', api_path)
                if not api:
                    api = await api_util.get_api(None, api_path)
                    if not api:
                        logger.error(f"{request_id} | API not found: {api_path}")
                        return GatewayService.error_response(request_id, 'GTW001', f'API does not exist: {api_path}', status=404)
                doorman_cache.set_cache('api_cache', api_path, api)
                if not api.get('api_servers'):
                    logger.error(f"{request_id} | No API servers configured for {api_path}")
                    return GatewayService.error_response(request_id, 'GTW001', 'No API servers configured', status=404)
                url = api.get('api_servers', [])[0].rstrip('/')
                if url.startswith('grpc://'):
                    url = url[7:]
                retry = api.get('api_allowed_retry_count') or 0
                if api.get('api_tokens_enabled'):
                    if not await token_util.deduct_ai_token(api.get('api_token_group'), username):
                        return GatewayService.error_response(request_id, 'GTW008', 'User does not have any tokens', status=401)
            current_time = time.time() * 1000
            allowed_headers = api.get('api_allowed_headers') or []
            headers = await get_headers(request, allowed_headers)
            try:
                body = await request.json()
                if not isinstance(body, dict):
                    logger.error(f"{request_id} | Invalid request body format")
                    return GatewayService.error_response(request_id, 'GTW011', 'Invalid request body format', status=400)
            except json.JSONDecodeError:
                logger.error(f"{request_id} | Invalid JSON in request body")
                return GatewayService.error_response(request_id, 'GTW011', 'Invalid JSON in request body', status=400)
            if 'method' not in body:
                logger.error(f"{request_id} | Missing method in request body")
                return GatewayService.error_response(request_id, 'GTW011', 'Missing method in request body', status=400)
            if 'message' not in body:
                logger.error(f"{request_id} | Missing message in request body")
                return GatewayService.error_response(request_id, 'GTW011', 'Missing message in request body', status=400)
            proto_filename = f"{api_name}_{api_version}.proto"
            proto_path = os.path.join(proto_dir, proto_filename)
            if not os.path.exists(proto_path):
                logger.error(f"{request_id} | Proto file not found: {proto_path}")
                return GatewayService.error_response(request_id, 'GTW012', f'Proto file not found for API: {api_path}', status=404)
            try:
                module_name = f"{api_name}_{api_version}".replace('-', '_')
                generated_dir = os.path.join(project_root, 'generated')
                if generated_dir not in sys.path:
                    sys.path.insert(0, generated_dir)
                try:
                    pb2_module = importlib.import_module(f"{module_name}_pb2")
                    service_module = importlib.import_module(f"{module_name}_pb2_grpc")
                except ImportError as e:
                    logger.error(f"{request_id} | Failed to import gRPC module: {str(e)}")
                    return GatewayService.error_response(request_id, 'GTW012', f'Failed to import gRPC module: {str(e)}', status=404)
                service_name = body['method'].split('.')[0]
                method_name = body['method'].split('.')[1]
                channel = grpc.aio.insecure_channel(url)
                try:
                    service_class = getattr(service_module, f"{service_name}Stub")
                    stub = service_class(channel)
                except AttributeError as e:
                    logger.error(f"{request_id} | Service {service_name} not found in module")
                    return GatewayService.error_response(request_id, 'GTW006', f'Service {service_name} not found', status=500)
                try:
                    request_class_name = f"{method_name}Request"
                    request_class = getattr(pb2_module, request_class_name)
                    request_message = request_class()
                except AttributeError as e:
                    logger.error(f"{request_id} | Method {method_name} not found in module: {str(e)}")
                    return GatewayService.error_response(request_id, 'GTW006', f'Method {method_name} not found', status=500)
                for key, value in body['message'].items():
                    setattr(request_message, key, value)
                method = getattr(stub, method_name)
                response = await method(request_message)
                response_dict = {}
                for field in response.DESCRIPTOR.fields:
                    value = getattr(response, field.name)
                    if hasattr(value, 'DESCRIPTOR'):
                        response_dict[field.name] = MessageToDict(value)
                    else:
                        response_dict[field.name] = value
                backend_end_time = time.time() * 1000
                return ResponseModel(
                    status_code=200,
                    response_headers={"request_id": request_id},
                    response=response_dict
                ).dict()
            except ImportError as e:
                logger.error(f"{request_id} | Failed to import gRPC module: {str(e)}")
                return GatewayService.error_response(request_id, 'GTW012', f'Failed to import gRPC module: {str(e)}', status=404)
            except AttributeError as e:
                logger.error(f"{request_id} | Invalid service or method: {str(e)}")
                return GatewayService.error_response(request_id, 'GTW006', f'Invalid service or method: {str(e)}', status=500)
            except grpc.RpcError as e:
                status_code = e.code()
                if status_code == grpc.StatusCode.UNAVAILABLE and retry > 0:
                    logger.error(f"{request_id} | gRPC gateway failed retrying")
                    return await GatewayService.grpc_gateway(username, request, request_id, start_time, api_name, url, retry - 1)
                error_message = e.details()
                logger.error(f"{request_id} | gRPC error: {error_message}")
                return ResponseModel(
                    status_code=500,
                    response_headers={"request_id": request_id},
                    error_code="GTW006",
                    error_message=error_message
                ).dict()
            except Exception as e:
                logger.error(f"{request_id} | gRPC gateway failed with code GTW006: {str(e)}")
                return GatewayService.error_response(request_id, 'GTW006', str(e), status=500)
        except httpx.TimeoutException:
            return ResponseModel(
                status_code=504,
                response_headers={"request_id": request_id},
                error_code="GTW010",
                error_message="Gateway timeout"
            ).dict()
        except Exception as e:
            logger.error(f"{request_id} | gRPC gateway failed with code GTW006: {str(e)}")
            return GatewayService.error_response(request_id, 'GTW006', str(e), status=500)
        finally:
            if current_time:
                logger.info(f"{request_id} | Gateway time {current_time - start_time}ms")
            if backend_end_time and current_time:
                logger.info(f"{request_id} | Backend time {backend_end_time - current_time}ms")

    async def _make_graphql_request(self, url: str, query: str, headers: Dict[str, str] = None) -> Dict:
        try:
            if headers is None:
                headers = {}
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/json'
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={'query': query}, headers=headers) as response:
                    response_data = await response.json()
                    if 'errors' in response_data:
                        return response_data
                    if response.status != 200:
                        return {
                            'errors': [{
                                'message': f'HTTP {response.status}: {response_data.get("message", "Unknown error")}',
                                'extensions': {'code': 'HTTP_ERROR'}
                            }]
                        }
                    return response_data
        except Exception as e:
            logger.error(f"Error making GraphQL request: {str(e)}")
            return {
                'errors': [{
                    'message': f'Error making GraphQL request: {str(e)}',
                    'extensions': {'code': 'REQUEST_ERROR'}
                }]
            }