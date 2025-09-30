"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException
from werkzeug.utils import secure_filename
from pathlib import Path

from models.response_model import ResponseModel
from utils.auth_util import auth_required
from utils.response_util import process_response
from utils.constants import Headers, Defaults, Roles, ErrorCodes, Messages
from utils.role_util import platform_role_required_bool

import os
import re
import logging
import uuid
import time
from datetime import datetime
import subprocess

proto_router = APIRouter()
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

@proto_router.post("/{api_name}/{api_version}",
    description="Upload proto file",
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
async def upload_proto_file(api_name: str, api_version: str, file: UploadFile = File(...), request: Request = None):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        max_size = int(os.getenv(Defaults.MAX_MULTIPART_SIZE_BYTES_ENV, Defaults.MAX_MULTIPART_SIZE_BYTES_DEFAULT))
        cl = request.headers.get('content-length') if request else None
        try:
            if cl and int(cl) > max_size:
                return process_response(ResponseModel(
                    status_code=413,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code=ErrorCodes.REQUEST_TOO_LARGE,
                    error_message=Messages.FILE_TOO_LARGE
                ).dict(), "rest")
        except Exception:
            pass
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username}")
        logger.info(f"{request_id} | Endpoint: POST /proto/{api_name}/{api_version}")
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code=ErrorCodes.AUTH_REQUIRED,
                error_message=Messages.PERMISSION_MANAGE_APIS
            ).dict(), "rest")
        original_name = file.filename or ""
        if not original_name.lower().endswith('.proto'):
            return process_response(ResponseModel(
                status_code=400,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code=ErrorCodes.REQUEST_FILE_TYPE,
                error_message=Messages.ONLY_PROTO_ALLOWED
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
                response_headers={Headers.REQUEST_ID: request_id},
                error_code=ErrorCodes.GRPC_GENERATION_FAILED,
                error_message=f"{Messages.GRPC_GEN_FAILED}: {str(e)}"
            ).dict(), "rest")
    except HTTPException as e:
        logger.error(f"{request_id} | Path validation error: {str(e)}")
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={Headers.REQUEST_ID: request_id},
            error_code=ErrorCodes.PATH_VALIDATION,
            error_message=str(e.detail)
        ).dict(), "rest")
    except Exception as e:
        logger.error(f"{request_id} | Error uploading proto file: {str(e)}")
        return process_response(ResponseModel(
            status_code=500,
            response_headers={Headers.REQUEST_ID: request_id},
            error_code=ErrorCodes.GRPC_GENERATION_FAILED,
            error_message=f"Failed to upload proto file: {str(e)}"
        ).dict(), "rest")
    finally:
        logger.info(f"{request_id} | Total time: {time.time() * 1000 - start_time}ms")

@proto_router.get("/{api_name}/{api_version}",
    description="Get proto file",
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
async def get_proto_file(api_name: str, api_version: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    payload = await auth_required(request)
    username = payload.get("sub")
    logger.info(f"{request_id} | Username: {username} | From: {request.client.host}")
    logger.info(f"{request_id} | Endpoint: {request.method} {request.url.path}")
    try:
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code=ErrorCodes.AUTH_REQUIRED,
                error_message=Messages.PERMISSION_MANAGE_APIS
            ).dict(), "rest")
        proto_path, _ = get_safe_proto_path(api_name, api_version)
        if not proto_path.exists():
            return process_response(ResponseModel(
                status_code=404,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code=ErrorCodes.API_NOT_FOUND,
                error_message=f"Proto file not found for API {api_name}/{api_version}"
            ).dict(), "rest")
        proto_content = proto_path.read_text()
        return process_response(ResponseModel(
            status_code=200,
            response_headers={Headers.REQUEST_ID: request_id},
            message="Proto file retrieved successfully",
            response={"content": proto_content}
        ).dict(), "rest")
    except HTTPException as e:
        logger.error(f"{request_id} | Path validation error: {str(e)}")
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={Headers.REQUEST_ID: request_id},
            error_code=ErrorCodes.PATH_VALIDATION,
            error_message=str(e.detail)
        ).dict(), "rest")
    except Exception as e:
        logger.error(f"{request_id} | Failed to get proto file: {str(e)}")
        return process_response(ResponseModel(
            status_code=500,
            response_headers={Headers.REQUEST_ID: request_id},
            error_code=ErrorCodes.API_NOT_FOUND,
            error_message=f"Failed to get proto file: {str(e)}"
        ).dict(), "rest")
    finally:
        logger.info(f"{request_id} | Total time: {time.time() * 1000 - start_time}ms")

@proto_router.put("/{api_name}/{api_version}",
    description="Update proto file",
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
async def update_proto_file(api_name: str, api_version: str, request: Request, proto_file: UploadFile = File(...)):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code="API008",
                error_message="You do not have permission to update proto files"
            ).dict(), "rest")
        original_name = proto_file.filename or ""
        if not original_name.lower().endswith('.proto'):
            return process_response(ResponseModel(
                status_code=400,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code=ErrorCodes.REQUEST_FILE_TYPE,
                error_message=Messages.ONLY_PROTO_ALLOWED
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
                response_headers={Headers.REQUEST_ID: request_id},
                error_code="API009",
                error_message="Failed to generate gRPC code from proto file"
            ).dict(), "rest")
        return process_response(ResponseModel(
            status_code=200,
            response_headers={Headers.REQUEST_ID: request_id},
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
            response_headers={Headers.REQUEST_ID: request_id},
            error_code=ErrorCodes.UNEXPECTED,
            error_message=Messages.UNEXPECTED
        ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@proto_router.delete("/{api_name}/{api_version}",
    description="Delete proto file",
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
async def delete_proto_file(api_name: str, api_version: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={Headers.REQUEST_ID: request_id},
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
            response_headers={Headers.REQUEST_ID: request_id},
            message="Proto file and generated files deleted successfully"
        ).dict(), "rest")
    except ValueError as e:
        logger.error(f"{request_id} | Path validation error: {str(e)}")
        return process_response(ResponseModel(
            status_code=400,
            response_headers={Headers.REQUEST_ID: request_id},
            error_code=ErrorCodes.PATH_VALIDATION,
            error_message=str(e)
        ).dict(), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={Headers.REQUEST_ID: request_id},
            error_code=ErrorCodes.UNEXPECTED,
            error_message=Messages.UNEXPECTED
        ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms") 
