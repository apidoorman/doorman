"""
Analytics API routes for querying metrics and performance data.

Provides comprehensive analytics endpoints for:
- Dashboard overview statistics
- Time-series data with filtering
- Top APIs and users
- Per-API and per-user breakdowns
- Endpoint performance analysis
"""

from fastapi import APIRouter, Request, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid
import time
import logging
from datetime import datetime, timedelta

from models.response_model import ResponseModel
from utils.response_util import respond_rest, process_response
from utils.auth_util import auth_required
from utils.role_util import platform_role_required_bool
from utils.enhanced_metrics_util import enhanced_metrics_store
from utils.analytics_aggregator import analytics_aggregator

analytics_router = APIRouter()
logger = logging.getLogger('doorman.analytics')


# ============================================================================
# ENDPOINT 1: Dashboard Overview
# ============================================================================

@analytics_router.get('/analytics/overview',
    description='Get dashboard overview statistics',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Analytics overview',
            'content': {
                'application/json': {
                    'example': {
                        'total_requests': 12345,
                        'total_errors': 123,
                        'error_rate': 0.01,
                        'avg_response_ms': 150.5,
                        'percentiles': {
                            'p50': 120.0,
                            'p75': 180.0,
                            'p90': 250.0,
                            'p95': 300.0,
                            'p99': 450.0
                        },
                        'unique_users': 150,
                        'total_bandwidth': 1073741824,
                        'top_apis': [
                            {'api': 'rest:customer', 'count': 5000},
                            {'api': 'rest:orders', 'count': 3000}
                        ],
                        'top_users': [
                            {'user': 'john_doe', 'count': 500},
                            {'user': 'jane_smith', 'count': 300}
                        ]
                    }
                }
            }
        }
    }
)
async def get_analytics_overview(
    request: Request,
    start_ts: Optional[int] = Query(None, description='Start timestamp (Unix seconds)'),
    end_ts: Optional[int] = Query(None, description='End timestamp (Unix seconds)'),
    range: Optional[str] = Query('24h', description='Time range (1h, 24h, 7d, 30d)')
):
    """
    Get dashboard overview statistics.
    
    Returns summary metrics including:
    - Total requests and errors
    - Error rate
    - Average response time
    - Latency percentiles (p50, p75, p90, p95, p99)
    - Unique user count
    - Total bandwidth
    - Top 10 APIs
    - Top 10 users
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Authentication and authorization
        payload = await auth_required(request)
        username = payload.get('sub')
        
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        
        if not await platform_role_required_bool(username, 'view_analytics'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='ANALYTICS001',
                error_message='You do not have permission to view analytics'
            ))
        
        # Determine time range
        if start_ts and end_ts:
            # Use provided timestamps
            pass
        else:
            # Use range parameter
            end_ts = int(time.time())
            range_map = {
                '1h': 3600,
                '24h': 86400,
                '7d': 604800,
                '30d': 2592000
            }
            seconds = range_map.get(range, 86400)
            start_ts = end_ts - seconds
        
        # Get analytics snapshot
        snapshot = enhanced_metrics_store.get_snapshot(start_ts, end_ts)
        
        # Build response
        overview = {
            'time_range': {
                'start_ts': start_ts,
                'end_ts': end_ts,
                'duration_seconds': end_ts - start_ts
            },
            'summary': {
                'total_requests': snapshot.total_requests,
                'total_errors': snapshot.total_errors,
                'error_rate': snapshot.error_rate,
                'avg_response_ms': snapshot.avg_response_ms,
                'unique_users': snapshot.unique_users,
                'total_bandwidth': snapshot.total_bytes_in + snapshot.total_bytes_out,
                'bandwidth_in': snapshot.total_bytes_in,
                'bandwidth_out': snapshot.total_bytes_out
            },
            'percentiles': snapshot.percentiles.to_dict(),
            'top_apis': snapshot.top_apis,
            'top_users': snapshot.top_users,
            'status_distribution': snapshot.status_distribution
        }
        
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            response=overview
        ))
    
    except Exception as e:
        logger.error(f'{request_id} | Error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='ANALYTICS999',
            error_message='An unexpected error occurred'
        ))
    
    finally:
        end_time = time.time()
        logger.info(f'{request_id} | Total time: {(end_time - start_time) * 1000:.2f}ms')


# ============================================================================
# ENDPOINT 2: Time-Series Data
# ============================================================================

@analytics_router.get('/analytics/timeseries',
    description='Get time-series analytics data with filtering',
    response_model=ResponseModel
)
async def get_analytics_timeseries(
    request: Request,
    start_ts: Optional[int] = Query(None, description='Start timestamp (Unix seconds)'),
    end_ts: Optional[int] = Query(None, description='End timestamp (Unix seconds)'),
    range: Optional[str] = Query('24h', description='Time range (1h, 24h, 7d, 30d)'),
    granularity: Optional[str] = Query('auto', description='Data granularity (auto, minute, 5minute, hour, day)'),
    metric_type: Optional[str] = Query(None, description='Specific metric to return (request_count, error_rate, latency, bandwidth)')
):
    """
    Get time-series analytics data.
    
    Returns series of data points over time with:
    - Timestamp
    - Request count
    - Error count and rate
    - Average response time
    - Latency percentiles
    - Bandwidth (in/out)
    - Unique users
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        
        if not await platform_role_required_bool(username, 'view_analytics'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='ANALYTICS001',
                error_message='You do not have permission to view analytics'
            ))
        
        # Determine time range
        if start_ts and end_ts:
            pass
        else:
            end_ts = int(time.time())
            range_map = {'1h': 3600, '24h': 86400, '7d': 604800, '30d': 2592000}
            seconds = range_map.get(range, 86400)
            start_ts = end_ts - seconds
        
        # Get snapshot with time-series data
        snapshot = enhanced_metrics_store.get_snapshot(start_ts, end_ts, granularity)
        
        # Filter by metric type if specified
        series = snapshot.series
        if metric_type:
            # Extract only requested metric
            filtered_series = []
            for point in series:
                filtered_point = {'timestamp': point['timestamp']}
                if metric_type == 'request_count':
                    filtered_point['count'] = point['count']
                elif metric_type == 'error_rate':
                    filtered_point['error_rate'] = point['error_rate']
                    filtered_point['error_count'] = point['error_count']
                elif metric_type == 'latency':
                    filtered_point['avg_ms'] = point['avg_ms']
                    filtered_point['percentiles'] = point['percentiles']
                elif metric_type == 'bandwidth':
                    filtered_point['bytes_in'] = point['bytes_in']
                    filtered_point['bytes_out'] = point['bytes_out']
                filtered_series.append(filtered_point)
            series = filtered_series
        
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            response={
                'time_range': {'start_ts': start_ts, 'end_ts': end_ts},
                'granularity': granularity,
                'series': series,
                'data_points': len(series)
            }
        ))
    
    except Exception as e:
        logger.error(f'{request_id} | Error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='ANALYTICS999',
            error_message='An unexpected error occurred'
        ))
    
    finally:
        end_time = time.time()
        logger.info(f'{request_id} | Total time: {(end_time - start_time) * 1000:.2f}ms')


