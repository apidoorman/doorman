import time
import socket
import requests
import pytest

from config import ENABLE_GRPC

def _find_port() -> int:
    s = socket.socket()
    s.bind(('0.0.0.0', 0))
    p = s.getsockname()[1]
    s.close()
    return p

def _get_host_from_container() -> str:
    """Get the hostname to use when referring to the host machine from a Docker container."""
    import os
    import platform

    # Check if we're running against a dockerized doorman
    base_url = os.getenv('DOORMAN_BASE_URL', 'http://localhost:3001')
    if 'localhost' in base_url or '127.0.0.1' in base_url:
        # Doorman is running on the host (not in Docker), use localhost
        return '127.0.0.1'

    # Running against remote/Docker - need to use host reference
    system = platform.system()
    if system == 'Darwin' or system == 'Windows':
        # Docker Desktop on Mac/Windows
        return 'host.docker.internal'
    else:
        # Linux - use host's IP on docker0 bridge (usually 172.17.0.1)
        return '172.17.0.1'

@pytest.mark.skipif(not ENABLE_GRPC, reason='gRPC disabled')
def test_public_grpc_with_proto_upload(client):
    try:
        import grpc
        from grpc_tools import protoc
        from concurrent import futures
        import tempfile, pathlib, importlib, sys
    except Exception as e:
        pytest.skip(f'Missing gRPC deps: {e}')

    PROTO = '''
syntax = "proto3";
package {pkg};
service Resource {
  rpc Create (CreateRequest) returns (CreateReply) {}
  rpc Read (ReadRequest) returns (ReadReply) {}
  rpc Update (UpdateRequest) returns (UpdateReply) {}
  rpc Delete (DeleteRequest) returns (DeleteReply) {}
}
message CreateRequest { string name = 1; }
message CreateReply { string message = 1; }
message ReadRequest { int32 id = 1; }
message ReadReply { string message = 1; }
message UpdateRequest { int32 id = 1; string name = 2; }
message UpdateReply { string message = 1; }
message DeleteRequest { int32 id = 1; }
message DeleteReply { bool ok = 1; }
'''

    base = client.base_url.rstrip('/')
    ts = int(time.time())
    api_name = f'grpcdemo{ts}'
    api_version = 'v1'
    pkg = f'{api_name}_{api_version}'

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        (tmp / 'svc.proto').write_text(PROTO.replace('{pkg}', pkg))
        out = tmp / 'gen'
        out.mkdir()
        code = protoc.main(['protoc', f'--proto_path={td}', f'--python_out={out}', f'--grpc_python_out={out}', str(tmp / 'svc.proto')])
        assert code == 0
        (out / '__init__.py').write_text('')
        sys.path.insert(0, str(out))
        pb2 = importlib.import_module('svc_pb2')
        pb2_grpc = importlib.import_module('svc_pb2_grpc')

        class Resource(pb2_grpc.ResourceServicer):
            def Create(self, request, context):
                return pb2.CreateReply(message=f'created {request.name}')

            def Read(self, request, context):
                return pb2.ReadReply(message=f'read {request.id}')

            def Update(self, request, context):
                return pb2.UpdateReply(message=f'updated {request.id}:{request.name}')

            def Delete(self, request, context):
                return pb2.DeleteReply(ok=True)

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        pb2_grpc.add_ResourceServicer_to_server(Resource(), server)
        port = _find_port()
        server.add_insecure_port(f'0.0.0.0:{port}')
        server.start()
        time.sleep(0.2)

        try:
            host_ref = _get_host_from_container()
            files = {'file': ('svc.proto', PROTO.replace('{pkg}', pkg), 'application/octet-stream')}
            r_up = client.post(f'/platform/proto/{api_name}/{api_version}', files=files)
            assert r_up.status_code in (200, 201), r_up.text

            r_api = client.post('/platform/api', json={
                'api_name': api_name,
                'api_version': api_version,
                'api_description': 'public grpc with uploaded proto',
                'api_allowed_roles': [],
                'api_allowed_groups': [],
                'api_servers': [f'grpc://{host_ref}:{port}'],
                'api_type': 'REST',
                'active': True,
                'api_public': True,
                'api_grpc_package': pkg
            })
            assert r_api.status_code in (200, 201), r_api.text

            r_ep = client.post('/platform/endpoint', json={
                'api_name': api_name,
                'api_version': api_version,
                'endpoint_method': 'POST',
                'endpoint_uri': '/grpc',
                'endpoint_description': 'grpc'
            })
            assert r_ep.status_code in (200, 201), r_ep.text

            url = f"{base}/api/grpc/{api_name}"
            hdr = {'X-API-Version': api_version}
            assert requests.post(url, json={'method': 'Resource.Create', 'message': {'name': 'A'}}, headers=hdr).status_code == 200
            assert requests.post(url, json={'method': 'Resource.Read', 'message': {'id': 1}}, headers=hdr).status_code == 200
            assert requests.post(url, json={'method': 'Resource.Update', 'message': {'id': 1, 'name': 'B'}}, headers=hdr).status_code == 200
            assert requests.post(url, json={'method': 'Resource.Delete', 'message': {'id': 1}}, headers=hdr).status_code == 200
        finally:
            try:
                client.delete(f'/platform/endpoint/POST/{api_name}/{api_version}/grpc')
            except Exception:
                pass
            try:
                client.delete(f'/platform/api/{api_name}/{api_version}')
            except Exception:
                pass
            server.stop(0)

