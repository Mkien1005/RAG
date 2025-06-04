import base64
import json
from fastapi import HTTPException, Header, Request, status
import os

JWT_PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY").replace("\\n", "\n")
ALGORITHM = os.getenv("ALGORITHM", "RS256")

# Dependency để lấy thông tin người dùng từ header X-User
async def get_current_user(request: Request):
    x_user = request.headers.get("x-user")
    if not x_user:
        raise HTTPException(status_code=401, detail="Unauthorized: Missing user data")
    decoded_user = base64.b64decode(x_user).decode("utf-8")
    user_data = json.loads(decoded_user)
    return user_data
