"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException
from fastapi_jwt_auth import AuthJWT
from werkzeug.utils import secure_filename
from pathlib import Path
import os
import re
import logging
import uuid
import time
from datetime import datetime
import subprocess
from typing import List

from models.response_model import ResponseModel
from services.api_service import ApiService
from utils import api_util
from utils.auth_util import auth_required
from models.create_api_model import CreateApiModel
from models.update_api_model import UpdateApiModel
from models.api_model_response import ApiModelResponse
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

api_router = APIRouter() 
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("doorman.gateway")

PROJECT_ROOT = Path(__file__).parent.parent.absolute()

def sanitize_filename(filename: str):
    if not filename:
        raise ValueError("Empty filename provided")
    sanitized = secure_filename(filename)
    if not sanitized:
        raise ValueError("Invalid filename after sanitization")
    return sanitized

def validate_path(base_path: Path, target_path: Path):
    try:
        base_path = Path(os.path.realpath(base_path))
        target_path = Path(os.path.realpath(target_path))
        project_root = Path(os.path.realpath(PROJECT_ROOT))
        if not str(base_path).startswith(str(project_root)):
            return False
        return str(target_path).startswith(str(base_path))
    except Exception as e:
        logger.error(f"Path validation error: {str(e)}")
        return False

def get_safe_proto_path(api_name: str, api_version: str):
    try:
        safe_api_name = sanitize_filename(api_name)
        safe_api_version = sanitize_filename(api_version)
        key = f"{safe_api_name}_{safe_api_version}"
        proto_dir = (PROJECT_ROOT / "proto").resolve()
        generated_dir = (PROJECT_ROOT / "generated").resolve()
        proto_dir.mkdir(exist_ok=True)
        generated_dir.mkdir(exist_ok=True)
        proto_path = (proto_dir / f"{key}.proto").resolve()
        if not validate_path(PROJECT_ROOT, proto_path) or not validate_path(PROJECT_ROOT, generated_dir):
            raise ValueError("Invalid path detected")
        return proto_path, generated_dir
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Path validation error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create safe paths: {str(e)}"
        )

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
async def upload_proto_file(api_name: str, api_version: str, file: UploadFile = File(...), Authorize: AuthJWT = Depends()):
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
        proto_path, generated_dir = get_safe_proto_path(api_name, api_version)
        content = await file.read()
        proto_content = content.decode('utf-8')
        safe_api_name = sanitize_filename(api_name)
        safe_api_version = sanitize_filename(api_version)
        if 'package' in proto_content:
            proto_content = re.sub(r'package\s+[^;]+;', f'package {safe_api_name}_{safe_api_version};', proto_content)
        else:
            proto_content = re.sub(r'syntax\s*=\s*"proto3";', f'syntax = "proto3";\n\npackage {safe_api_name}_{safe_api_version};', proto_content)
        proto_path.write_text(proto_content)
        try:
            subprocess.run([
                "python", "-m", "grpc_tools.protoc",
                f"--proto_path={proto_path.parent}",
                f"--python_out={generated_dir}",
                f"--grpc_python_out={generated_dir}",
                str(proto_path)
            ], check=True)
            init_path = (generated_dir / "__init__.py").resolve()
            if not validate_path(generated_dir, init_path):
                raise ValueError("Invalid init path")
            if not init_path.exists():
                init_path.write_text('"""Generated gRPC code."""\n')
            pb2_grpc_file = (generated_dir / f"{safe_api_name}_{safe_api_version}_pb2_grpc.py").resolve()
            if not validate_path(generated_dir, pb2_grpc_file):
                raise ValueError("Invalid grpc file path")
            if pb2_grpc_file.exists():
                content = pb2_grpc_file.read_text()
                content = content.replace(
                    f'import {safe_api_name}_{safe_api_version}_pb2 as {safe_api_name}__{safe_api_version}__pb2',
                    f'from generated import {safe_api_name}_{safe_api_version}_pb2 as {safe_api_name}__{safe_api_version}__pb2'
                )
                pb2_grpc_file.write_text(content)
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
    except HTTPException as e:
        logger.error(f"{request_id} | Path validation error: {str(e)}")
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={"request_id": request_id},
            error_code="GTW013",
            error_message=str(e.detail)
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
async def get_proto_file(api_name: str, api_version: str, request: Request, Authorize: AuthJWT = Depends()):
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
        proto_path, _ = get_safe_proto_path(api_name, api_version)
        if not proto_path.exists():
            return process_response(ResponseModel(
                status_code=404,
                response_headers={"request_id": request_id},
                error_code="API002",
                error_message=f"Proto file not found for API {api_name}/{api_version}"
            ).dict(), "rest")
        proto_content = proto_path.read_text()
        return process_response(ResponseModel(
            status_code=200,
            response_headers={"request_id": request_id},
            message="Proto file retrieved successfully",
            response={"content": proto_content}
        ).dict(), "rest")
    except HTTPException as e:
        logger.error(f"{request_id} | Path validation error: {str(e)}")
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={"request_id": request_id},
            error_code="GTW013",
            error_message=str(e.detail)
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
async def update_proto_file(api_name: str, api_version: str, request: Request, proto_file: UploadFile = File(...), Authorize: AuthJWT = Depends()):
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
        proto_path, generated_dir = get_safe_proto_path(api_name, api_version)
        proto_path.write_bytes(await proto_file.read())
        try:
            subprocess.run([
                'python', '-m', 'grpc_tools.protoc',
                f'--proto_path={proto_path.parent}',
                f'--python_out={generated_dir}',
                f'--grpc_python_out={generated_dir}',
                str(proto_path)
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
    except HTTPException as e:
        logger.error(f"{request_id} | Path validation error: {str(e)}")
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={"request_id": request_id},
            error_code="GTW013",
            error_message=str(e.detail)
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
                response_headers={"request_id": request_id},
                error_code="API008",
                error_message="You do not have permission to delete proto files"
            ).dict(), "rest")
        proto_path, generated_dir = get_safe_proto_path(api_name, api_version)
        safe_api_name = sanitize_filename(api_name)
        safe_api_version = sanitize_filename(api_version)
        key = f"{safe_api_name}_{safe_api_version}"
        if proto_path.exists():
            if not validate_path(PROJECT_ROOT, proto_path):
                raise ValueError("Unsafe proto file path detected")
            proto_path.unlink()
            logger.info(f"{request_id} | Deleted proto file: {proto_path}")
        generated_files = [f"{key}_pb2.py", f"{key}_pb2.pyc", f"{key}_pb2_grpc.py", f"{key}_pb2_grpc.pyc"]
        for file in generated_files:
            file_path = (generated_dir / file).resolve()
            if not validate_path(generated_dir, file_path):
                logger.warning(f"{request_id} | Unsafe file path detected: {file_path}. Skipping deletion.")
                continue
            if file_path.exists():
                file_path.unlink()
                logger.info(f"{request_id} | Deleted generated file: {file_path}")
        return process_response(ResponseModel(
            status_code=200,
            response_headers={"request_id": request_id},
            message="Proto file and generated files deleted successfully"
        ).dict(), "rest")
    except ValueError as e:
        logger.error(f"{request_id} | Path validation error: {str(e)}")
        return process_response(ResponseModel(
            status_code=400,
            response_headers={"request_id": request_id},
            error_code="GTW013",
            error_message=str(e)
        ).dict(), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={"request_id": request_id},
            error_code="GTW999",
            error_message="An unexpected error occurred"
        ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")