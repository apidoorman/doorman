
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

async def verify_flow():
    from doorman import doorman
    from httpx import AsyncClient
    from utils.database import database as db
    
    # Ensure admin user exists for test
    try:
        if hasattr(db, 'db') and hasattr(db.db, 'users'):
            users = db.db.users
            admin_email = os.environ['DOORMAN_ADMIN_EMAIL']
            # Simple check if admin exists, if not create
            # Note: In-memory DB usually starts empty or with defaults depending on init
            # But let's try to login first.
            pass
    except Exception as e:
        print(f"Warning checking DB: {e}")

    print("--- Starting API Builder Flow Verification ---")
    
    async with AsyncClient(app=doorman, base_url='http://testserver') as client:
        # 0. Ensure Admin User Exists (if needed)
        # We can try to create it directly via internal method or just hope it's there.
        # Let's try to create it using the setup endpoint if it exists or just rely on default.
        # Actually simplest is to try login, if fail with 400/404, maybe create it?
        # But we don't have a public create-admin endpoint.
        # Let's rely on app startup to create admin if configured.
        
        # 1. Login
        print("1. Logging in...")
        login_payload = {
            'email': os.environ['DOORMAN_ADMIN_EMAIL'],
            'password': os.environ['DOORMAN_ADMIN_PASSWORD']
        }
        r = await client.post('/platform/authorization', json=login_payload)
        
        if r.status_code == 400:
            print(f"Login failed: {r.status_code} - {r.text}")
            # Try to register/create user if possible? 
            # In test mode, maybe we can hack it?
            # Let's try to inject the user directly into the DB if we can import it
            print("Attempting to inject admin user...")
            from utils.database import database
            from utils.security_util import hash_password
            
            admin_user = {
                'email': login_payload['email'],
                'password_hash': hash_password(login_payload['password']),
                'role': 'admin',
                'active': True,
                'groups': ['ALL'],
                'username': 'admin'
            }
            # Add to users collection
            if hasattr(database.db, 'users'):
                # Check if exists
                existing = next((u for u in database.db.users._data if u.get('email') == login_payload['email']), None)
                if not existing:
                    database.db.users._data.append(admin_user)
                    print("Injected admin user.")
                else:
                    print("Admin user already in DB?")
            
            # Retry login
            r = await client.post('/platform/authorization', json=login_payload)
        
        if r.status_code != 200:
            print(f"Login failed: {r.status_code} - {r.text}")
            return
            
        # Extract token
        token = r.json().get('access_token')
        if token:
            client.cookies.set('access_token_cookie', token)
        
        print("Login successful.")

        # 2. Mimic Frontend: Create API
        print("2. Creating API (simulating frontend form submit)...")
        api_name = "builder-test-api"
        version = "v1"
        resource = "products"
        
        # Cleanup previous run if exists
        try:
            await client.delete(f'/platform/api/{api_name}/{version}')
        except:
            pass
        
        api_payload = {
            'api_name': api_name,
            'api_version': version,
            'api_type': 'REST',
            'api_is_crud': True,
            'api_servers': [],
            'active': True,
            'api_allowed_groups': ['ALL'],
            'api_allowed_roles': [],
            'api_auth_required': True
        }
        
        r = await client.post('/platform/api', json=api_payload)
        if r.status_code not in (200, 201):
            print(f"FAILED: Create API returned {r.status_code}: {r.text}")
            return
        print(f"SUCCESS: API created")
        
        # 3. Mimic Frontend: Create endpoints
        print(f"3. Generating endpoints for resource '{resource}'...")
        endpoints = [
            {'method': 'GET', 'uri': f'/{resource}'},
            {'method': 'POST', 'uri': f'/{resource}'},
            {'method': 'GET', 'uri': f'/{resource}/{{id}}'},
            {'method': 'PUT', 'uri': f'/{resource}/{{id}}'},
            {'method': 'DELETE', 'uri': f'/{resource}/{{id}}'}
        ]
        
        for ep in endpoints:
            payload = {
                'api_name': api_name,
                'api_version': version,
                'endpoint_method': ep['method'],
                'endpoint_uri': ep['uri'],
                'endpoint_description': f"Auto-generated {ep['method']} {ep['uri']}"
            }
            r = await client.post('/platform/endpoint', json=payload)
            if r.status_code not in (200, 201):
                # 409 is ok if it exists
                if r.status_code != 409:
                    print(f"FAILED: Create endpoint {ep['method']} {ep['uri']} returned {r.status_code}")
                else:
                    print(f"  - Endpoint {ep['method']} {ep['uri']} already exists")
            else:
                print(f"  - Created {ep['method']} {ep['uri']}")

        # 4. Verify functionality
        print("4. Verifying CRUD functionality...")
        
        # Create item
        item = {'name': 'test-product', 'price': 99.99}
        r = await client.post(f'/api/rest/{api_name}/{version}/{resource}', json=item)
        print(f"POST /{resource}: {r.status_code}")
        
        item_id = None
        if r.status_code == 201:
            data = r.json()
            item_id = data.get('_id')
            print(f"  - Created item ID: {item_id}")
            
            # Get item
            r = await client.get(f'/api/rest/{api_name}/{version}/{resource}/{item_id}')
            print(f"GET /{resource}/{{id}}: {r.status_code}")
            if r.status_code == 200:
                print(f"  - Retrieved item: {r.json().get('name')}")
            else:
                print(f"  - Failed to get item: {r.text}")
                
            # List items
            r = await client.get(f'/api/rest/{api_name}/{version}/{resource}')
            print(f"GET /{resource}: {r.status_code}")
            if r.status_code == 200:
                items = r.json().get('items', [])
                print(f"  - List count: {len(items)}")
            else:
                print(f"  - Failed to list items: {r.text}")
                
        else:
            print(f"  - Failed to create item: {r.text}")

        print("--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(verify_flow())
