"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import logging
import string as _string
import uuid
from pathlib import Path

from models.create_endpoint_model import CreateEndpointModel
from models.create_endpoint_validation_model import CreateEndpointValidationModel
from models.response_model import ResponseModel
from models.update_endpoint_model import UpdateEndpointModel
from models.update_endpoint_validation_model import UpdateEndpointValidationModel
from utils.database import api_collection, endpoint_collection, endpoint_validation_collection
from utils.doorman_cache_util import doorman_cache

logger = logging.getLogger('doorman.gateway')


class EndpointService:
    @staticmethod
    async def create_endpoint(data: CreateEndpointModel, request_id):
        """
        Create an endpoint for an API.
        """
        logger.info(
            request_id
            + ' | Creating endpoint: '
            + data.api_name
            + ' '
            + data.api_version
            + ' '
            + data.endpoint_uri
        )
        # Use client_uri for routing if provided, otherwise use endpoint_uri
        routing_uri = data.client_uri if data.client_uri else data.endpoint_uri
        cache_key = f'/{data.endpoint_method}/{data.api_name}/{data.api_version}/{routing_uri}'.replace(
            '//', '/'
        )
        if doorman_cache.get_cache('endpoint_cache', cache_key) or endpoint_collection.find_one(
            {
                'endpoint_method': data.endpoint_method,
                'api_name': data.api_name,
                'api_version': data.api_version,
                'endpoint_uri': data.endpoint_uri,
            }
        ):
            logger.error(request_id + ' | Endpoint creation failed with code END001')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='END001',
                error_message='Endpoint already exists for the requested API name, version and URI',
            ).dict()
        # Check if client_uri conflicts with another endpoint's client_uri or endpoint_uri
        if data.client_uri:
            conflict = endpoint_collection.find_one(
                {
                    'endpoint_method': data.endpoint_method,
                    'api_name': data.api_name,
                    'api_version': data.api_version,
                    '$or': [
                        {'client_uri': data.client_uri},
                        {'endpoint_uri': data.client_uri, 'client_uri': None}
                    ]
                }
            )
            if conflict:
                logger.error(request_id + ' | Endpoint creation failed - client_uri conflict')
                return ResponseModel(
                    status_code=400,
                    response_headers={'request_id': request_id},
                    error_code='END001',
                    error_message='Client URI conflicts with an existing endpoint',
                ).dict()
        # Resolve API ID from cache using canonical key "/{name}/{version}"
        data.api_id = doorman_cache.get_cache(
            'api_id_cache', f'/{data.api_name}/{data.api_version}'
        )
        if not data.api_id:
            api = api_collection.find_one(
                {'api_name': data.api_name, 'api_version': data.api_version}
            )
            if not api:
                logger.error(request_id + ' | Endpoint creation failed with code END002')
                return ResponseModel(
                    status_code=400,
                    error_code='END002',
                    error_message='API does not exist for the requested name and version',
                ).dict()
            data.api_id = api.get('api_id')
            # Ensure cache uses the same canonical key with leading slash
            doorman_cache.set_cache(
                'api_id_cache', f'/{data.api_name}/{data.api_version}', data.api_id
            )
        data.endpoint_id = str(uuid.uuid4())
        endpoint_dict = data.dict()
        insert_result = endpoint_collection.insert_one(endpoint_dict)
        if not insert_result.acknowledged:
            logger.error(request_id + ' | Endpoint creation failed with code END003')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='END003',
                error_message='Unable to insert endpoint',
            ).dict()
        endpoint_dict['_id'] = str(insert_result.inserted_id)
        doorman_cache.set_cache('endpoint_cache', cache_key, endpoint_dict)
        api_endpoints = doorman_cache.get_cache('api_endpoint_cache', data.api_id) or list()
        api_endpoints.append(
            endpoint_dict.get('endpoint_method') + endpoint_dict.get('endpoint_uri')
        )
        doorman_cache.set_cache('api_endpoint_cache', data.api_id, api_endpoints)
        logger.info(request_id + ' | Endpoint creation successful')
        try:
            if (
                data.endpoint_method.upper() == 'POST'
                and str(data.endpoint_uri).strip().lower() == '/grpc'
            ):
                from grpc_tools import protoc as _protoc

                api_name = data.api_name
                api_version = data.api_version
                module_base = f'{api_name}_{api_version}'.replace('-', '_')
                allowed = set(_string.ascii_letters + _string.digits + '_')
                module_base = ''.join(ch if ch in allowed else '_' for ch in module_base)
                if not module_base or (module_base[0] not in (_string.ascii_letters + '_')):
                    module_base = f'a_{module_base}' if module_base else 'default_proto'
                project_root = Path(__file__).resolve().parent.parent
                proto_dir = project_root / 'proto'
                generated_dir = project_root / 'generated'
                proto_dir.mkdir(exist_ok=True)
                generated_dir.mkdir(exist_ok=True)
                proto_path = (proto_dir / f'{module_base}.proto').resolve()
                # Validate path stays within proto directory
                proto_dir_resolved = proto_dir.resolve()
                if not str(proto_path).startswith(str(proto_dir_resolved)):
                    logger.error(f'{request_id} | Invalid proto path detected')
                    raise ValueError('Proto path must be within proto directory')
                # Additional validation before file operations
                if not str(proto_path).startswith(str(project_root.resolve())):
                    logger.error(f'{request_id} | Proto path outside project root')
                    raise ValueError('Proto path must be within project root')
                if not proto_path.exists():
                    proto_content = (
                        'syntax = "proto3";\n'
                        f'package {module_base};\n'
                        'service Resource {\n'
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
                code = _protoc.main(
                    [
                        'protoc',
                        f'--proto_path={str(proto_dir)}',
                        f'--python_out={str(generated_dir)}',
                        f'--grpc_python_out={str(generated_dir)}',
                        str(proto_path),
                    ]
                )
                if code != 0:
                    logger.warning(
                        f'{request_id} | Pre-gen gRPC stubs returned {code} for {module_base}'
                    )
                try:
                    init_path = (generated_dir / '__init__.py').resolve()
                    # Validate init path is within generated directory
                    if str(init_path).startswith(str(generated_dir.resolve())) and not init_path.exists():
                        init_path.write_text('"""Generated gRPC code."""\n', encoding='utf-8')
                except Exception:
                    pass
        except Exception as _e:
            logger.debug(f'{request_id} | Skipping pre-gen gRPC stubs: {_e}')
        return ResponseModel(
            status_code=201,
            response_headers={'request_id': request_id},
            message='Endpoint created successfully',
        ).dict()

    @staticmethod
    async def update_endpoint(
        endpoint_method, api_name, api_version, endpoint_uri, data: UpdateEndpointModel, request_id
    ):
        logger.info(
            request_id
            + ' | Updating endpoint: '
            + api_name
            + ' '
            + api_version
            + ' '
            + endpoint_uri
        )
        cache_key = f'/{endpoint_method}/{api_name}/{api_version}/{endpoint_uri}'.replace('//', '/')
        endpoint = doorman_cache.get_cache('endpoint_cache', cache_key)
        if not endpoint:
            endpoint = endpoint_collection.find_one(
                {
                    'api_name': api_name,
                    'api_version': api_version,
                    'endpoint_uri': endpoint_uri,
                    'endpoint_method': endpoint_method,
                }
            )
            logger.error(request_id + ' | Endpoint update failed with code END008')
            if not endpoint:
                return ResponseModel(
                    status_code=400,
                    error_code='END008',
                    error_message='Endpoint does not exist for the requested API name, version and URI',
                ).dict()
        else:
            doorman_cache.delete_cache('endpoint_cache', cache_key)
        if (
            (data.endpoint_method and data.endpoint_method != endpoint.get('endpoint_method'))
            or (data.api_name and data.api_name != endpoint.get('api_name'))
            or (data.api_version and data.api_version != endpoint.get('api_version'))
            or (data.endpoint_uri and data.endpoint_uri != endpoint.get('endpoint_uri'))
        ):
            logger.error(request_id + ' | Endpoint update failed with code END006')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='END006',
                error_message='API method, name, version and URI cannot be updated',
            ).dict()
        # Check if client_uri update conflicts with existing endpoints
        if data.client_uri and data.client_uri != endpoint.get('client_uri'):
            conflict = endpoint_collection.find_one(
                {
                    'endpoint_method': endpoint_method,
                    'api_name': api_name,
                    'api_version': api_version,
                    'endpoint_uri': {'$ne': endpoint_uri},  # Exclude current endpoint
                    '$or': [
                        {'client_uri': data.client_uri},
                        {'endpoint_uri': data.client_uri, 'client_uri': None}
                    ]
                }
            )
            if conflict:
                logger.error(request_id + ' | Endpoint update failed - client_uri conflict')
                return ResponseModel(
                    status_code=400,
                    response_headers={'request_id': request_id},
                    error_code='END006',
                    error_message='Client URI conflicts with an existing endpoint',
                ).dict()
        not_null_data = {k: v for k, v in data.dict().items() if v is not None}
        if not_null_data:
            update_result = endpoint_collection.update_one(
                {
                    'api_name': api_name,
                    'api_version': api_version,
                    'endpoint_uri': endpoint_uri,
                    'endpoint_method': endpoint_method,
                },
                {'$set': not_null_data},
            )
            if not update_result.acknowledged or update_result.modified_count == 0:
                logger.error(request_id + ' | Endpoint update failed with code END003')
                return ResponseModel(
                    status_code=400, error_code='END003', error_message='Unable to update endpoint'
                ).dict()
            logger.info(request_id + ' | Endpoint update successful')
            return ResponseModel(status_code=200, message='Endpoint updated successfully').dict()
        else:
            logger.error(request_id + ' | Endpoint update failed with code END007')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='END007',
                error_message='No data to update',
            ).dict()

    @staticmethod
    async def delete_endpoint(endpoint_method, api_name, api_version, endpoint_uri, request_id):
        """
        Delete an endpoint for an API.
        """
        logger.info(
            request_id + ' | Deleting: ' + api_name + ' ' + api_version + ' ' + endpoint_uri
        )
        cache_key = f'/{endpoint_method}/{api_name}/{api_version}/{endpoint_uri}'.replace('//', '/')
        endpoint = doorman_cache.get_cache('endpoint_cache', cache_key)
        if not endpoint:
            endpoint = endpoint_collection.find_one(
                {
                    'api_name': api_name,
                    'api_version': api_version,
                    'endpoint_uri': endpoint_uri,
                    'endpoint_method': endpoint_method,
                }
            )
            if not endpoint:
                logger.error(request_id + ' | Endpoint deletion failed with code END004')
                return ResponseModel(
                    status_code=400,
                    error_code='END004',
                    error_message='Endpoint does not exist for the requested API name, version and URI',
                ).dict()
        delete_result = endpoint_collection.delete_one(
            {
                'api_name': api_name,
                'api_version': api_version,
                'endpoint_uri': endpoint_uri,
                'endpoint_method': endpoint_method,
            }
        )
        if not delete_result.acknowledged:
            logger.error(request_id + ' | Endpoint deletion failed with code END009')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='END009',
                error_message='Unable to delete endpoint',
            ).dict()
        doorman_cache.delete_cache('endpoint_cache', cache_key)
        try:
            api_id = endpoint.get('api_id') if isinstance(endpoint, dict) else None
            if api_id:
                doorman_cache.delete_cache('api_endpoint_cache', api_id)
        except Exception:
            pass
        logger.info(request_id + ' | Endpoint deletion successful')
        return ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            message='Endpoint deleted successfully',
        ).dict()

    @staticmethod
    async def get_endpoint(endpoint_method, api_name, api_version, endpoint_uri, request_id):
        """
        Get an endpoint by API name, version and URI.
        """
        logger.info(request_id + ' | Getting: ' + api_name + ' ' + api_version + ' ' + endpoint_uri)
        endpoint = doorman_cache.get_cache(
            'endpoint_cache', f'{api_name}/{api_version}/{endpoint_uri}'
        )
        if not endpoint:
            endpoint = endpoint_collection.find_one(
                {
                    'api_name': api_name,
                    'api_version': api_version,
                    'endpoint_uri': endpoint_uri,
                    'endpoint_method': endpoint_method,
                }
            )
            if not endpoint:
                logger.error(request_id + ' | Endpoint retrieval failed with code END004')
                return ResponseModel(
                    status_code=400,
                    error_code='END004',
                    error_message='Endpoint does not exist for the requested API name, version and URI',
                ).dict()
            if endpoint.get('_id'):
                del endpoint['_id']
            doorman_cache.set_cache(
                'endpoint_cache', f'{api_name}/{api_version}/{endpoint_uri}', endpoint
            )
        if '_id' in endpoint:
            del endpoint['_id']
        logger.info(request_id + ' | Endpoint retrieval successful')
        return ResponseModel(status_code=200, response=endpoint).dict()

    @staticmethod
    async def get_endpoints_by_name_version(api_name, api_version, request_id):
        """
        Get all endpoints by API name and version.
        """
        logger.info(request_id + ' | Getting: ' + api_name + ' ' + api_version)
        cursor = endpoint_collection.find({'api_name': api_name, 'api_version': api_version})

        try:
            endpoints = list(cursor)
        except Exception:
            endpoints = await cursor.to_list(length=None)
        for endpoint in endpoints:
            if '_id' in endpoint:
                del endpoint['_id']
        if not endpoints:
            logger.error(request_id + ' | Endpoint retrieval failed with code END005')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='END005',
                error_message='No endpoints found for the requested API name and version',
            ).dict()
        logger.info(request_id + ' | Endpoint retrieval successful')
        return ResponseModel(status_code=200, response={'endpoints': endpoints}).dict()

    @staticmethod
    async def create_endpoint_validation(data: CreateEndpointValidationModel, request_id):
        """
        Create a new endpoint validation.
        """
        logger.info(request_id + ' | Creating endpoint validation: ' + data.endpoint_id)
        if not data.endpoint_id:
            logger.error(request_id + ' | Endpoint ID is required')
            return ResponseModel(
                status_code=400, error_code='END013', error_message='Endpoint ID is required'
            ).dict()
        if not data.validation_schema:
            logger.error(request_id + ' | Validation schema is required')
            return ResponseModel(
                status_code=400, error_code='END014', error_message='Validation schema is required'
            ).dict()
        if doorman_cache.get_cache('endpoint_validation_cache', data.endpoint_id):
            logger.error(request_id + ' | Endpoint validation already exists')
            return ResponseModel(
                status_code=400,
                error_code='END017',
                error_message='Endpoint validation already exists',
            ).dict()
        if not endpoint_collection.find_one({'endpoint_id': data.endpoint_id}):
            logger.error(request_id + ' | Endpoint does not exist')
            return ResponseModel(
                status_code=400, error_code='END015', error_message='Endpoint does not exist'
            ).dict()
        validation_dict = data.dict()
        insert_result = endpoint_validation_collection.insert_one(validation_dict)
        if not insert_result.acknowledged:
            logger.error(request_id + ' | Endpoint validation creation failed with code END016')
            return ResponseModel(
                status_code=400,
                error_code='END016',
                error_message='Unable to create endpoint validation',
            ).dict()
        logger.info(request_id + ' | Endpoint validation created successfully')
        doorman_cache.set_cache('endpoint_validation_cache', f'{data.endpoint_id}', validation_dict)
        return ResponseModel(
            status_code=201, message='Endpoint validation created successfully'
        ).dict()

    @staticmethod
    async def get_endpoint_validation(endpoint_id, request_id):
        """
        Get an endpoint validation by endpoint ID.
        """
        logger.info(request_id + ' | Getting endpoint validation: ' + endpoint_id)
        validation = doorman_cache.get_cache('endpoint_validation_cache', endpoint_id)
        if not validation:
            validation = endpoint_validation_collection.find_one({'endpoint_id': endpoint_id})
            if not validation:
                logger.error(
                    request_id + ' | Endpoint validation retrieval failed with code END018'
                )
                return ResponseModel(
                    status_code=400,
                    error_code='END018',
                    error_message='Endpoint validation does not exist',
                ).dict()
        logger.info(request_id + ' | Endpoint validation retrieval successful')
        return ResponseModel(status_code=200, response=validation).dict()

    @staticmethod
    async def delete_endpoint_validation(endpoint_id, request_id):
        """
        Delete an endpoint validation by endpoint ID.
        """
        logger.info(request_id + ' | Deleting endpoint validation: ' + endpoint_id)
        delete_result = endpoint_validation_collection.delete_one({'endpoint_id': endpoint_id})
        if not delete_result.acknowledged:
            logger.error(request_id + ' | Endpoint validation deletion failed with code END019')
            return ResponseModel(
                status_code=400,
                error_code='END019',
                error_message='Unable to delete endpoint validation',
            ).dict()
        logger.info(request_id + ' | Endpoint validation deletion successful')
        return ResponseModel(
            status_code=200, message='Endpoint validation deleted successfully'
        ).dict()

    @staticmethod
    async def update_endpoint_validation(
        endpoint_id, data: UpdateEndpointValidationModel, request_id
    ):
        """
        Update an endpoint validation by endpoint ID.
        """
        logger.info(request_id + ' | Updating endpoint validation: ' + endpoint_id)
        if not data.validation_enabled:
            logger.error(request_id + ' | Validation enabled is required')
            return ResponseModel(
                status_code=400, error_code='END020', error_message='Validation enabled is required'
            ).dict()
        if not data.validation_schema:
            logger.error(request_id + ' | Validation schema is required')
            return ResponseModel(
                status_code=400, error_code='END021', error_message='Validation schema is required'
            ).dict()
        if not endpoint_collection.find_one({'endpoint_id': endpoint_id}):
            logger.error(request_id + ' | Endpoint does not exist')
            return ResponseModel(
                status_code=400, error_code='END022', error_message='Endpoint does not exist'
            ).dict()
        update_result = endpoint_validation_collection.update_one(
            {'endpoint_id': endpoint_id},
            {
                '$set': {
                    'validation_enabled': data.validation_enabled,
                    'validation_schema': data.validation_schema,
                }
            },
        )
        if not update_result.acknowledged:
            logger.error(request_id + ' | Endpoint validation update failed with code END023')
            return ResponseModel(
                status_code=400,
                error_code='END023',
                error_message='Unable to update endpoint validation',
            ).dict()
        logger.info(request_id + ' | Endpoint validation updated successfully')
