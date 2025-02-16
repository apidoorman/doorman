"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

# External imports
import bcrypt

def hash_password(password: str) -> str:
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed_password.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    password = password.encode('utf-8')
    hashed_password = hashed_password.encode('utf-8')
    if bcrypt.checkpw(password, hashed_password):
        return True
    else:
        return False