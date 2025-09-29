"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

import bcrypt

def hash_password(password: str):
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed_password

def verify_password(password: str, hashed_password: str):
    password = password.encode('utf-8')
    return bcrypt.checkpw(password, hashed_password)
    
def is_secure_password(password: str):
    if len(password) < 16:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.islower() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    if not any(c in '!@#$%^&*()-_=+[]{};:,.<>?/' for c in password):
        return False
    return True