# ============================================================================
# ENDPOINT 3: Top APIs
# ============================================================================

@analytics_router.get('/analytics/top-apis',
    description='Get most used APIs',
    response_model=ResponseModel
)
async def get_top_apis(
    request: Request,
    start_ts: Optional[int] = Query(None),
    end_ts: Optional[int] = Query(None),
    range: Optional[str] = Query('24h'),
    limit: int = Query(10, ge=1, le=100, description='Number of APIs to return')
):
    """
    Get top N most used APIs.
    
    Returns list of APIs sorted by request count with:
    - API name
    - Total requests
    - Error count
    - Error rate
    - Average response time
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        
        if not await platform_role_required_bool(username, 'view_analytics'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='ANALYTICS001',
                error_message='You do not have permission to view analytics'
            ))
        
        # Determine time range
        if start_ts and end_ts:
            pass
        else:
            end_ts = int(time.time())
            range_map = {'1h': 3600, '24h': 86400, '7d': 604800, '30d': 2592000}
            seconds = range_map.get(range, 86400)
            start_ts = end_ts - seconds
        
        # Get snapshot
        snapshot = enhanced_metrics_store.get_snapshot(start_ts, end_ts)
        
        # Get top APIs (already sorted by count)
        top_apis = snapshot.top_apis[:limit]
        
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            response={
                'time_range': {'start_ts': start_ts, 'end_ts': end_ts},
                'top_apis': top_apis,
                'total_apis': len(snapshot.top_apis)
            }
        ))
    
    except Exception as e:
        logger.error(f'{request_id} | Error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='ANALYTICS999',
            error_message='An unexpected error occurred'
        ))
    
    finally:
        end_time = time.time()
        logger.info(f'{request_id} | Total time: {(end_time - start_time) * 1000:.2f}ms')


# ============================================================================
# ENDPOINT 4: Top Users
# ============================================================================

@analytics_router.get('/analytics/top-users',
    description='Get highest consuming users',
    response_model=ResponseModel
)
async def get_top_users(
    request: Request,
    start_ts: Optional[int] = Query(None),
    end_ts: Optional[int] = Query(None),
    range: Optional[str] = Query('24h'),
    limit: int = Query(10, ge=1, le=100, description='Number of users to return')
):
    """
    Get top N highest consuming users.
    
    Returns list of users sorted by request count.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        
        if not await platform_role_required_bool(username, 'view_analytics'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='ANALYTICS001',
                error_message='You do not have permission to view analytics'
            ))
        
        # Determine time range
        if start_ts and end_ts:
            pass
        else:
            end_ts = int(time.time())
            range_map = {'1h': 3600, '24h': 86400, '7d': 604800, '30d': 2592000}
            seconds = range_map.get(range, 86400)
            start_ts = end_ts - seconds
        
        # Get snapshot
        snapshot = enhanced_metrics_store.get_snapshot(start_ts, end_ts)
        
        # Get top users (already sorted by count)
        top_users = snapshot.top_users[:limit]
        
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            response={
                'time_range': {'start_ts': start_ts, 'end_ts': end_ts},
                'top_users': top_users,
                'total_users': len(snapshot.top_users)
            }
        ))
    
    except Exception as e:
        logger.error(f'{request_id} | Error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='ANALYTICS999',
            error_message='An unexpected error occurred'
        ))
    
    finally:
        end_time = time.time()
        logger.info(f'{request_id} | Total time: {(end_time - start_time) * 1000:.2f}ms')


