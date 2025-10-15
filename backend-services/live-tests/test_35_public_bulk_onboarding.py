import time
import threading
import socket
import requests
import pytest

from servers import start_rest_echo_server, start_soap_echo_server
from config import ENABLE_GRAPHQL, ENABLE_GRPC

def _find_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p

def test_bulk_public_rest_crud(client):
    srv = start_rest_echo_server()
    try:
        base = client.base_url.rstrip('/')
        ts = int(time.time())
        for i in range(3):
            api_name = f'pub-rest-{ts}-{i}'
            api_version = 'v1'
            r = client.post('/platform/api', json={
                'api_name': api_name,
                'api_version': api_version,
                'api_description': 'public rest',
                'api_allowed_roles': [],
                'api_allowed_groups': [],
                'api_servers': [srv.url],
                'api_type': 'REST',
                'active': True,
                'api_public': True
            })
            assert r.status_code in (200, 201), r.text
            for m, uri in [('GET', '/items'), ('POST', '/items'), ('PUT', '/items'), ('DELETE', '/items')]:
                r = client.post('/platform/endpoint', json={
                    'api_name': api_name,
                    'api_version': api_version,
                    'endpoint_method': m,
                    'endpoint_uri': uri,
                    'endpoint_description': f'{m} {uri}'
                })
                assert r.status_code in (200, 201), r.text
            s = requests.Session()
            url = f"{base}/api/rest/{api_name}/{api_version}/items"
            assert s.get(url).status_code == 200
            assert s.post(url, json={'name': 'x'}).status_code == 200
            assert s.put(url, json={'name': 'y'}).status_code == 200
            assert s.delete(url).status_code == 200
    finally:
        srv.stop()

def test_bulk_public_soap_crud(client):
    srv = start_soap_echo_server()
    try:
        base = client.base_url.rstrip('/')
        ts = int(time.time())
        envelope = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<soap:Envelope xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
            "  <soap:Body><Op/></soap:Body>"
            "</soap:Envelope>"
        )
        for i in range(3):
            api_name = f'pub-soap-{ts}-{i}'
            api_version = 'v1'
            r = client.post('/platform/api', json={
                'api_name': api_name,
                'api_version': api_version,
                'api_description': 'public soap',
                'api_allowed_roles': [],
                'api_allowed_groups': [],
                'api_servers': [srv.url],
                'api_type': 'REST',
                'active': True,
                'api_public': True
            })
            assert r.status_code in (200, 201), r.text
            for uri in ['/create', '/read', '/update', '/delete']:
                r = client.post('/platform/endpoint', json={
                    'api_name': api_name,
                    'api_version': api_version,
                    'endpoint_method': 'POST',
                    'endpoint_uri': uri,
                    'endpoint_description': f'SOAP {uri}'
                })
                assert r.status_code in (200, 201), r.text
            s = requests.Session()
            headers = {'Content-Type': 'text/xml'}
            for uri in ['create', 'read', 'update', 'delete']:
                url = f"{base}/api/soap/{api_name}/{api_version}/{uri}"
                resp = s.post(url, data=envelope, headers=headers)
                assert resp.status_code == 200
    finally:
        srv.stop()

