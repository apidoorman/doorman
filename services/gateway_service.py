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

from utils.database import db
from services.cache import pygate_cache

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
        start_time = time.time() * 1000
        gateway_end_time = None
        backend_start_time = None
        try:
            match = re.match(r"([^/]+/v\d+)", request.path)
            api_name_version = '/' + match.group(1) if match else ""
            endpoint_uri = re.sub(r"^[^/]+/v\d+/", "", request.path)
            api = pygate_cache.get_cache('api_cache', pygate_cache.get_cache('api_id_cache', api_name_version)) or GatewayService.api_collection.find_one({'api_path': api_name_version})   
            if not api:
                raise ValueError("API does not exists: " + api_name_version)
            endpoints = pygate_cache.get_cache('api_endpoint_cache', api.get('api_id')) or GatewayService.endpoint_collection.find({'api_id': api.get('api_id')})
            if not endpoints or not any(re.fullmatch(re.sub(r"\{[^/]+\}", r"([^/]+)", endpoint), request.method + '/' + endpoint_uri) for endpoint in endpoints):
                raise ValueError("Endpoint does not exists - " + str(endpoints) + "-" + request.method + '/' + endpoint_uri)
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
                return JSONResponse(content={"error": "Method not supported"}, status_code=405)
            try:
                response_content = response.json()
            except requests.exceptions.JSONDecodeError:
                response_content = response.text
            if response.status_code == 404:
                return JSONResponse("Endpoint does not exists in backend service", status_code=404)
            return JSONResponse(content=response_content, status_code=response.status_code)
        except Exception as e:
            GatewayService.logger.error(f"Error in rest_gateway: {str(e)}")
            return {"error": str(e)}
        finally:
            end_time = time.time() * 1000
            if gateway_end_time:
                GatewayService.logger.info(f"Gateway Time: {gateway_end_time - start_time}ms")
            if backend_start_time:
                GatewayService.logger.info(f"Backend Time: {end_time - backend_start_time}ms")
            GatewayService.logger.info(f"Total Time: {end_time - start_time}ms")