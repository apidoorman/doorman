from datetime import datetime, timedelta
from fastapi_jwt_auth import AuthJWT
import uuid

def create_access_token(data: dict, Authorize: AuthJWT, refresh: bool = False):
    to_encode = data.copy()
    expire = timedelta(minutes=30) if not refresh else timedelta(days=7)
    to_encode.update({"exp": datetime.utcnow() + expire, "jti": str(uuid.uuid4())})
    encoded_jwt = Authorize.create_access_token(subject=data["sub"], expires_time=expire, user_claims={"role": data.get("role")})
    return encoded_jwt