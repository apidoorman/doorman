"""
Routes to expose gateway metrics to the web client.
"""

import csv
import io
import logging
import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import Response as FastAPIResponse
from pydantic import BaseModel

from models.response_model import ResponseModel
from services.logging_service import LoggingService
from utils.auth_util import auth_required
from utils.database import database
from utils.doorman_cache_util import doorman_cache
from utils.health_check_util import check_mongodb, check_redis
from utils.metrics_util import metrics_store
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool


class LivenessResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    mongodb: bool | None = None
    redis: bool | None = None
    mode: str | None = None
    cache_backend: str | None = None


monitor_router = APIRouter()
logger = logging.getLogger('doorman.gateway')

"""
Endpoint

Request:
{}
Response:
{}
"""


@monitor_router.get(
    '/monitor/metrics', description='Get aggregated gateway metrics', response_model=ResponseModel
)
async def get_metrics(
    request: Request, range: str = '24h', group: str = 'minute', sort: str = 'asc'
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
        if not await platform_role_required_bool(username, 'manage_gateway'):
            return process_response(
                ResponseModel(
                    status_code=403,
                    response_headers={'request_id': request_id},
                    error_code='MON001',
                    error_message='You do not have permission to view monitor metrics',
                ).dict(),
                'rest',
            )
        grp = (group or 'minute').lower()
        if grp not in ('minute', 'day'):
            grp = 'minute'
        srt = (sort or 'asc').lower()
        if srt not in ('asc', 'desc'):
            srt = 'asc'
        snap = metrics_store.snapshot(range, group=grp, sort=srt)
        return process_response(
            ResponseModel(
                status_code=200, response_headers={'request_id': request_id}, response=snap
            ).dict(),
            'rest',
        )
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            ).dict(),
            'rest',
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')


"""
Endpoint

Request:
{}
Response:
{}
"""


@monitor_router.get(
    '/monitor/liveness',
    description='Kubernetes liveness probe endpoint (no auth)',
    response_model=LivenessResponse,
)
async def liveness(request: Request):
    return {'status': 'alive'}


"""
Endpoint

Request:
{}
Response:
{}
"""


@monitor_router.get(
    '/monitor/readiness',
    description='Kubernetes readiness probe endpoint. Detailed status requires manage_gateway permission.',
    response_model=ReadinessResponse,
)
async def readiness(request: Request):
    """Readiness probe endpoint.

    Public/unauthenticated callers:
        Returns minimal status: {'status': 'ready' | 'degraded'}

    Authorized users with 'manage_gateway':
        Returns detailed status including mongodb, redis, mode, cache_backend
    """

    authorized = False
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        authorized = (
            await platform_role_required_bool(username, 'manage_gateway') if username else False
        )
    except Exception:
        authorized = False

    try:
        mongo_ok = await check_mongodb()
        redis_ok = await check_redis()
        ready = mongo_ok and redis_ok

        if not authorized:
            return {'status': 'ready' if ready else 'degraded'}

        return {
            'status': 'ready' if ready else 'degraded',
            'mongodb': mongo_ok,
            'redis': redis_ok,
            'mode': 'memory' if getattr(database, 'memory_only', False) else 'mongodb',
            'cache_backend': 'redis' if getattr(doorman_cache, 'is_redis', False) else 'memory',
        }
    except Exception:
        return {'status': 'degraded'}


"""
Endpoint

Request:
{}
Response:
{}
"""