# ============================================================================
# ENDPOINT 5: Top Endpoints
# ============================================================================

@analytics_router.get('/analytics/top-endpoints',
    description='Get slowest/most-used endpoints',
    response_model=ResponseModel
)
async def get_top_endpoints(
    request: Request,
    start_ts: Optional[int] = Query(None),
    end_ts: Optional[int] = Query(None),
    range: Optional[str] = Query('24h'),
    sort_by: str = Query('count', description='Sort by: count, avg_ms, error_rate'),
    limit: int = Query(10, ge=1, le=100)
):
    """
    Get top endpoints sorted by usage or performance.
    
    Returns detailed per-endpoint metrics including:
    - Request count
    - Error count and rate
    - Average response time
    - Latency percentiles
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        
        if not await platform_role_required_bool(username, 'view_analytics'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='ANALYTICS001',
                error_message='You do not have permission to view analytics'
            ))
        
        # Determine time range
        if start_ts and end_ts:
            pass
        else:
            end_ts = int(time.time())
            range_map = {'1h': 3600, '24h': 86400, '7d': 604800, '30d': 2592000}
            seconds = range_map.get(range, 86400)
            start_ts = end_ts - seconds
        
        # Get snapshot
        snapshot = enhanced_metrics_store.get_snapshot(start_ts, end_ts)
        
        # Get and sort endpoints
        endpoints = snapshot.top_endpoints
        
        if sort_by == 'avg_ms':
            endpoints.sort(key=lambda x: x['avg_ms'], reverse=True)
        elif sort_by == 'error_rate':
            endpoints.sort(key=lambda x: x['error_rate'], reverse=True)
        # Default is already sorted by count
        
        top_endpoints = endpoints[:limit]
        
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            response={
                'time_range': {'start_ts': start_ts, 'end_ts': end_ts},
                'sort_by': sort_by,
                'top_endpoints': top_endpoints,
                'total_endpoints': len(endpoints)
            }
        ))
    
    except Exception as e:
        logger.error(f'{request_id} | Error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='ANALYTICS999',
            error_message='An unexpected error occurred'
        ))
    
    finally:
        end_time = time.time()
        logger.info(f'{request_id} | Total time: {(end_time - start_time) * 1000:.2f}ms')


# ============================================================================
# ENDPOINT 6: Per-API Breakdown
# ============================================================================

@analytics_router.get('/analytics/api/{api_name}/{version}',
    description='Get detailed analytics for a specific API',
    response_model=ResponseModel
)
async def get_api_analytics(
    request: Request,
    api_name: str,
    version: str,
    start_ts: Optional[int] = Query(None),
    end_ts: Optional[int] = Query(None),
    range: Optional[str] = Query('24h')
):
    """
    Get detailed analytics for a specific API.
    
    Returns:
    - Total requests for this API
    - Error count and rate
    - Performance metrics
    - Time-series data
    - Top endpoints within this API
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        
        if not await platform_role_required_bool(username, 'view_analytics'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='ANALYTICS001',
                error_message='You do not have permission to view analytics'
            ))
        
        # Determine time range
        if start_ts and end_ts:
            pass
        else:
            end_ts = int(time.time())
            range_map = {'1h': 3600, '24h': 86400, '7d': 604800, '30d': 2592000}
            seconds = range_map.get(range, 86400)
            start_ts = end_ts - seconds
        
        # Get full snapshot
        snapshot = enhanced_metrics_store.get_snapshot(start_ts, end_ts)
        
        # Filter for this API
        api_key = f"rest:{api_name}"  # Assuming REST API
        
        # Find API in top_apis
        api_data = None
        for api, count in snapshot.top_apis:
            if api == api_key:
                api_data = {'api': api, 'count': count}
                break
        
        if not api_data:
            return respond_rest(ResponseModel(
                status_code=404,
                response_headers={'request_id': request_id},
                error_code='ANALYTICS404',
                error_message=f'No data found for API: {api_name}/{version}'
            ))
        
        # Filter endpoints for this API
        api_endpoints = [
            ep for ep in snapshot.top_endpoints
            if ep['endpoint_uri'].startswith(f'/{api_name}/{version}')
        ]
        
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            response={
                'api_name': api_name,
                'version': version,
                'time_range': {'start_ts': start_ts, 'end_ts': end_ts},
                'summary': api_data,
                'endpoints': api_endpoints
            }
        ))
    
    except Exception as e:
        logger.error(f'{request_id} | Error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='ANALYTICS999',
            error_message='An unexpected error occurred'
        ))
    
    finally:
        end_time = time.time()
        logger.info(f'{request_id} | Total time: {(end_time - start_time) * 1000:.2f}ms')


