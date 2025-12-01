# app/api/v1/api.py
from fastapi import APIRouter
from app.api.v1.endpoints import user
from app.api.v1.endpoints import ai      # 之前的 AI 模块
from app.api.v1.endpoints import reminder # 新增的 提醒/植物 模块

api_router = APIRouter()

# 用户模块 -> /api/v1/auth/...
api_router.include_router(user.router, prefix="/auth", tags=["用户中心"])

# AI模块 -> /api/v1/plant/chat... (根据上一次的修改)
api_router.include_router(ai.router, prefix="/plant", tags=["AI养护助手"])

# 智慧提醒与植物管理模块
# 这里 prefix=""，因为 reminder.py 内部已经包含了 /reminders 和 /plants 两个不同的资源路径
# 最终路径示例: /api/v1/reminders, /api/v1/plants/1/water
api_router.include_router(reminder.router, prefix="", tags=["智慧提醒与管理"])