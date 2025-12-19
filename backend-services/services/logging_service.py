"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import glob
import json
import logging
import os
import re
from datetime import datetime
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger('doorman.logging')


class LoggingService:
    def __init__(self):
        env_dir = os.getenv('LOGS_DIR')
        base_dir = os.path.dirname(os.path.abspath(__file__))
        backend_root = os.path.normpath(os.path.join(base_dir, '..'))

        # Build a prioritized list of candidate directories to search for log files
        candidates: list[str] = []
        if env_dir and str(env_dir).strip():
            candidates.append(os.path.abspath(env_dir))

        # Repo-default locations
        candidates.append(os.path.join(backend_root, 'platform-logs'))
        candidates.append(os.path.join(backend_root, 'logs'))

        # Container fallback where doorman.py may write if LOGS_DIR isn't writable
        candidates.append('/tmp/doorman-logs')

        # Dedupe while preserving order
        seen = set()
        self.log_directories = [c for c in candidates if not (c in seen or seen.add(c))]

        self.log_file_patterns = ['doorman.log*', 'doorman-trail.log*']
        self.max_logs_per_request = 1000

    async def get_logs(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        user: str | None = None,
        api: str | None = None,
        endpoint: str | None = None,
        request_id: str | None = None,
        method: str | None = None,
        ip_address: str | None = None,
        min_response_time: str | None = None,
        max_response_time: str | None = None,
        level: str | None = None,
        limit: int = 100,
        offset: int = 0,
        request_id_param: str = None,
    ) -> dict[str, Any]:
        """
        Retrieve and filter logs based on various criteria
        """
        try:
            # Prefer fast in-memory buffer if available and non-empty
            try:
                from utils.memory_log import memory_log_snapshot

                buffer_lines = memory_log_snapshot()
            except Exception:
                buffer_lines = []

            log_files: list[str] = []
            for d in self.log_directories:
                for pat in self.log_file_patterns:
                    log_files.extend(glob.glob(os.path.join(d, pat)))

            logs = []
            total_count = 0

            # Case A: Use in-memory buffer when it has content; it's fastest and covers both envs
            if buffer_lines:
                for line in reversed(buffer_lines):
                    log_entry = self._parse_log_line(line)
                    if log_entry and self._matches_filters(
                        log_entry,
                        {
                            'start_date': start_date,
                            'end_date': end_date,
                            'start_time': start_time,
                            'end_time': end_time,
                            'user': user,
                            'api': api,
                            'endpoint': endpoint,
                            'request_id': request_id,
                            'method': method,
                            'ip_address': ip_address,
                            'min_response_time': min_response_time,
                            'max_response_time': max_response_time,
                            'level': level,
                        },
                    ):
                        total_count += 1
                        if total_count > offset and len(logs) < limit:
                            logs.append(log_entry)
                        if len(logs) >= limit:
                            break
                logs.reverse()
            elif log_files:
                log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                # Cap file scanning to a few recent files for performance
                log_files = log_files[:3]

                for log_file in log_files:
                    if not os.path.exists(log_file):
                        continue

                    try:
                        with open(log_file, encoding='utf-8') as file:
                            for line in file:
                                log_entry = self._parse_log_line(line)
                                if log_entry and self._matches_filters(
                                    log_entry,
                                    {
                                        'start_date': start_date,
                                        'end_date': end_date,
                                        'start_time': start_time,
                                        'end_time': end_time,
                                        'user': user,
                                        'api': api,
                                        'endpoint': endpoint,
                                        'request_id': request_id,
                                        'method': method,
                                        'ip_address': ip_address,
                                        'min_response_time': min_response_time,
                                        'max_response_time': max_response_time,
                                        'level': level,
                                    },
                                ):
                                    total_count += 1
                                    if len(logs) < limit and total_count > offset:
                                        logs.append(log_entry)

                                    if len(logs) >= limit:
                                        break

                        if len(logs) >= limit:
                            break

                    except Exception as e:
                        logger.warning(f'Error reading log file {log_file}: {str(e)}')
                        continue
            else:
                # Nothing to read
                pass

            return {'logs': logs, 'total': total_count, 'has_more': total_count > offset + limit}

        except Exception as e:
            logger.error(f'Error retrieving logs: {str(e)}', exc_info=True)
            raise HTTPException(status_code=500, detail='Failed to retrieve logs')

    def get_available_log_files(self) -> list[str]:
        """
        Get list of available log files for debugging
        """
        log_files: list[str] = []
        for d in self.log_directories:
            for pat in self.log_file_patterns:
                log_files.extend(glob.glob(os.path.join(d, pat)))
        log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return log_files

    async def get_log_statistics(self, request_id: str = None) -> dict[str, Any]:
        """
        Get log statistics for dashboard
        """
        try:
            # Prefer in-memory stats if available
            try:
                from utils.memory_log import memory_log_snapshot

                buffer_lines = memory_log_snapshot()
            except Exception:
                buffer_lines = []

            log_files: list[str] = []
            for d in self.log_directories:
                for pat in self.log_file_patterns:
                    log_files.extend(glob.glob(os.path.join(d, pat)))

            stats = {
                'total_logs': 0,
                'error_count': 0,
                'warning_count': 0,
                'info_count': 0,
                'debug_count': 0,
                'response_times': [],
                'apis': {},
                'users': {},
                'endpoints': {},
            }
            if buffer_lines:
                for line in buffer_lines:
                    self._accumulate_stats_line(line, stats)
            elif log_files:
                for log_file in log_files:
                    if not os.path.exists(log_file):
                        continue

                    try:
                        with open(log_file, encoding='utf-8') as file:
                            for line in file:
                                self._accumulate_stats_line(line, stats)
                    except Exception as e:
                        logger.warning(f'Error reading log file {log_file} for statistics: {str(e)}')
                        continue
            else:
                try:
                    from utils.memory_log import memory_log_snapshot

                    for line in memory_log_snapshot():
                        self._accumulate_stats_line(line, stats)
                except Exception as e:
                    logger.warning(f'In-memory stats fallback unavailable: {e}')

            avg_response_time = (
                sum(stats['response_times']) / len(stats['response_times'])
                if stats['response_times']
                else 0
            )

            top_apis = sorted(stats['apis'].items(), key=lambda x: x[1], reverse=True)[:10]
            top_users = sorted(stats['users'].items(), key=lambda x: x[1], reverse=True)[:10]
            top_endpoints = sorted(stats['endpoints'].items(), key=lambda x: x[1], reverse=True)[
                :10
            ]

            return {
                'total_logs': stats['total_logs'],
                'error_count': stats['error_count'],
                'warning_count': stats['warning_count'],
                'info_count': stats['info_count'],
                'debug_count': stats['debug_count'],
                'avg_response_time': round(avg_response_time, 2),
                'top_apis': [{'name': api, 'count': count} for api, count in top_apis],
                'top_users': [{'name': user, 'count': count} for user, count in top_users],
                'top_endpoints': [
                    {'name': endpoint, 'count': count} for endpoint, count in top_endpoints
                ],
            }

        except Exception as e:
            logger.error(f'Error retrieving log statistics: {str(e)}')
            raise HTTPException(status_code=500, detail='Failed to retrieve log statistics')

    async def export_logs(
        self,
        format: str = 'json',
        start_date: str | None = None,
        end_date: str | None = None,
        filters: dict[str, Any] = None,
        request_id: str = None,
    ) -> dict[str, Any]:
        """
        Export logs in various formats
        """
        try:
            logs_data = await self.get_logs(
                start_date=start_date, end_date=end_date, limit=10000, **filters if filters else {}
            )

            logs = logs_data['logs']

            if format.lower() == 'json':
                return {
                    'format': 'json',
                    'data': json.dumps(logs, indent=2, default=str),
                    'filename': f'logs_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
                }
            elif format.lower() == 'csv':
                if not logs:
                    return {
                        'format': 'csv',
                        'data': 'timestamp,level,message,source,user,api,endpoint,method,status_code,response_time,ip_address,protocol,request_id,group,role\n',
                        'filename': f'logs_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                    }

                csv_data = 'timestamp,level,message,source,user,api,endpoint,method,status_code,response_time,ip_address,protocol,request_id,group,role\n'
                for log in logs:
                    csv_data += f'{log.get("timestamp", "")},{log.get("level", "")},{log.get("message", "").replace(",", ";")},{log.get("source", "")},{log.get("user", "")},{log.get("api", "")},{log.get("endpoint", "")},{log.get("method", "")},{log.get("status_code", "")},{log.get("response_time", "")},{log.get("ip_address", "")},{log.get("protocol", "")},{log.get("request_id", "")},{log.get("group", "")},{log.get("role", "")}\n'

                return {
                    'format': 'csv',
                    'data': csv_data,
                    'filename': f'logs_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                }
            else:
                raise HTTPException(status_code=400, detail='Unsupported export format')

        except Exception as e:
            logger.error(f'Error exporting logs: {str(e)}')
            raise HTTPException(status_code=500, detail='Failed to export logs')

    def _parse_log_line(self, line: str) -> dict[str, Any] | None:
        """
        Parse a log line and extract structured data
        Format: timestamp - logger_name - level - request_id | message
        """
        try:
            s = line.strip()
            if s.startswith('{') and s.endswith('}'):
                try:
                    rec = json.loads(s)
                    timestamp_str = rec.get('time') or rec.get('timestamp')
                    try:
                        timestamp = timestamp_str or datetime.utcnow().isoformat()
                    except Exception:
                        timestamp = datetime.utcnow().isoformat()
                    message = rec.get('message', '')
                    name = rec.get('name', '')
                    level = rec.get('level', '')
                    structured = self._extract_structured_data(message)
                    return {
                        'timestamp': timestamp
                        if isinstance(timestamp, str)
                        else timestamp.isoformat(),
                        'level': level,
                        'message': message,
                        'source': name,
                        **structured,
                    }
                except Exception:
                    pass

            parts = s.split(' - ', 3)
            if len(parts) < 4:
                return None
            timestamp_str, name, level, full_message = parts
            try:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
            except ValueError:
                try:
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    timestamp = datetime.utcnow()
            message_parts = full_message.split(' | ', 1)
            request_id = message_parts[0] if len(message_parts) > 1 else None
            message = message_parts[1] if len(message_parts) > 1 else full_message
            structured_data = self._extract_structured_data(message)
            if request_id:
                structured_data['request_id'] = request_id
            return {
                'timestamp': timestamp.isoformat(),
                'level': level,
                'message': message,
                'source': name,
                **structured_data,
            }

        except Exception as e:
            logger.debug(f'Failed to parse log line: {str(e)}', exc_info=True)
            return None

    def _extract_structured_data(self, message: str) -> dict[str, Any]:
        """
        Extract structured data from log message
        """
        data = {}

        request_id_match = re.search(r'(\w{8}-\w{4}-\w{4}-\w{4}-\w{12})', message)
        if request_id_match:
            data['request_id'] = request_id_match.group(1)

        username_match = re.search(r'Username: (\w+)', message)
        if username_match:
            data['user'] = username_match.group(1)

        ip_kv_match = re.search(r'(?:effective_ip|client_ip)=([A-Fa-f0-9:\.]+)', message)
        if ip_kv_match:
            data['ip_address'] = ip_kv_match.group(1)
        else:
            ip_from_match = re.search(r'From:\s+(.+?)$', message)
            if ip_from_match:
                hostport = ip_from_match.group(1)
                if hostport.count(':') > 1:
                    hp = hostport.rsplit(':', 1)
                    data['ip_address'] = hp[0]
                else:
                    hp = hostport.split(':')
                    if hp:
                        data['ip_address'] = hp[0]

        endpoint_match = re.search(r'Endpoint: (\w+) (.+)', message)
        if endpoint_match:
            data['method'] = endpoint_match.group(1)
            data['endpoint'] = endpoint_match.group(2)

        response_time_match = re.search(r'Total time: ([\d\.]+)ms', message)
        if response_time_match:
            data['response_time'] = response_time_match.group(1)

        if 'Status check failed' in message or 'status_code' in message.lower():
            status_match = re.search(r'status_code[:\s]+(\d+)', message, re.IGNORECASE)
            if status_match:
                data['status_code'] = status_match.group(1)

        return data

    def _accumulate_stats_line(self, line: str, stats: dict[str, Any]) -> None:
        log_entry = self._parse_log_line(line)
        if not log_entry:
            return
        stats['total_logs'] += 1

        level = log_entry.get('level', '').lower()
        if level == 'error':
            stats['error_count'] += 1
        elif level == 'warning':
            stats['warning_count'] += 1
        elif level == 'info':
            stats['info_count'] += 1
        elif level == 'debug':
            stats['debug_count'] += 1

        if log_entry.get('response_time'):
            try:
                stats['response_times'].append(float(log_entry['response_time']))
            except (ValueError, TypeError):
                pass

        if log_entry.get('api'):
            stats['apis'][log_entry['api']] = stats['apis'].get(log_entry['api'], 0) + 1

        if log_entry.get('user'):
            stats['users'][log_entry['user']] = stats['users'].get(log_entry['user'], 0) + 1

        if log_entry.get('endpoint'):
            stats['endpoints'][log_entry['endpoint']] = (
                stats['endpoints'].get(log_entry['endpoint'], 0) + 1
            )

    def _matches_filters(self, log_entry: dict[str, Any], filters: dict[str, Any]) -> bool:
        """
        Check if log entry matches all applied filters
        """
        try:
            timestamp_str = log_entry.get('timestamp', '')
            if not timestamp_str:
                return False

            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError:
                logger.debug(f'Failed to parse timestamp: {timestamp_str}')
                return False

            if filters.get('start_date') or filters.get('start_time'):
                start_datetime = None
                if filters.get('start_date'):
                    start_date = datetime.strptime(filters['start_date'], '%Y-%m-%d')
                    if filters.get('start_time'):
                        start_time = datetime.strptime(filters['start_time'], '%H:%M').time()
                        start_datetime = datetime.combine(start_date.date(), start_time)
                    else:
                        start_datetime = start_date
                else:
                    start_time = datetime.strptime(filters['start_time'], '%H:%M').time()
                    start_datetime = datetime.combine(timestamp.date(), start_time)

                if timestamp < start_datetime:
                    return False

            if filters.get('end_date') or filters.get('end_time'):
                end_datetime = None
                if filters.get('end_date'):
                    end_date = datetime.strptime(filters['end_date'], '%Y-%m-%d')
                    if filters.get('end_time'):
                        end_time = datetime.strptime(filters['end_time'], '%H:%M').time()
                        end_datetime = datetime.combine(end_date.date(), end_time)
                    else:
                        end_datetime = datetime.combine(end_date.date(), datetime.max.time())
                else:
                    end_time = datetime.strptime(filters['end_time'], '%H:%M').time()
                    end_datetime = datetime.combine(timestamp.date(), end_time)

                if timestamp > end_datetime:
                    return False

            for field in ['user', 'api', 'endpoint', 'request_id', 'method', 'ip_address', 'level']:
                if filters.get(field) and filters[field].strip():
                    filter_value = filters[field].strip().lower()
                    log_value = str(log_entry.get(field, '')).lower()

                    if not log_value:
                        logger.debug(
                            f"Filter '{field}' = '{filter_value}' but log has no value for '{field}'"
                        )
                        return False

                    if filter_value not in log_value:
                        logger.debug(
                            f"Filter '{field}' = '{filter_value}' not found in log value '{log_value}'"
                        )
                        return False
                    else:
                        logger.debug(
                            f"Filter '{field}' = '{filter_value}' matches log value '{log_value}'"
                        )

            if filters.get('status_code') and filters['status_code'].strip():
                try:
                    filter_status = filters['status_code'].strip()
                    log_status = str(log_entry.get('status_code', ''))

                    if not log_status:
                        return False
                    if log_status != filter_status:
                        return False
                except (ValueError, TypeError):
                    return False

            if filters.get('min_response_time') and filters['min_response_time'].strip():
                try:
                    min_time = float(filters['min_response_time'].strip())
                    log_time = float(log_entry.get('response_time', 0))
                    if log_time < min_time:
                        return False
                except (ValueError, TypeError):
                    return False

            if filters.get('max_response_time') and filters['max_response_time'].strip():
                try:
                    max_time = float(filters['max_response_time'].strip())
                    log_time = float(log_entry.get('response_time', 0))
                    if log_time > max_time:
                        return False
                except (ValueError, TypeError):
                    return False

            applied_filters = [f'{k}={v}' for k, v in filters.items() if v and str(v).strip()]
            if applied_filters:
                logger.debug(f'Log entry passed all filters: {", ".join(applied_filters)}')
            return True

        except Exception as e:
            logger.debug(f'Error applying filters: {str(e)}', exc_info=True)
            return False
