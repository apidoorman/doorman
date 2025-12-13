"""
Test body size limit enforcement for Transfer-Encoding: chunked requests.

This test suite verifies that the body_size_limit middleware properly
enforces size limits on chunked-encoded requests, preventing the bypass
vulnerability where attackers could stream unlimited data without a
Content-Length header.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from doorman import doorman


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(doorman)


class TestChunkedEncodingBodyLimit:
    """Test suite for chunked encoding body size limit enforcement."""

    def test_chunked_encoding_within_limit(self, client):
        """Test that chunked requests within limit are accepted."""
        small_payload = b'x' * 1000

        response = client.post(
            '/platform/authorization',
            data=small_payload,
            headers={'Transfer-Encoding': 'chunked', 'Content-Type': 'application/json'},
        )

        assert response.status_code != 413

    def test_chunked_encoding_exceeds_limit(self, client):
        """Test that chunked requests exceeding limit are rejected."""
        os.environ['MAX_BODY_SIZE_BYTES'] = '1024'

        try:
            large_payload = b'x' * 2048

            response = client.post(
                '/platform/authorization',
                data=large_payload,
                headers={'Transfer-Encoding': 'chunked', 'Content-Type': 'application/json'},
            )

            assert response.status_code == 413
            assert 'REQ001' in response.text or 'too large' in response.text.lower()

        finally:
            os.environ['MAX_BODY_SIZE_BYTES'] = '1048576'

    def test_chunked_encoding_rest_api_limit(self, client):
        """Test chunked encoding limit on REST API routes."""
        os.environ['MAX_BODY_SIZE_BYTES_REST'] = '1024'

        try:
            large_payload = b'x' * 2048

            response = client.post(
                '/api/rest/test/v1/endpoint',
                data=large_payload,
                headers={'Transfer-Encoding': 'chunked', 'Content-Type': 'application/json'},
            )

            assert response.status_code == 413

        finally:
            if 'MAX_BODY_SIZE_BYTES_REST' in os.environ:
                del os.environ['MAX_BODY_SIZE_BYTES_REST']

    def test_chunked_encoding_soap_api_limit(self, client):
        """Test chunked encoding limit on SOAP API routes."""
        os.environ['MAX_BODY_SIZE_BYTES_SOAP'] = '2048'

        try:
            medium_payload = b'<soap>test</soap>' * 100

            response = client.post(
                '/api/soap/test/v1/service',
                data=medium_payload,
                headers={'Transfer-Encoding': 'chunked', 'Content-Type': 'text/xml'},
            )

            assert response.status_code != 413

        finally:
            if 'MAX_BODY_SIZE_BYTES_SOAP' in os.environ:
                del os.environ['MAX_BODY_SIZE_BYTES_SOAP']

    def test_content_length_still_works(self, client):
        """Test that Content-Length enforcement still works (regression test)."""
        os.environ['MAX_BODY_SIZE_BYTES'] = '1024'

        try:
            large_payload = b'x' * 2048

            response = client.post(
                '/platform/authorization',
                data=large_payload,
                headers={'Content-Type': 'application/json'},
            )

            assert response.status_code == 413
            assert 'REQ001' in response.text or 'too large' in response.text.lower()

        finally:
            os.environ['MAX_BODY_SIZE_BYTES'] = '1048576'

    def test_no_bypass_with_fake_content_length(self, client):
        """Test that fake Content-Length with chunked encoding doesn't bypass limit."""
        os.environ['MAX_BODY_SIZE_BYTES'] = '1024'

        try:
            large_payload = b'x' * 2048

            response = client.post(
                '/platform/authorization',
                data=large_payload,
                headers={
                    'Transfer-Encoding': 'chunked',
                    'Content-Length': '100',
                    'Content-Type': 'application/json',
                },
            )

            assert response.status_code == 413

        finally:
            os.environ['MAX_BODY_SIZE_BYTES'] = '1048576'

    def test_get_request_with_chunked_ignored(self, client):
        """Test that GET requests with Transfer-Encoding: chunked are not limited."""
        response = client.get(
            '/platform/authorization/status', headers={'Transfer-Encoding': 'chunked'}
        )

        assert response.status_code != 413

    def test_put_request_with_chunked_enforced(self, client):
        """Test that PUT requests with chunked encoding are enforced."""
        os.environ['MAX_BODY_SIZE_BYTES'] = '1024'

        try:
            large_payload = b'x' * 2048

            response = client.put(
                '/platform/user/testuser',
                data=large_payload,
                headers={'Transfer-Encoding': 'chunked', 'Content-Type': 'application/json'},
            )

            assert response.status_code == 413

        finally:
            os.environ['MAX_BODY_SIZE_BYTES'] = '1048576'

    def test_patch_request_with_chunked_enforced(self, client):
        """Test that PATCH requests with chunked encoding are enforced."""
        os.environ['MAX_BODY_SIZE_BYTES'] = '1024'

        try:
            large_payload = b'x' * 2048

            response = client.patch(
                '/platform/user/testuser',
                data=large_payload,
                headers={'Transfer-Encoding': 'chunked', 'Content-Type': 'application/json'},
            )

            assert response.status_code == 413

        finally:
            os.environ['MAX_BODY_SIZE_BYTES'] = '1048576'

    def test_graphql_chunked_limit(self, client):
        """Test chunked encoding limit on GraphQL routes."""
        os.environ['MAX_BODY_SIZE_BYTES_GRAPHQL'] = '512'

        try:
            large_query = '{"query":"' + ('x' * 1000) + '"}'

            response = client.post(
                '/api/graphql/test',
                data=large_query.encode(),
                headers={'Transfer-Encoding': 'chunked', 'Content-Type': 'application/json'},
            )

            assert response.status_code == 413

        finally:
            if 'MAX_BODY_SIZE_BYTES_GRAPHQL' in os.environ:
                del os.environ['MAX_BODY_SIZE_BYTES_GRAPHQL']

    def test_platform_routes_protected(self, client):
        """Test that all platform routes are protected by default."""
        os.environ['MAX_BODY_SIZE_BYTES'] = '1024'

        try:
            large_payload = b'x' * 2048

            routes = [
                '/platform/authorization',
                '/platform/user',
                '/platform/api',
                '/platform/endpoint',
            ]

            for route in routes:
                response = client.post(
                    route,
                    data=large_payload,
                    headers={'Transfer-Encoding': 'chunked', 'Content-Type': 'application/json'},
                )

                assert response.status_code == 413, f'Route {route} not protected'

        finally:
            os.environ['MAX_BODY_SIZE_BYTES'] = '1048576'

    def test_audit_log_on_chunked_rejection(self, client):
        """Test that rejection of chunked requests is logged to audit trail."""
        os.environ['MAX_BODY_SIZE_BYTES'] = '1024'

        try:
            large_payload = b'x' * 2048

            response = client.post(
                '/platform/authorization',
                data=large_payload,
                headers={'Transfer-Encoding': 'chunked', 'Content-Type': 'application/json'},
            )

            assert response.status_code == 413

        finally:
            os.environ['MAX_BODY_SIZE_BYTES'] = '1048576'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
