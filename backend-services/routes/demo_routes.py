"""
Protected demo seeding routes for populating the running server with dummy data.
Only available to users with 'manage_gateway' OR 'manage_credits'.
"""

import logging
import time
import uuid

from fastapi import APIRouter, Request, HTTPException

from models.response_model import ResponseModel
from utils.auth_util import auth_required
from utils.demo_seed_util import run_seed
from utils.response_util import respond_rest
from utils.role_util import is_admin_user

demo_router = APIRouter()
logger = logging.getLogger('doorman.gateway')

"""
Endpoint

Request:
{}
Response:
{}
"""


@demo_router.post(
    '/seed', description='Seed the running server with demo data', response_model=ResponseModel
)
async def demo_seed(
    request: Request,
    users: int = 40,
    apis: int = 15,
    endpoints: int = 6,
    groups: int = 8,
    protos: int = 6,
    logs: int = 1500,
    seed: int | None = None,
):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        if not await is_admin_user(username):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code='DEMO001',
                    error_message='Permission denied to run seeder',
                )
            )
        res = run_seed(
            users=users,
            apis=apis,
            endpoints=endpoints,
            groups=groups,
            protos=protos,
            logs=logs,
            seed=seed,
        )
        return respond_rest(ResponseModel(status_code=200, response=res, message='Seed completed'))
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f'{request_id} | Demo seed error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500, error_code='DEMO999', error_message='Failed to seed demo data'
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')
