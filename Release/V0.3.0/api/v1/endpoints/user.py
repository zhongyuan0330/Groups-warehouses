from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm  # <--- 1. 引入这个
from app.schemas.user import UserRegister, BaseResponse, UserLogin  # 移除了 UserLogin
from app.models.user import User
from app.core.security import verify_password, get_password_hash, create_access_token

router = APIRouter()


# --------------------------
# 注册接口 (无验证码)
# --------------------------
@router.post("/register", response_model=BaseResponse)
async def register(req: UserRegister):
    # 1. 检查用户名是否已存在
    if await User.filter(username=req.username).exists():
        return BaseResponse(code=400, msg="用户名已存在")

    # 2. 检查邮箱是否已存在
    if await User.filter(email=req.email).exists():
        return BaseResponse(code=400, msg="该邮箱已被注册")

    # 3. 创建用户 (密码加密存储)
    # 注意：id, created_at, updated_at, is_deleted 会自动处理
    new_user = await User.create(
        username=req.username,
        email=req.email,
        password=get_password_hash(req.password)
    )

    # 4. 注册成功，自动生成 Token 让用户免登直接进入? 或者要求重新登录
    # 这里演示直接返回注册成功
    return BaseResponse(
        msg="注册成功",
        data={"user_id": new_user.id, "username": new_user.username}
    )


@router.post("/login", response_model=BaseResponse)  # 你可以选择返回 BaseResponse 或直接返回 Token
async def login(user_in: UserLogin):  # <--- 关键变化：接收 Pydantic 模型 (JSON)
    """
    用户登录 (JSON 方式)
    """
    # 1. 查找用户
    user = await User.get_or_none(username=user_in.account)
    if not user:
        user = await User.get_or_none(email=user_in.account)

    # 2. 验证
    if not user or not verify_password(user_in.password, user.password):
        # 返回业务错误码 (根据你的 BaseResponse 习惯)
        return BaseResponse(code=400, msg="账号或密码错误")

    # 3. 生成 Token
    access_token = create_access_token(subject=user.id)

    # 4. 返回结果
    # 这里我们把 Token 包装在 BaseResponse 里，符合你最初的设计
    return BaseResponse(
        code=200,
        msg="登录成功",
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.id,
            "username": user.username
        }
    )