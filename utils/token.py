from datetime import datetime, timedelta
from fastapi_jwt_auth import AuthJWT

def create_access_token(data: dict, Authorize: AuthJWT):
    to_encode = data.copy()
    expire = timedelta(minutes=30)
    to_encode.update({"exp": datetime.utcnow() + expire})
    encoded_jwt = Authorize.create_access_token(subject=data["sub"], expires_time=expire, user_claims={"role": data.get("role")})
    return encoded_jwt