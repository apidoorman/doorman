#!/usr/bin/env python3
"""Quick test to validate role model"""

from models.update_role_model import UpdateRoleModel

# Test data with new permissions
test_data = {
    'role_name': 'admin',
    'role_description': 'Administrator role',
    'manage_users': True,
    'manage_apis': True,
    'manage_endpoints': True,
    'manage_groups': True,
    'manage_roles': True,
    'manage_routings': True,
    'manage_gateway': True,
    'manage_subscriptions': True,
    'manage_security': True,
    'manage_tiers': True,
    'manage_rate_limits': True,
    'manage_credits': True,
    'manage_auth': True,
    'view_analytics': True,
    'view_logs': True,
    'export_logs': True,
}

try:
    model = UpdateRoleModel(**test_data)
    print('✅ Model validation successful!')
    print(f'Model: {model.model_dump()}')
except Exception as e:
    print(f'❌ Model validation failed: {e}')
    import traceback

    traceback.print_exc()
