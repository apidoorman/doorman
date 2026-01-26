
import asyncio
import sys
import os
import pydantic

# Add backend to path
sys.path.insert(0, os.path.abspath('backend-services'))

# Set environment variables like conftest.py
os.environ.setdefault('MEM_OR_EXTERNAL', 'MEM')
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key')
os.environ.setdefault('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev')
os.environ.setdefault('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars')
os.environ.setdefault('DOORMAN_TEST_MODE', 'true')
os.environ.setdefault('LOGIN_IP_RATE_DISABLED', 'true')
os.environ.setdefault('DISABLE_PLATFORM_CHUNKED_WRAP', 'true')

async def verify_nested_schema():
    from doorman import doorman
    from httpx import AsyncClient
    from utils.database import database as db
    
    print("--- Starting Nested Schema Verification ---")
    
    async with AsyncClient(app=doorman, base_url='http://testserver') as client:
        # 1. Login
        login_payload = {
            'email': os.environ['DOORMAN_ADMIN_EMAIL'],
            'password': os.environ['DOORMAN_ADMIN_PASSWORD']
        }
        r = await client.post('/platform/authorization', json=login_payload)
        if r.status_code == 200:
            token = r.json().get('access_token')
            if token:
                client.cookies.set('access_token_cookie', token)
        
        # 2. Define Nested Schema
        # User -> Address (Object) -> City (String, Required)
        nested_schema = {
            "name": {"type": "string", "required": True},
            "address": {
                "type": "object",
                "required": True,
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string", "required": True},
                    "zip": {"type": "number", "min_value": 10000}
                }
            }
        }
        
        api_name = "test-nested-api"
        version = "v1"
        resource = "customers"
        
        # Cleanup
        await client.delete(f'/platform/api/{api_name}/{version}')

        api_payload = {
            'api_name': api_name,
            'api_version': version,
            'api_type': 'REST',
            'api_is_crud': True,
            'api_crud_schema': nested_schema,
            'active': True,
            'api_allowed_groups': ['ALL'],
            'api_auth_required': True
        }
        
        print("2. Creating API with Nested Schema...")
        r = await client.post('/platform/api', json=api_payload)
        if r.status_code not in (200, 201):
            print(f"FAILED to update/create API: {r.status_code}")
            print(r.text)
            return
        
        # Create Endpoint
        await client.post('/platform/endpoint', json={
            'api_name': api_name, 'api_version': version, 
            'endpoint_method': 'POST', 'endpoint_uri': f'/{resource}'
        })

        ep_url = f'/api/rest/{api_name}/{version}/{resource}'

        # 3. Test Valid Nested Data
        print("3. Testing Valid Nested Data...")
        valid_data = {
            "name": "Jane Doe",
            "address": {
                "street": "123 Main St",
                "city": "New York",
                "zip": 10001
            }
        }
        r = await client.post(ep_url, json=valid_data)
        if r.status_code == 201:
            print("  SUCCESS: Valid nested data accepted")
        else:
            print(f"  FAILED: Valid data rejected: {r.status_code} {r.text}")

        # 4. Test Invalid Child Data (Missing Required Field in Child)
        print("4. Testing Missing Child Field (address.city)...")
        invalid_child = {
            "name": "John Doe",
            "address": {
                "street": "456 Elm St",
                # "city" missing
                "zip": 10002
            }
        }
        r = await client.post(ep_url, json=invalid_child)
        if r.status_code == 400:
            print("  SUCCESS: Missing child field rejected")
            print(f"  Error: {r.json()['response']['errors']}")
        else:
            print(f"  FAILED: Missing child field allowed: {r.status_code}")

        # 5. Test Invalid Child Constraint (zip too small)
        print("5. Testing Child Constraint Violation (zip < 10000)...")
        invalid_constraint = {
            "name": "Jim Doe",
            "address": {
                "city": "Boston",
                "zip": 123
            }
        }
        r = await client.post(ep_url, json=invalid_constraint)
        if r.status_code == 400:
             print("  SUCCESS: Child constraint violation rejected")
             print(f"  Error: {r.json()['response']['errors']}")
        else:
             print(f"  FAILED: Child constraint allowed: {r.status_code}")

        print("--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(verify_nested_schema())
