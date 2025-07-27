"""
Test file for logging service
"""

import pytest
import os
import tempfile
from datetime import datetime
from services.logging_service import LoggingService

class TestLoggingService:
    @pytest.fixture
    def logging_service(self):
        return LoggingService()
    
    @pytest.fixture
    def sample_log_file(self):
        # Create a temporary log file with sample data
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            f.write("2024-01-01 12:00:00,123 - doorman.gateway - INFO - 123e4567-e89b-12d3-a456-426614174000 | Username: testuser | From: 192.168.1.1:8080\n")
            f.write("2024-01-01 12:00:01,456 - doorman.gateway - INFO - 123e4567-e89b-12d3-a456-426614174000 | Endpoint: GET /api/test/v1/users\n")
            f.write("2024-01-01 12:00:02,789 - doorman.gateway - INFO - 123e4567-e89b-12d3-a456-426614174000 | Total time: 150.5ms\n")
            f.write("2024-01-01 12:01:00,000 - doorman.gateway - ERROR - 456e7890-e89b-12d3-a456-426614174000 | Username: testuser2 | From: 192.168.1.2:8080\n")
            f.write("2024-01-01 12:01:01,000 - doorman.gateway - ERROR - 456e7890-e89b-12d3-a456-426614174000 | Endpoint: POST /api/test/v1/users\n")
            f.write("2024-01-01 12:01:02,000 - doorman.gateway - ERROR - 456e7890-e89b-12d3-a456-426614174000 | Total time: 500.0ms\n")
            temp_file = f.name
        
        yield temp_file
        
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)
    
    @pytest.mark.asyncio
    async def test_get_logs_no_file(self, logging_service):
        """Test getting logs when log file doesn't exist"""
        result = await logging_service.get_logs()
        assert result["logs"] == []
        assert result["total"] == 0
        assert result["has_more"] == False
    
    @pytest.mark.asyncio
    async def test_get_logs_with_file(self, logging_service, sample_log_file):
        """Test getting logs from existing file"""
        # Temporarily set the log file path
        original_path = logging_service.log_file_path
        logging_service.log_file_path = sample_log_file
        
        try:
            result = await logging_service.get_logs()
            assert len(result["logs"]) > 0
            assert result["total"] > 0
            assert "timestamp" in result["logs"][0]
            assert "level" in result["logs"][0]
            assert "message" in result["logs"][0]
        finally:
            logging_service.log_file_path = original_path
    
    @pytest.mark.asyncio
    async def test_get_logs_with_filters(self, logging_service, sample_log_file):
        """Test getting logs with filters"""
        original_path = logging_service.log_file_path
        logging_service.log_file_path = sample_log_file
        
        try:
            # Filter by level
            result = await logging_service.get_logs(level="ERROR")
            assert all(log["level"] == "ERROR" for log in result["logs"])
            
            # Filter by user
            result = await logging_service.get_logs(user="testuser")
            assert all("testuser" in log.get("user", "") for log in result["logs"])
        finally:
            logging_service.log_file_path = original_path
    
    @pytest.mark.asyncio
    async def test_get_log_statistics(self, logging_service, sample_log_file):
        """Test getting log statistics"""
        original_path = logging_service.log_file_path
        logging_service.log_file_path = sample_log_file
        
        try:
            stats = await logging_service.get_log_statistics()
            assert "total_logs" in stats
            assert "error_count" in stats
            assert "warning_count" in stats
            assert "info_count" in stats
            assert "debug_count" in stats
            assert "avg_response_time" in stats
            assert "top_apis" in stats
            assert "top_users" in stats
            assert "top_endpoints" in stats
        finally:
            logging_service.log_file_path = original_path
    
    @pytest.mark.asyncio
    async def test_export_logs_json(self, logging_service, sample_log_file):
        """Test exporting logs as JSON"""
        original_path = logging_service.log_file_path
        logging_service.log_file_path = sample_log_file
        
        try:
            result = await logging_service.export_logs(format="json")
            assert result["format"] == "json"
            assert "data" in result
            assert "filename" in result
            assert result["filename"].endswith(".json")
        finally:
            logging_service.log_file_path = original_path
    
    @pytest.mark.asyncio
    async def test_export_logs_csv(self, logging_service, sample_log_file):
        """Test exporting logs as CSV"""
        original_path = logging_service.log_file_path
        logging_service.log_file_path = sample_log_file
        
        try:
            result = await logging_service.export_logs(format="csv")
            assert result["format"] == "csv"
            assert "data" in result
            assert "filename" in result
            assert result["filename"].endswith(".csv")
            assert "timestamp,level,message" in result["data"]
        finally:
            logging_service.log_file_path = original_path
    
    def test_parse_log_line(self, logging_service):
        """Test parsing log line"""
        log_line = "2024-01-01 12:00:00,123 - doorman.gateway - INFO - 123e4567-e89b-12d3-a456-426614174000 | Username: testuser | From: 192.168.1.1:8080"
        result = logging_service._parse_log_line(log_line)
        
        assert result is not None
        assert result["level"] == "INFO"
        assert result["source"] == "doorman.gateway"
        assert "testuser" in result["message"]
    
    def test_extract_structured_data(self, logging_service):
        """Test extracting structured data from log message"""
        message = "123e4567-e89b-12d3-a456-426614174000 | Username: testuser | From: 192.168.1.1:8080 | Endpoint: GET /api/test/v1/users | Total time: 150.5ms"
        result = logging_service._extract_structured_data(message)
        
        assert result["request_id"] == "123e4567-e89b-12d3-a456-426614174000"
        assert result["user"] == "testuser"
        assert result["ip_address"] == "192.168.1.1"
        assert result["method"] == "GET"
        assert result["endpoint"] == "/api/test/v1/users"
        assert result["response_time"] == "150.5"
        assert result["api"] == "test" 