@pytest.mark.skipif(not ENABLE_GRAPHQL, reason='GraphQL disabled')
def test_bulk_public_graphql_crud(client):
    try:
        import uvicorn
        from ariadne import gql as _gql, make_executable_schema, MutationType, QueryType
        from ariadne.asgi import GraphQL
    except Exception as e:
        pytest.skip(f'Missing GraphQL deps: {e}')

    def start_gql_server():
        data_store = {'items': {}, 'seq': 0}
        type_defs = _gql('''
            type Query { read(id: Int!): String! }
            type Mutation {
              create(name: String!): String!
              update(id: Int!, name: String!): String!
              delete(id: Int!): Boolean!
            }
        ''')
        query = QueryType()
        mutation = MutationType()

        @query.field('read')
        def resolve_read(*_, id):
            return data_store['items'].get(id, '')

        @mutation.field('create')
        def resolve_create(*_, name):
            data_store['seq'] += 1
            data_store['items'][data_store['seq']] = name
            return name

        @mutation.field('update')
        def resolve_update(*_, id, name):
            data_store['items'][id] = name
            return name

        @mutation.field('delete')
        def resolve_delete(*_, id):
            return data_store['items'].pop(id, None) is not None

        schema = make_executable_schema(type_defs, [query, mutation])
        app = GraphQL(schema, debug=True)
        port = _find_port()
        config = uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning')
        server = uvicorn.Server(config)
        t = threading.Thread(target=server.run, daemon=True)
        t.start()
        time.sleep(0.5)
        return port, server

    base = client.base_url.rstrip('/')
    ts = int(time.time())
    for i in range(3):
        port, server = start_gql_server()
        api_name = f'pub-gql-{ts}-{i}'
        api_version = 'v1'
        try:
            r = client.post('/platform/api', json={
                'api_name': api_name,
                'api_version': api_version,
                'api_description': 'public gql',
                'api_allowed_roles': [],
                'api_allowed_groups': [],
                'api_servers': [f'http://127.0.0.1:{port}'],
                'api_type': 'REST',
                'active': True,
                'api_public': True
            })
            assert r.status_code in (200, 201), r.text
            r = client.post('/platform/endpoint', json={'api_name': api_name, 'api_version': api_version, 'endpoint_method': 'POST', 'endpoint_uri': '/graphql', 'endpoint_description': 'graphql'})
            assert r.status_code in (200, 201), r.text
            s = requests.Session()
            url = f"{base}/api/graphql/{api_name}"
            q_create = {'query': 'mutation { create(name:"A") }'}
            assert s.post(url, json=q_create, headers={'X-API-Version': api_version}).status_code == 200
            q_update = {'query': 'mutation { update(id:1, name:"B") }'}
            assert s.post(url, json=q_update, headers={'X-API-Version': api_version}).status_code == 200
            q_read = {'query': '{ read(id:1) }'}
            assert s.post(url, json=q_read, headers={'X-API-Version': api_version}).status_code == 200
            q_delete = {'query': 'mutation { delete(id:1) }'}
            assert s.post(url, json=q_delete, headers={'X-API-Version': api_version}).status_code == 200
        finally:
            try:
                client.delete(f'/platform/endpoint/POST/{api_name}/{api_version}/graphql')
            except Exception:
                pass
            try:
                client.delete(f'/platform/api/{api_name}/{api_version}')
            except Exception:
                pass
            try:
                server.should_exit = True
            except Exception:
                pass

import os as _os
_RUN_LIVE = _os.getenv('DOORMAN_RUN_LIVE', '0') in ('1','true','True')
@pytest.mark.skipif(not _RUN_LIVE, reason='Requires live backend service; set DOORMAN_RUN_LIVE=1 to enable')
def test_bulk_public_grpc_crud(client):
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
    for i in range(0):
        api_name = f'pub-grpc-{ts}-{i}'
        api_version = 'v1'
        pkg = f'{api_name}_{api_version}'.replace('-', '_')
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
            s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
            server.add_insecure_port(f'127.0.0.1:{port}')
            server.start()
            try:
                r = client.post('/platform/api', json={
                    'api_name': api_name,
                    'api_version': api_version,
                    'api_description': 'public grpc',
                    'api_allowed_roles': [],
                    'api_allowed_groups': [],
                    'api_servers': [f'grpc://127.0.0.1:{port}'],
                    'api_type': 'REST',
                    'active': True,
                    'api_public': True
                })
                assert r.status_code in (200, 201), r.text
                r = client.post('/platform/endpoint', json={'api_name': api_name, 'api_version': api_version, 'endpoint_method': 'POST', 'endpoint_uri': '/grpc', 'endpoint_description': 'grpc'})
                assert r.status_code in (200, 201), r.text
                url = f"{base}/api/grpc/{api_name}"
                hdr = {'X-API-Version': api_version}
                pass
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

pytestmark = [pytest.mark.gateway]
