
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath('backend-services'))

# Set environment variables like conftest.py
os.environ.setdefault('MEM_OR_EXTERNAL', 'MEM')
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key')
os.environ.setdefault('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev')
os.environ.setdefault('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars')
os.environ.setdefault('DOORMAN_TEST_MODE', 'true')
os.environ.setdefault('LOGIN_IP_RATE_DISABLED', 'true')

async def verify_schema():
    from doorman import doorman
    from httpx import AsyncClient
    from utils.database import database as db
    
    print("--- Starting Schema Validation Verification ---")
    
    async with AsyncClient(app=doorman, base_url='http://testserver') as client:
        # 1. Login
        print("1. Logging in...")
        login_payload = {
            'email': os.environ['DOORMAN_ADMIN_EMAIL'],
            'password': os.environ['DOORMAN_ADMIN_PASSWORD']
        }
        r = await client.post('/platform/authorization', json=login_payload)
        
        # Determine success without failing script immediately if auth fails due to existing state
        if r.status_code == 200:
            token = r.json().get('access_token')
            if token:
                client.cookies.set('access_token_cookie', token)
        else:
            print(f"Login failed/skipped: {r.status_code}")
            # Try to continue if we are modifying existing DB state in memory test
        
        # 2. Create API with Schema
        print("2. Creating API with Schema...")
        api_name = "test-schema-api"
        version = "v1"
        resource = "users"
        
        # Cleanup previous
        await client.delete(f'/platform/api/{api_name}/{version}')
        
        
        
        # DEBUG: Check model fields
        import pydantic
        print(f"DEBUG: Pydantic version: {pydantic.VERSION}")
        from models.create_api_model import CreateApiModel
        # Try V1 or V2 access
        fields = getattr(CreateApiModel, 'model_fields', getattr(CreateApiModel, '__fields__', {}))
        print(f"DEBUG: CreateApiModel fields: {fields.keys()}")
        if 'api_crud_schema' in fields:
             f = fields['api_crud_schema']
             print("DEBUG: api_crud_schema field:", f)
        
        schema = {
            "name": {"type": "string", "required": True, "min_length": 3},
            "age": {"type": "number", "min_value": 0, "max_value": 120},
            "role": {"type": "string", "enum": ["user", "admin"]}
        }

        api_payload = {
            'api_name': api_name,
            'api_version': version,
            'api_type': 'REST',
            'api_is_crud': True,
            'api_crud_schema': schema,
            'active': True,
            'api_allowed_groups': ['ALL'],
            'api_auth_required': True
        }
        
        r = await client.post('/platform/api', json=api_payload)
        if r.status_code not in (200, 201):
            print(f"FAILED to update/create API: {r.status_code}")
            print(r.text)
            return

        # 3. Create endpoint
        ep_uri = f"/{resource}"
        await client.post('/platform/endpoint', json={
            'api_name': api_name, 'api_version': version, 
            'endpoint_method': 'POST', 'endpoint_uri': ep_uri
        })
        
        # 4. Valid Request
        print("4. Testing Valid POST...")
        valid_data = {"name": "Alice", "age": 30, "role": "admin"}
        r = await client.post(f'/api/rest/{api_name}/{version}{ep_uri}', json=valid_data)
        if r.status_code == 201:
            print("  SUCCESS: Valid request accepted")
        else:
            print(f"  FAILED: Valid request rejected: {r.status_code} {r.text}")

        # 5. Invalid Request - Missing Required
        print("5. Testing Missing Required Field...")
        invalid_data = {"age": 30, "role": "user"} # name missing
        r = await client.post(f'/api/rest/{api_name}/{version}{ep_uri}', json=invalid_data)
        if r.status_code == 400:
            print("  SUCCESS: Missing required field rejected")
        else:
             print(f"  FAILED: Missing required field allowed: {r.status_code}")

        # 6. Invalid Request - Constraints
        print("6. Testing Constraint Violation (age < 0)...")
        invalid_data = {"name": "Bob", "age": -5, "role": "user"}
        r = await client.post(f'/api/rest/{api_name}/{version}{ep_uri}', json=invalid_data)
        if r.status_code == 400:
            print("  SUCCESS: Constraint violation rejected")
        else:
             print(f"  FAILED: Constraint violation allowed: {r.status_code}")

        # 7. Invalid Request - Type Check
        print("7. Testing Type Violation (name is number)...")
        invalid_data = {"name": 12345, "age": 30, "role": "user"}
        r = await client.post(f'/api/rest/{api_name}/{version}{ep_uri}', json=invalid_data)
        if r.status_code == 400:
            print("  SUCCESS: Type violation rejected")
        else:
             print(f"  FAILED: Type violation allowed: {r.status_code}")

        print("--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(verify_schema())
