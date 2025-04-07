"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

# Removed unused import: JSONResponse

from models.response_model import ResponseModel
from utils import routing_util
from utils.database import db
from services.cache import pygate_cache

import uuid
import requests
import logging
import re
import time

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

class GatewayService:
    
    api_collection = db.apis
    endpoint_collection = db.endpoints

    @staticmethod
    async def rest_gateway(request, request_id):
        """
        External gateway.
        """
        response = None
        logger.info(f"{request_id} | REST gateway trying resource: {request.path}")
        try:
            match = re.match(r"([^/]+/v\d+)", request.path)
            api_name_version = '/' + match.group(1) if match else ""
            endpoint_uri = re.sub(r"^[^/]+/v\d+/", "", request.path)
            api = pygate_cache.get_cache('api_cache', pygate_cache.get_cache('api_id_cache', api_name_version))
            if not api:
                api = GatewayService.api_collection.find_one({'api_path': api_name_version})
                if not api:
                    logger.error(f"{request_id} | REST gateway failed with code GTW001")
                    return ResponseModel(
                        status_code=404,
                        error_code='GTW001',
                        error_message='API does not exist for the requested name and version'
                    ).dict()
                if api.get('_id'): del api['_id']
                pygate_cache.set_cache('api_cache', pygate_cache.get_cache('api_id_cache', api_name_version), api)
            endpoints = pygate_cache.get_cache('api_endpoint_cache', api.get('api_id'))
            if not endpoints:
                endpoints = GatewayService.endpoint_collection.find({'api_id': api.get('api_id')})
                if not endpoints:
                    logger.error(f"{request_id} | REST gateway failed with code GTW002")
                    return ResponseModel(
                        status_code=404,
                        error_code='GTW002',
                        error_message='No endpoints found for the requested API'
                    ).dict()
                api_endpoints = []
                for endpoint in endpoints:
                    if endpoint.get('_id'): del endpoint['_id']
                    api_endpoints.append(endpoint.get('endpoint_method') + endpoint.get('endpoint_uri'))
                pygate_cache.set_cache('api_endpoint_cache', api.get('api_id'), api_endpoints)
                endpoints = api_endpoints
            if not endpoints or not any(re.fullmatch(re.sub(r"\{[^/]+\}", r"([^/]+)", endpoint), request.method + '/' + endpoint_uri) for endpoint in endpoints):
                logger.error(f"{request_id} | REST gateway failed with code GTW003")
                return ResponseModel(
                    status_code=404,
                    error_code='GTW003',
                    error_message='Endpoint does not exist for the requested API and URI'
                ).dict()
            client_key = request.headers.get('client-key')
            if client_key:
                routing = await routing_util.get_client_routing(client_key)
                if not routing:
                    logger.error(f"{request_id} | REST gateway failed with code GTW007")
                    return ResponseModel(
                        status_code=401,
                        error_code='GTW007',
                        error_message='Client key is invalid'
                    ).dict()
                server_index = routing.get('server_index') or 0
                api_servers = routing.get('routing_servers') or []
                server = api_servers[server_index]
                server_index = (server_index + 1) % len(api_servers)
                routing['server_index'] = server_index
                pygate_cache.set_cache('client_routing_cache', client_key, routing)
                logger.info(f"{request_id} | REST gateway to: {server}")
            else:
                server_index = pygate_cache.get_cache('endpoint_server_cache', api.get('api_id')) or 0
                api_servers = api.get('api_servers') or []
                server = api_servers[server_index]
                pygate_cache.set_cache('endpoint_server_cache', api.get('api_id'), (server_index + 1) % len(api.get('api_servers')))
                logger.info(f"{request_id} | REST gateway to: {server}")
            url = server + request.path
            method = request.method.upper()
            if method == 'GET':
                response = requests.get(url)
            elif method == 'POST':
                body = await request.json()
                response = requests.post(url, json=body)
            elif method == 'PUT':
                body = await request.json()
                response = requests.put(url, json=body)
            elif method == 'DELETE':
                response = requests.delete(url)
            else:
                logger.error(f"{request_id} | REST gateway failed with code GTW004")
                return ResponseModel(
                    status_code=405,
                    error_code='GTW004',
                    error_message='Method not supported'
                ).dict()
            try:
                response_content = response.json()
            except requests.exceptions.JSONDecodeError:
                response_content = response.text
            if response.status_code == 404:
                logger.error(f"{request_id} | REST gateway failed with code GTW005")
                return ResponseModel(
                    status_code=404,
                    error_code='GTW005',
                    error_message='Endpoint does not exist in backend service'
                ).dict()
            logger.info(f"{request_id} | REST gateway response successfully recieved")
            return ResponseModel(
                status_code=response.status_code,
                response=response_content
            ).dict()
        except Exception:
            logger.error(f"{request_id} | REST gateway failed with code GTW006")
            return ResponseModel(
                status_code=500,
                error_code='GTW006',
                error_message='Internal server error'
            ).dict()
        finally:
            if response:
                response.headers['X-Request-Id'] = request_id