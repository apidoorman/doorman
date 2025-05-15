"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException
from fastapi_jwt_auth import AuthJWT


from models.response_model import ResponseModel
from services.api_service import ApiService
from utils import api_util
from utils.auth_util import auth_required
from models.create_api_model import CreateApiModel
from models.update_api_model import UpdateApiModel
from models.api_model_response import ApiModelResponse
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

import uuid
import time
import logging
from typing import List
import os
import subprocess
from datetime import datetime
import re

api_router = APIRouter() 
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("doorman.gateway")

@api_router.post("",
    description="Add API",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "API created successfully"
                    }
                }
            }
        }
    }
)
async def create_api(request: Request, api_data: CreateApiModel, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
    logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
    try:
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_apis'):
            logger.warning(f"{request_id} | Permission denied for user: {Authorize.get_jwt_subject()}")
            return process_response(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="API007",
                error_message="You do not have permission to create APIs"
            ).dict(), "rest")
        return process_response(await ApiService.create_api(api_data, request_id), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@api_router.put("/{api_name}/{api_version}",
    description="Update API",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "API updated successfully"
                    }
                }
            }
        }
    }
)
async def update_api(api_name: str, api_version: str, request: Request, api_data: UpdateApiModel, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_apis'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="API008",
                error_message="You do not have permission to update APIs"
            ).dict(), "rest")
        return process_response(await ApiService.update_api(api_name, api_version, api_data, request_id), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@api_router.get("/{api_name}/{api_version}",
    description="Get API",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=ApiModelResponse,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "API retrieved successfully"
                    }
                }
            }
        }
    }
)
async def get_api_by_name_version(api_name: str, api_version: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await ApiService.get_api_by_name_version(api_name, api_version, request_id), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
    
@api_router.delete("/{api_name}/{api_version}",
    description="Delete API",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "API deleted successfully"
                    }
                }
            }
        }
    }
)
async def delete_api(api_name: str, api_version: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await ApiService.delete_api(api_name, api_version, request_id), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@api_router.get("/all",
    description="Get all APIs",
    dependencies=[
        Depends(auth_required) 
    ],
    response_model=List[ApiModelResponse]
)
async def get_all_apis(request: Request, Authorize: AuthJWT = Depends(), page: int = 1, page_size: int = 10):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await ApiService.get_apis(page, page_size, request_id), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@api_router.post("/proto/{api_name}/{api_version}",
    description="Upload proto file",
    dependencies=[
        Depends(auth_required) 
    ],
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Proto file uploaded successfully"
                    }
                }
            }
        }
    })
async def upload_proto_file(
    api_name: str,
    api_version: str,
    file: UploadFile = File(...),
    Authorize: AuthJWT = Depends()
):
    """Upload a proto file for an API"""
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()}")
        logger.info(f"{request_id} | Endpoint: POST /proto/{api_name}/{api_version}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_apis'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={"request_id": request_id},
                error_code="AUTH001",
                error_message="User does not have permission to manage APIs"
            ).dict(), "rest")
        content = await file.read()
        proto_content = content.decode('utf-8')
        if 'package' in proto_content:
            proto_content = re.sub(r'package\s+[^;]+;', f'package {api_name}_{api_version};', proto_content)
        else:
            proto_content = re.sub(r'syntax\s*=\s*"proto3";', f'syntax = "proto3";\n\npackage {api_name}_{api_version};', proto_content)
        proto_filename = f"{api_name}_{api_version}.proto"
        proto_path = os.path.join("proto", proto_filename)
        os.makedirs("proto", exist_ok=True)
        with open(proto_path, "w") as f:
            f.write(proto_content)
        os.makedirs("generated", exist_ok=True)
        try:
            subprocess.run([
                "python", "-m", "grpc_tools.protoc",
                f"--proto_path=proto",
                f"--python_out=generated",
                f"--grpc_python_out=generated",
                proto_path
            ], check=True)
            init_path = os.path.join("generated", "__init__.py")
            if not os.path.exists(init_path):
                with open(init_path, "w") as f:
                    f.write('"""Generated gRPC code."""\n')
            pb2_file = os.path.join("generated", f"{api_name}_{api_version}_pb2.py")
            pb2_grpc_file = os.path.join("generated", f"{api_name}_{api_version}_pb2_grpc.py")
            if os.path.exists(pb2_grpc_file):
                with open(pb2_grpc_file, 'r') as f:
                    content = f.read()
                content = content.replace(
                    f'import {api_name}_{api_version}_pb2 as {api_name}__{api_version}__pb2',
                    f'from generated import {api_name}_{api_version}_pb2 as {api_name}__{api_version}__pb2'
                )
                with open(pb2_grpc_file, 'w') as f:
                    f.write(content)
            return process_response(ResponseModel(
                status_code=200,
                response_headers={"request_id": request_id},
                message="Proto file uploaded and gRPC code generated successfully"
            ).dict(), "rest")
        except subprocess.CalledProcessError as e:
            logger.error(f"{request_id} | Failed to generate gRPC code: {str(e)}")
            return process_response(ResponseModel(
                status_code=500,
                response_headers={"request_id": request_id},
                error_code="GTW012",
                error_message=f"Failed to generate gRPC code: {str(e)}"
            ).dict(), "rest")
    except Exception as e:
        logger.error(f"{request_id} | Error uploading proto file: {str(e)}")
        return process_response(ResponseModel(
            status_code=500,
            response_headers={"request_id": request_id},
            error_code="GTW012",
            error_message=f"Failed to upload proto file: {str(e)}"
        ).dict(), "rest")
    finally:
        logger.info(f"{request_id} | Total time: {time.time() * 1000 - start_time}ms")