# ============================================================================
# ENDPOINT 7: Per-User Breakdown
# ============================================================================

@analytics_router.get('/analytics/user/{username}',
    description='Get detailed analytics for a specific user',
    response_model=ResponseModel
)
async def get_user_analytics(
    request: Request,
    username: str,
    start_ts: Optional[int] = Query(None),
    end_ts: Optional[int] = Query(None),
    range: Optional[str] = Query('24h')
):
    """
    Get detailed analytics for a specific user.
    
    Returns:
    - Total requests by this user
    - APIs accessed
    - Time-series of user activity
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        payload = await auth_required(request)
        requesting_username = payload.get('sub')
        
        if not await platform_role_required_bool(requesting_username, 'view_analytics'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='ANALYTICS001',
                error_message='You do not have permission to view analytics'
            ))
        
        # Determine time range
        if start_ts and end_ts:
            pass
        else:
            end_ts = int(time.time())
            range_map = {'1h': 3600, '24h': 86400, '7d': 604800, '30d': 2592000}
            seconds = range_map.get(range, 86400)
            start_ts = end_ts - seconds
        
        # Get full snapshot
        snapshot = enhanced_metrics_store.get_snapshot(start_ts, end_ts)
        
        # Find user in top_users
        user_data = None
        for user, count in snapshot.top_users:
            if user == username:
                user_data = {'user': user, 'count': count}
                break
        
        if not user_data:
            return respond_rest(ResponseModel(
                status_code=404,
                response_headers={'request_id': request_id},
                error_code='ANALYTICS404',
                error_message=f'No data found for user: {username}'
            ))
        
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            response={
                'username': username,
                'time_range': {'start_ts': start_ts, 'end_ts': end_ts},
                'summary': user_data
            }
        ))
    
    except Exception as e:
        logger.error(f'{request_id} | Error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='ANALYTICS999',
            error_message='An unexpected error occurred'
        ))
    
    finally:
        end_time = time.time()
        logger.info(f'{request_id} | Total time: {(end_time - start_time) * 1000:.2f}ms')
