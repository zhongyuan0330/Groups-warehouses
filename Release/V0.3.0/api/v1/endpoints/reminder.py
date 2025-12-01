from fastapi import APIRouter, HTTPException, Depends
from datetime import date, timedelta, datetime
from typing import List, Optional

# 导入依赖
from app.api.deps import get_current_user

# 导入模型和Schema
from app.models.plant import Plant
from app.models.user import User
from app.schemas.user import BaseResponse
from app.schemas.reminder import (
    ReminderItem,
    ReminderListResponse,
    PlantOperationResponse,
    PlantCreate,
    PlantOut  # <--- 1. 新增导入这个
)

router = APIRouter()


# --- 辅助函数 (保持不变) ---
def calculate_days_overdue(last_date: Optional[object], cycle: int) -> int:
    if not last_date: return 999
    if isinstance(last_date, datetime):
        last_date_obj = last_date.date()
    elif isinstance(last_date, date):
        last_date_obj = last_date
    else:
        return 999
    today = date.today()
    days_passed = (today - last_date_obj).days
    return days_passed - cycle


def get_urgency_level(days_overdue: int, cycle: int) -> str:
    if days_overdue < 0: return "low"
    safe_cycle = cycle if cycle > 0 else 1
    ratio = days_overdue / safe_cycle
    if ratio > 0.5: return "high"
    if ratio > 0.2: return "medium"
    return "low"


def get_icon(operation_type: str, urgency: str) -> str:
    base_icons = {"water": "💧", "fertilize": "🌱"}
    base = base_icons.get(operation_type, "🍃")
    if urgency == "high": return f"{base}🔥"
    if urgency == "medium": return f"{base}⏰"
    return base


# --- 路由定义 ---

# 2. 新增：获取用户所有植物列表
@router.get("/get_plants", response_model=BaseResponse)
async def get_user_plants(
        current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的所有植物列表
    """
    # 查询属于当前用户且未删除的植物，按创建时间倒序排列
    plants = await Plant.filter(user=current_user, is_deleted=False).order_by("-created_at").all()

    # 将 ORM 对象转换为 Pydantic 模型列表
    # Tortoise ORM 对象可以直接传给 Pydantic (如果配置了 from_attributes=True)
    plant_data = [PlantOut.model_validate(p) for p in plants]

    return BaseResponse(
        code=200,
        msg="获取成功",
        data=plant_data  # 返回列表数据
    )


@router.post("/plants", response_model=BaseResponse)
async def create_plant(
        plant_in: PlantCreate,
        current_user: User = Depends(get_current_user)
):
    """添加植物"""
    w_date = None
    if plant_in.last_watered:
        try:
            w_date = datetime.strptime(plant_in.last_watered, "%Y-%m-%d").date()
        except ValueError:
            pass

    f_date = None
    if plant_in.last_fertilized:
        try:
            f_date = datetime.strptime(plant_in.last_fertilized, "%Y-%m-%d").date()
        except ValueError:
            pass

    plant = await Plant.create(
        user=current_user,
        nickname=plant_in.nickname,
        species=plant_in.species,
        water_cycle=plant_in.water_cycle,
        fertilize_cycle=plant_in.fertilize_cycle,
        last_watered=w_date,
        last_fertilized=f_date
    )

    return BaseResponse(
        msg="植物添加成功",
        data={"plant_id": plant.id, "nickname": plant.nickname}
    )


@router.get("/reminders", response_model=BaseResponse)
async def get_reminders(current_user: User = Depends(get_current_user)):
    """获取智能提醒列表"""
    reminders: List[ReminderItem] = []
    plants = await Plant.filter(user=current_user, is_deleted=False).all()
    today = date.today()

    for plant in plants:
        # 检查浇水
        if plant.water_cycle > 0:
            overdue = calculate_days_overdue(plant.last_watered, plant.water_cycle)
            if overdue >= -1:
                urgency = get_urgency_level(max(0, overdue), plant.water_cycle)
                last_w = plant.last_watered
                if isinstance(last_w, datetime): last_w = last_w.date()
                base_date = last_w or today
                due_date_obj = base_date + timedelta(days=plant.water_cycle)
                msg = f"{plant.nickname}明天需要浇水" if overdue == -1 else f"{plant.nickname}已逾期{overdue}天未浇水"

                reminders.append(ReminderItem(
                    plant_id=plant.id,
                    plant_name=plant.nickname,
                    type="water",
                    message=msg,
                    days_overdue=max(0, overdue),
                    urgency=urgency,
                    due_date=due_date_obj.strftime("%Y-%m-%d"),
                    icon=get_icon("water", urgency)
                ))

        # 检查施肥 (逻辑同上，略微省略以节省篇幅，保持你原有逻辑即可)
        if plant.fertilize_cycle > 0:
            overdue = calculate_days_overdue(plant.last_fertilized, plant.fertilize_cycle)
            if overdue >= -1:
                urgency = get_urgency_level(max(0, overdue), plant.fertilize_cycle)
                last_f = plant.last_fertilized
                if isinstance(last_f, datetime): last_f = last_f.date()
                base_date = last_f or today
                due_date_obj = base_date + timedelta(days=plant.fertilize_cycle)
                msg = f"{plant.nickname}明天需要施肥" if overdue == -1 else f"{plant.nickname}已逾期{overdue}天未施肥"

                reminders.append(ReminderItem(
                    plant_id=plant.id,
                    plant_name=plant.nickname,
                    type="fertilize",
                    message=msg,
                    days_overdue=max(0, overdue),
                    urgency=urgency,
                    due_date=due_date_obj.strftime("%Y-%m-%d"),
                    icon=get_icon("fertilize", urgency)
                ))

    urgency_map = {"high": 0, "medium": 1, "low": 2}
    reminders.sort(key=lambda x: (urgency_map[x.urgency], -x.days_overdue))

    return BaseResponse(data=ReminderListResponse(reminders=reminders, total=len(reminders)).model_dump())


@router.post("/plants/{plant_id}/water", response_model=BaseResponse)
async def record_watering(plant_id: int, current_user: User = Depends(get_current_user)):
    plant = await Plant.get_or_none(id=plant_id, user=current_user, is_deleted=False)
    if not plant: return BaseResponse(code=404, msg="植物不存在或无权操作")
    plant.last_watered = date.today()
    await plant.save()
    return BaseResponse(msg="浇水打卡成功", data=PlantOperationResponse(plant_id=plant.id, operation="water",
                                                                        operated_at=str(plant.last_watered)).dict())


@router.post("/plants/{plant_id}/fertilize", response_model=BaseResponse)
async def record_fertilizing(plant_id: int, current_user: User = Depends(get_current_user)):
    plant = await Plant.get_or_none(id=plant_id, user=current_user, is_deleted=False)
    if not plant: return BaseResponse(code=404, msg="植物不存在或无权操作")
    plant.last_fertilized = date.today()
    await plant.save()
    return BaseResponse(msg="施肥打卡成功", data=PlantOperationResponse(plant_id=plant.id, operation="fertilize",
                                                                        operated_at=str(plant.last_fertilized)).dict())