@api_router.get("/proto/{api_name}/{api_version}",
    description="Get proto file",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Proto file retrieved successfully"
                    }
                }
            }
        }
    }
)
async def get_proto_file(
    api_name: str,
    api_version: str,
    request: Request,
    Authorize: AuthJWT = Depends()
):
    """Get a proto file for an API"""
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    logger.info(f"{request_id} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')[:-3]}ms")
    logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}")
    logger.info(f"{request_id} | Endpoint: {request.method} {request.url.path}")

    try:
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_apis'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={"request_id": request_id},
                error_code="AUTH001",
                error_message="User does not have permission to manage APIs"
            ).dict(), "rest")
        api = await api_util.get_api(None, f"{api_name}/{api_version}")
        if not api:
            return process_response(ResponseModel(
                status_code=404,
                response_headers={"request_id": request_id},
                error_code="API001",
                error_message=f"API {api_name}/{api_version} not found"
            ).dict(), "rest")
        proto_filename = f"{api_name}_{api_version}.proto"
        proto_path = os.path.join("proto", proto_filename)
        if not os.path.exists(proto_path):
            return process_response(ResponseModel(
                status_code=404,
                response_headers={"request_id": request_id},
                error_code="API002",
                error_message=f"Proto file not found for API {api_name}/{api_version}"
            ).dict(), "rest")
        with open(proto_path, "r") as f:
            proto_content = f.read()
        return process_response(ResponseModel(
            status_code=200,
            response_headers={"request_id": request_id},
            message="Proto file retrieved successfully",
            response={"content": proto_content}
        ).dict(), "rest")
    except Exception as e:
        logger.error(f"{request_id} | Failed to get proto file: {str(e)}")
        return process_response(ResponseModel(
            status_code=500,
            response_headers={"request_id": request_id},
            error_code="API002",
            error_message=f"Failed to get proto file: {str(e)}"
        ).dict(), "rest")
    finally:
        logger.info(f"{request_id} | Total time: {time.time() * 1000 - start_time}ms")

@api_router.put("/proto/{api_name}/{api_version}",
    description="Update proto file",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Proto file updated successfully"
                    }
                }
            }
        }
    }
)
async def update_proto_file(
    api_name: str,
    api_version: str,
    request: Request,
    proto_file: UploadFile = File(...),
    Authorize: AuthJWT = Depends()
):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_apis'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="API008",
                error_message="You do not have permission to update proto files"
            ).dict(), "rest")
        key = f"{api_name}_{api_version}"
        proto_path = os.path.join("proto", f"{key}.proto")
        with open(proto_path, "wb") as f:
            f.write(await proto_file.read())
        try:
            subprocess.run([
                'python', '-m', 'grpc_tools.protoc',
                f'--proto_path=proto',
                f'--python_out=generated',
                f'--grpc_python_out=generated',
                proto_path
            ], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"{request_id} | Failed to generate gRPC code: {str(e)}")
            return process_response(ResponseModel(
                status_code=500,
                response_headers={
                    "request_id": request_id
                },
                error_code="API009",
                error_message="Failed to generate gRPC code from proto file"
            ).dict(), "rest")
        
        return process_response(ResponseModel(
            status_code=200,
            response_headers={
                "request_id": request_id
            },
            message="Proto file updated successfully"
        ).dict(), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
        ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@api_router.delete("/proto/{api_name}/{api_version}",
    description="Delete proto file",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Proto file deleted successfully"
                    }
                }
            }
        }
    }
)
async def delete_proto_file(api_name: str, api_version: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_apis'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="API008",
                error_message="You do not have permission to delete proto files"
            ).dict(), "rest")
        key = f"{api_name}_{api_version}"
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        proto_path = os.path.join(project_root, "proto", f"{key}.proto")
        if os.path.exists(proto_path):
            os.remove(proto_path)
            logger.info(f"{request_id} | Deleted proto file: {proto_path}")
        generated_dir = os.path.join(project_root, "generated")
        generated_files = [
            f"{key}_pb2.py",
            f"{key}_pb2.pyc",
            f"{key}_pb2_grpc.py",
            f"{key}_pb2_grpc.pyc"
        ]
        for file in generated_files:
            file_path = os.path.join(generated_dir, file)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"{request_id} | Deleted generated file: {file_path}")
        return process_response(ResponseModel(
            status_code=200,
            response_headers={
                "request_id": request_id
            },
            message="Proto file and generated files deleted successfully"
        ).dict(), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
        ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")