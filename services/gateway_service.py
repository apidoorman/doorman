"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

import re
import time
from fastapi.responses import JSONResponse
import requests
import logging

from models.response_model import ResponseModel
from utils.database import db
from services.cache import pygate_cache
import uuid

class GatewayService:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    logger = logging.getLogger("pygate.gateway")
    
    api_collection = db.apis
    endpoint_collection = db.endpoints

    @staticmethod
    async def rest_gateway(request):
        """
        External gateway.
        """
        request_id = uuid.uuid4()
        start_time = time.time() * 1000
        gateway_end_time = None
        backend_start_time = None
        response = None
        GatewayService.logger.info(f"REST | {request_id} | Resource: {request.path}")
        try:
            match = re.match(r"([^/]+/v\d+)", request.path)
            api_name_version = '/' + match.group(1) if match else ""
            endpoint_uri = re.sub(r"^[^/]+/v\d+/", "", request.path)
            api = pygate_cache.get_cache('api_cache', pygate_cache.get_cache('api_id_cache', api_name_version))
            if not api:
                api = GatewayService.api_collection.find_one({'api_path': api_name_version})
                if not api:
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
                return ResponseModel(
                    status_code=404,
                    error_code='GTW003',
                    error_message='Endpoint does not exist for the requested API and URI'
                ).dict()
            server_index = pygate_cache.get_cache('endpoint_server_cache', api.get('api_id')) or 0
            api_servers = api.get('api_servers') or []
            server = api_servers[server_index]
            pygate_cache.set_cache('endpoint_server_cache', api.get('api_id'), (server_index + 1) % len(api.get('api_servers')))
            url = server + request.path
            gateway_end_time = time.time() * 1000
            backend_start_time = time.time() * 1000
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
                return ResponseModel(
                    status_code=404,
                    error_code='GTW005',
                    error_message='Endpoint does not exist in backend service'
                ).dict()
            return ResponseModel(
                status_code=response.status_code,
                response=response_content
            ).dict()
        except Exception as e:
            GatewayService.logger.error(f"REST | {request_id} | Error in rest_gateway: {str(e)}")
            GatewayService.logger.info(f'"error: {str(e)}')
            return ResponseModel(
                status_code=500,
                error_code='GTW006',
                error_message='Internal server error'
            ).dict()
        finally:
            end_time = time.time() * 1000
            response.headers['X-Request-Id'] = request_id
            if gateway_end_time:
                GatewayService.logger.info(f"REST | {request_id} | Gateway Time: {gateway_end_time - start_time}ms")
            if backend_start_time:
                GatewayService.logger.info(f"REST | {request_id} | Backend Time: {end_time - backend_start_time}ms")
            GatewayService.logger.info(f"REST | {request_id} | Total Time: {end_time - start_time}ms")
            GatewayService.logger.info(f"REST | {request_id} | Status Code: {response.status_code}")