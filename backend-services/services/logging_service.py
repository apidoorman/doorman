"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

import logging
import os
import json
import glob
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
import re

logger = logging.getLogger("doorman.logging")

class LoggingService:
    def __init__(self):
        self.log_directory = "logs"
        self.log_file_pattern = "doorman.log*"  # Support rotated log files (doorman.log, doorman.log.1, etc.)
        self.max_logs_per_request = 1000
        
    async def get_logs(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        user: Optional[str] = None,
        endpoint: Optional[str] = None,
        request_id: Optional[str] = None,
        method: Optional[str] = None,
        ip_address: Optional[str] = None,
        min_response_time: Optional[str] = None,
        max_response_time: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        request_id_param: str = None
    ) -> Dict[str, Any]:
        """
        Retrieve and filter logs based on various criteria
        """
        try:
            # Find all log files matching the pattern
            log_files = glob.glob(os.path.join(self.log_directory, self.log_file_pattern))
            
            # Sort log files by modification time (newest first)
            # This ensures we read the most recent log files first
            log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            if not log_files:
                return {
                    "logs": [],
                    "total": 0,
                    "has_more": False
                }
            
            logs = []
            total_count = 0
            
            # Read from all log files
            logger.debug(f"Found {len(log_files)} log files: {log_files}")
            for log_file in log_files:
                if not os.path.exists(log_file):
                    continue
                    
                try:
                    with open(log_file, 'r', encoding='utf-8') as file:
                        for line in file:
                            log_entry = self._parse_log_line(line)
                            if log_entry and self._matches_filters(log_entry, {
                                'start_date': start_date,
                                'end_date': end_date,
                                'start_time': start_time,
                                'end_time': end_time,
                                'user': user,
                                'endpoint': endpoint,
                                'request_id': request_id,
                                'method': method,
                                'ip_address': ip_address,
                                'min_response_time': min_response_time,
                                'max_response_time': max_response_time,
                                'level': level
                            }):
                                total_count += 1
                                if len(logs) < limit and total_count > offset:
                                    logs.append(log_entry)
                                    
                                # Stop if we've reached the limit
                                if len(logs) >= limit:
                                    break
                                    
                    # Stop if we've reached the limit
                    if len(logs) >= limit:
                        break
                        
                except Exception as e:
                    logger.warning(f"Error reading log file {log_file}: {str(e)}")
                    continue
            
            return {
                "logs": logs,
                "total": total_count,
                "has_more": total_count > offset + limit
            }
            
        except Exception as e:
            logger.error(f"Error retrieving logs: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to retrieve logs: {str(e)}")
    
    def get_available_log_files(self) -> List[str]:
        """
        Get list of available log files for debugging
        """
        log_files = glob.glob(os.path.join(self.log_directory, self.log_file_pattern))
        log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return log_files
    
    async def get_log_statistics(self, request_id: str = None) -> Dict[str, Any]:
        """
        Get log statistics for dashboard
        """
        try:
            # Find all log files matching the pattern
            log_files = glob.glob(os.path.join(self.log_directory, self.log_file_pattern))
            
            if not log_files:
                return {
                    "total_logs": 0,
                    "error_count": 0,
                    "warning_count": 0,
                    "info_count": 0,
                    "debug_count": 0,
                    "avg_response_time": 0,
                    "top_apis": [],
                    "top_users": [],
                    "top_endpoints": []
                }
            
            stats = {
                "total_logs": 0,
                "error_count": 0,
                "warning_count": 0,
                "info_count": 0,
                "debug_count": 0,
                "response_times": [],
                "apis": {},
                "users": {},
                "endpoints": {}
            }
            
            # Read from all log files
            for log_file in log_files:
                if not os.path.exists(log_file):
                    continue
                    
                try:
                    with open(log_file, 'r', encoding='utf-8') as file:
                        for line in file:
                            log_entry = self._parse_log_line(line)
                            if log_entry:
                                stats["total_logs"] += 1
                                
                                # Count by level
                                level = log_entry.get('level', '').lower()
                                if level == 'error':
                                    stats["error_count"] += 1
                                elif level == 'warning':
                                    stats["warning_count"] += 1
                                elif level == 'info':
                                    stats["info_count"] += 1
                                elif level == 'debug':
                                    stats["debug_count"] += 1
                                
                                # Collect response times
                                if log_entry.get('response_time'):
                                    try:
                                        stats["response_times"].append(float(log_entry['response_time']))
                                    except (ValueError, TypeError):
                                        pass
                                
                                # Count APIs
                                if log_entry.get('api'):
                                    stats["apis"][log_entry['api']] = stats["apis"].get(log_entry['api'], 0) + 1
                                
                                # Count users
                                if log_entry.get('user'):
                                    stats["users"][log_entry['user']] = stats["users"].get(log_entry['user'], 0) + 1
                                
                                # Count endpoints
                                if log_entry.get('endpoint'):
                                    stats["endpoints"][log_entry['endpoint']] = stats["endpoints"].get(log_entry['endpoint'], 0) + 1
                                    
                except Exception as e:
                    logger.warning(f"Error reading log file {log_file} for statistics: {str(e)}")
                    continue
            
            # Calculate averages and top items
            avg_response_time = sum(stats["response_times"]) / len(stats["response_times"]) if stats["response_times"] else 0
            
            top_apis = sorted(stats["apis"].items(), key=lambda x: x[1], reverse=True)[:10]
            top_users = sorted(stats["users"].items(), key=lambda x: x[1], reverse=True)[:10]
            top_endpoints = sorted(stats["endpoints"].items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "total_logs": stats["total_logs"],
                "error_count": stats["error_count"],
                "warning_count": stats["warning_count"],
                "info_count": stats["info_count"],
                "debug_count": stats["debug_count"],
                "avg_response_time": round(avg_response_time, 2),
                "top_apis": [{"name": api, "count": count} for api, count in top_apis],
                "top_users": [{"name": user, "count": count} for user, count in top_users],
                "top_endpoints": [{"name": endpoint, "count": count} for endpoint, count in top_endpoints]
            }
            
        except Exception as e:
            logger.error(f"Error retrieving log statistics: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to retrieve log statistics")
    
    async def export_logs(
        self,
        format: str = "json",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        filters: Dict[str, Any] = None,
        request_id: str = None
    ) -> Dict[str, Any]:
        """
        Export logs in various formats
        """
        try:
            # Get filtered logs
            logs_data = await self.get_logs(
                start_date=start_date,
                end_date=end_date,
                limit=10000,  # Higher limit for exports
                **filters if filters else {}
            )
            
            logs = logs_data["logs"]
            
            if format.lower() == "json":
                return {
                    "format": "json",
                    "data": json.dumps(logs, indent=2, default=str),
                    "filename": f"logs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                }
            elif format.lower() == "csv":
                if not logs:
                    return {
                        "format": "csv",
                        "data": "timestamp,level,message,source,user,api,endpoint,method,status_code,response_time,ip_address,protocol,request_id,group,role\n",
                        "filename": f"logs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    }
                
                csv_data = "timestamp,level,message,source,user,api,endpoint,method,status_code,response_time,ip_address,protocol,request_id,group,role\n"
                for log in logs:
                    csv_data += f"{log.get('timestamp', '')},{log.get('level', '')},{log.get('message', '').replace(',', ';')},{log.get('source', '')},{log.get('user', '')},{log.get('api', '')},{log.get('endpoint', '')},{log.get('method', '')},{log.get('status_code', '')},{log.get('response_time', '')},{log.get('ip_address', '')},{log.get('protocol', '')},{log.get('request_id', '')},{log.get('group', '')},{log.get('role', '')}\n"
                
                return {
                    "format": "csv",
                    "data": csv_data,
                    "filename": f"logs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                }
            else:
                raise HTTPException(status_code=400, detail="Unsupported export format")
                
        except Exception as e:
            logger.error(f"Error exporting logs: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to export logs")
    
    def _parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a log line and extract structured data
        Format: timestamp - logger_name - level - request_id | message
        """
        try:
            # Basic log format: timestamp - name - level - message
            parts = line.strip().split(' - ', 3)
            if len(parts) < 4:
                return None
            
            timestamp_str, name, level, full_message = parts
            
            # Parse timestamp
            try:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
            except ValueError:
                try:
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    timestamp = datetime.now()
            
            # Extract request ID and message from the full message
            # Format: request_id | message
            message_parts = full_message.split(' | ', 1)
            request_id = message_parts[0] if len(message_parts) > 1 else None
            message = message_parts[1] if len(message_parts) > 1 else full_message
            
            # Extract structured data from message
            structured_data = self._extract_structured_data(message)
            
            # Add request_id to structured data if found
            if request_id:
                structured_data['request_id'] = request_id
            
            return {
                "timestamp": timestamp.isoformat(),
                "level": level,
                "message": message,
                "source": name,
                **structured_data
            }
            
        except Exception as e:
            logger.debug(f"Failed to parse log line: {str(e)}", exc_info=True)
            return None
    
    def _extract_structured_data(self, message: str) -> Dict[str, Any]:
        """
        Extract structured data from log message
        """
        data = {}
        
        # Extract request ID (UUID format)
        request_id_match = re.search(r'(\w{8}-\w{4}-\w{4}-\w{4}-\w{12})', message)
        if request_id_match:
            data['request_id'] = request_id_match.group(1)
        
        # Extract username
        username_match = re.search(r'Username: (\w+)', message)
        if username_match:
            data['user'] = username_match.group(1)
        
        # Extract IP address
        ip_match = re.search(r'From: ([\d\.]+):(\d+)', message)
        if ip_match:
            data['ip_address'] = ip_match.group(1)
        
        # Extract endpoint
        endpoint_match = re.search(r'Endpoint: (\w+) (.*)', message)
        if endpoint_match:
            data['method'] = endpoint_match.group(1)
            data['endpoint'] = endpoint_match.group(2)
        
        # Extract response time
        response_time_match = re.search(r'Total time: ([\d\.]+)ms', message)
        if response_time_match:
            data['response_time'] = response_time_match.group(1)
        
        # Extract status codes from error messages (only for actual errors)
        if 'Status check failed' in message or 'status_code' in message.lower():
            status_match = re.search(r'status_code[:\s]+(\d+)', message, re.IGNORECASE)
            if status_match:
                data['status_code'] = status_match.group(1)
        
        return data
    
    def _matches_filters(self, log_entry: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """
        Check if log entry matches all applied filters
        """
        try:
            # Handle timestamp parsing more robustly
            timestamp_str = log_entry.get('timestamp', '')
            if not timestamp_str:
                return False
                
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError:
                logger.debug(f"Failed to parse timestamp: {timestamp_str}")
                return False
            
            # Date filters - combine date and time for more accurate filtering
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
            
            # String filters - make them case-insensitive and more flexible
            for field in ['user', 'endpoint', 'request_id', 'method', 'ip_address', 'level']:
                if filters.get(field) and filters[field].strip():
                    filter_value = filters[field].strip().lower()
                    log_value = str(log_entry.get(field, '')).lower()
                    
                    # If log value is empty, it doesn't match the filter
                    if not log_value:
                        logger.debug(f"Filter '{field}' = '{filter_value}' but log has no value for '{field}'")
                        return False
                        
                    # Check if filter value is contained in log value
                    if filter_value not in log_value:
                        logger.debug(f"Filter '{field}' = '{filter_value}' not found in log value '{log_value}'")
                        return False
                    else:
                        logger.debug(f"Filter '{field}' = '{filter_value}' matches log value '{log_value}'")
            
            # Status code filter
            if filters.get('status_code') and filters['status_code'].strip():
                try:
                    filter_status = filters['status_code'].strip()
                    log_status = str(log_entry.get('status_code', ''))
                    # If log has no status code, it doesn't match the filter
                    if not log_status:
                        return False
                    if log_status != filter_status:
                        return False
                except (ValueError, TypeError):
                    return False
            
            # Response time filters
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
            
            # Log successful filter match
            applied_filters = [f"{k}={v}" for k, v in filters.items() if v and str(v).strip()]
            if applied_filters:
                logger.debug(f"Log entry passed all filters: {', '.join(applied_filters)}")
            return True
            
        except Exception as e:
            logger.debug(f"Error applying filters: {str(e)}", exc_info=True)
            return False 