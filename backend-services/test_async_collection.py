#!/usr/bin/env python3
"""Test script to verify async collection behavior"""
import asyncio
import os
os.environ['MEM_OR_EXTERNAL'] = 'MEM'

from utils.database_async import async_database

async def test_async_collection():
    print("Testing async collection...")
    
    # Insert a test tier
    test_tier = {
        'tier_id': 'test',
        'name': 'test',
        'display_name': 'Test Tier',
        'limits': {},
        'features': [],
        'is_default': False,
        'enabled': True
    }
    
    await async_database.db.tiers.insert_one(test_tier)
    print("Inserted test tier")
    
    # Try to list tiers
    cursor = async_database.db.tiers.find({})
    print(f"Cursor type: {type(cursor)}")
    print(f"Cursor has skip: {hasattr(cursor, 'skip')}")
    print(f"Cursor has limit: {hasattr(cursor, 'limit')}")
    
    # Test skip/limit
    cursor = cursor.skip(0).limit(10)
    print("Applied skip/limit")
    
    # Iterate
    tiers = []
    async for tier_data in cursor:
        print(f"Found tier: {tier_data.get('tier_id')}")
        tiers.append(tier_data)
    
    print(f"Total tiers found: {len(tiers)}")
    return tiers

if __name__ == '__main__':
    result = asyncio.run(test_async_collection())
    print(f"Result: {result}")
