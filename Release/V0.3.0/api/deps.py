from fastapi import Depends, HTTPException, status
# 1. 改用 HTTPBearer，而不是 OAuth2PasswordBearer
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.core.config import settings
from app.models.user import User

# 这会在 Swagger 上生成一个简单的 "Token" 粘贴框
security = HTTPBearer()


async def get_current_user(token_creds: HTTPAuthorizationCredentials = Depends(security)) -> User:
    # 2. 获取 token 字符串
    token = token_creds.credentials

    # 后面的逻辑和之前一模一样
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="无效凭证")
    except JWTError:
        raise HTTPException(status_code=401, detail="无法验证凭证")

    user = await User.get_or_none(id=int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user