@monitor_router.get(
    '/monitor/report',
    description='Generate a CSV report for a date range (requires manage_gateway)',
    include_in_schema=False,
)
async def generate_report(request: Request, start: str, end: str):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        if not await platform_role_required_bool(username, 'manage_gateway'):
            return process_response(
                ResponseModel(
                    status_code=403,
                    response_headers={'request_id': request_id},
                    error_code='MON002',
                    error_message='You do not have permission to generate reports',
                ).dict(),
                'rest',
            )

        def _parse_ts(s: str) -> int:
            from datetime import datetime

            fmt_variants = ['%Y-%m-%dT%H:%M', '%Y-%m-%d']
            for fmt in fmt_variants:
                try:
                    return int(datetime.strptime(s, fmt).timestamp())
                except Exception:
                    pass

            try:
                return int(datetime.fromisoformat(s).timestamp())
            except Exception:
                raise ValueError('Invalid date format. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM')

        start_ts = _parse_ts(start)
        end_ts = _parse_ts(end)
        if end_ts < start_ts:
            raise ValueError('End date must be after start date')

        ls = LoggingService()

        import datetime as _dt

        def _to_date_time(ts: int):
            dt = _dt.datetime.utcfromtimestamp(ts)
            return dt.strftime('%Y-%m-%d'), dt.strftime('%H:%M')

        start_date, start_time_str = _to_date_time(start_ts)
        end_date, end_time_str = _to_date_time(end_ts)

        logs: list = []
        offset = 0
        page_limit = 1000
        max_pages = 100
        for _ in range(max_pages):
            batch = await ls.get_logs(
                start_date=start_date,
                end_date=end_date,
                start_time=start_time_str,
                end_time=end_time_str,
                limit=page_limit,
                offset=offset,
                request_id_param=request_id,
            )
            chunk = batch.get('logs', [])
            logs.extend(chunk)
            batch.get('total', 0)
            offset += page_limit
            if not batch.get('has_more') or not chunk:
                break

        def _api_from_endpoint(ep: str) -> str:
            try:
                if ep.startswith('/api/rest/'):
                    parts = ep.split('/')
                    return f'rest:{parts[3]}' if len(parts) > 3 else 'rest:unknown'
                if ep.startswith('/api/graphql/'):
                    return f'graphql:{ep.split("/")[-1] or "unknown"}'
                if ep.startswith('/api/soap/'):
                    return f'soap:{ep.split("/")[-1] or "unknown"}'
                return 'platform'
            except Exception:
                return 'unknown'

        total = 0
        errors = 0
        total_ms = 0.0
        status_counts: dict = {}
        api_totals: dict = {}
        api_errors: dict = {}
        user_totals: dict = {}
        for e in logs:
            ep = str(e.get('endpoint') or '')
            if not ep:
                continue
            total += 1

            status_code = None
            try:
                status_code = (
                    int(e.get('status_code')) if e.get('status_code') is not None else None
                )
            except Exception:
                status_code = None
            level = (e.get('level') or '').upper()
            is_error = (status_code is not None and status_code >= 400) or (
                level not in ('INFO', 'DEBUG')
            )
            if is_error:
                errors += 1
            if status_code is not None:
                status_counts[str(status_code)] = status_counts.get(str(status_code), 0) + 1
            if e.get('response_time') is not None:
                try:
                    total_ms += float(e.get('response_time'))
                except Exception:
                    pass
            api_key = _api_from_endpoint(ep)
            api_totals[api_key] = api_totals.get(api_key, 0) + 1
            if is_error:
                api_errors[api_key] = api_errors.get(api_key, 0) + 1
            uname = e.get('user')
            if uname:
                user_totals[uname] = user_totals.get(uname, 0) + 1

        if total == 0:
            buckets = list(metrics_store._buckets)
            sel = [b for b in buckets if b.start_ts >= start_ts and b.start_ts <= end_ts]
            total = sum(b.count for b in sel)
            errors = sum(b.error_count for b in sel)
            total_ms = sum(b.total_ms for b in sel)
            for b in sel:
                for k, v in (b.status_counts or {}).items():
                    status_counts[k] = status_counts.get(k, 0) + v
                for k, v in (b.api_counts or {}).items():
                    api_totals[k] = api_totals.get(k, 0) + v
                for k, v in (b.api_error_counts or {}).items():
                    api_errors[k] = api_errors.get(k, 0) + v
                for k, v in (b.user_counts or {}).items():
                    user_totals[k] = user_totals.get(k, 0) + v
        buckets = list(metrics_store._buckets)
        sel = [b for b in buckets if b.start_ts >= start_ts and b.start_ts <= end_ts]
        total_bytes_in = sum(getattr(b, 'bytes_in', 0) for b in sel)
        total_bytes_out = sum(getattr(b, 'bytes_out', 0) for b in sel)
        from collections import defaultdict

        daily_bw = defaultdict(lambda: {'in': 0, 'out': 0})
        for b in sel:
            day_ts = int((b.start_ts // 86400) * 86400)
            daily_bw[day_ts]['in'] += getattr(b, 'bytes_in', 0)
            daily_bw[day_ts]['out'] += getattr(b, 'bytes_out', 0)

        avg_ms = (total_ms / total) if total else 0.0

        buf = io.StringIO()
        w = csv.writer(buf)

        w.writerow(['Report', 'From', start, 'To', end])
        w.writerow(['Overview'])
        w.writerow(['total_requests', total])
        w.writerow(['total_errors', errors])
        w.writerow(['successes', max(total - errors, 0)])
        w.writerow(
            ['success_rate', f'{(0 if total == 0 else (100.0 * (total - errors) / total)):.2f}%']
        )
        w.writerow(['avg_response_ms', f'{avg_ms:.2f}'])
        w.writerow([])
        w.writerow(['Bandwidth Overview'])
        w.writerow(['total_bytes_in', int(total_bytes_in)])
        w.writerow(['total_bytes_out', int(total_bytes_out)])
        w.writerow(['total_bytes', int(total_bytes_in + total_bytes_out)])
        w.writerow([])

        w.writerow(['Status Codes'])
        w.writerow(['status', 'count'])
        for code, cnt in sorted(status_counts.items(), key=lambda kv: int(kv[0])):
            w.writerow([code, cnt])
        w.writerow([])

        w.writerow(['API Usage'])
        w.writerow(['api', 'total', 'errors', 'successes', 'success_rate'])
        for api, cnt in sorted(api_totals.items(), key=lambda kv: kv[1], reverse=True):
            err = api_errors.get(api, 0)
            succ = max(cnt - err, 0)
            rate = 0.0 if cnt == 0 else (100.0 * succ / cnt)
            w.writerow([api, cnt, err, succ, f'{rate:.2f}%'])
        w.writerow([])

        w.writerow(['User Usage'])
        w.writerow(['username', 'requests'])
        for uname, cnt in sorted(user_totals.items(), key=lambda kv: kv[1], reverse=True):
            w.writerow([uname, cnt])

        w.writerow([])
        w.writerow(['Bandwidth (per day, UTC)'])
        w.writerow(['date', 'bytes_in', 'bytes_out', 'total'])
        for day_ts in sorted(daily_bw.keys()):
            date_str = _dt.datetime.utcfromtimestamp(day_ts).strftime('%Y-%m-%d')
            bi = int(daily_bw[day_ts]['in'])
            bo = int(daily_bw[day_ts]['out'])
            w.writerow([date_str, bi, bo, bi + bo])

        csv_bytes = buf.getvalue().encode('utf-8')
        filename = f'doorman_report_{start}_to_{end}.csv'
        return FastAPIResponse(
            content=csv_bytes,
            media_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'},
        )
    except ValueError as ve:
        return process_response(
            ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='MON003',
                error_message=str(ve),
            ).dict(),
            'rest',
        )
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error in report: {str(e)}', exc_info=True)
        return process_response(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            ).dict(),
            'rest',
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')
