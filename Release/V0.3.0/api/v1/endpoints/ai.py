from fastapi import APIRouter, HTTPException, UploadFile, File, Form
# 移除不需要的 FastAPI, CORSMiddleware, StaticFiles (路由中无法直接挂载静态文件)
from fastapi.responses import JSONResponse
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional
import aiohttp

# 创建 Router 实例
router = APIRouter()

# 创建必要的目录
os.makedirs("uploads", exist_ok=True)

# DeepSeek API配置
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_API_KEY = "sk-c84fe4cb9d664f62a772dcded8d7e737"

# 植物养护专家系统提示词
PLANT_EXPERT_SYSTEM_PROMPT = """你是一个专业的植物养护专家，专注于室内植物、多肉植物、观叶植物的养护指导。请遵循以下原则：
1. 提供专业、准确的植物养护建议
2. 回答要具体、实用，避免笼统
3. 针对用户的具体问题给出针对性解决方案
4. 如果涉及病虫害，要说明识别方法和具体治疗步骤
5. 浇水建议要具体到频率、水量和注意事项
6. 光照建议要说明具体的光照时长和强度
7. 施肥建议要说明肥料类型、频率和用量
请用中文回答，语气亲切专业，像一位经验丰富的园艺师。如果用户的问题信息不足，请主动询问更多细节以便给出更精准的建议。"""

# 模拟知识库数据
KNOWLEDGE_BASE = {
    "多肉浇水指南": {
        "title": "多肉植物浇水指南",
        "content": """
        <p>多肉植物浇水核心原则：<strong>宁干勿湿，浇则浇透</strong></p>
        <p>1. 浇水频率：</p>
        <ul>
            <li>春/秋（生长季）：7-10天一次</li>
            <li>夏季：15-20天一次（少量浇水，避免积水）</li>
            <li>冬季：5°C以上10-15天一次，5°C以下断水</li>
        </ul>
        <p>2. 浇水方法：</p>
        <ul>
            <li>沿盆边缓慢浇水，避免浇到叶片中心</li>
            <li>直到盆底有水流出，确保根系充分吸收水分</li>
            <li>浇水后放在通风处，加速土壤干燥</li>
        </ul>
        """
    },
    "绿萝养护技巧": {
        "title": "绿萝日常养护与黄叶处理",
        "content": """
        <p>绿萝是非常适合室内养护的观叶植物，养护要点如下：</p>
        <p>1. 光照：适合明亮的散射光环境，避免阳光直射</p>
        <p>2. 浇水：保持土壤湿润但不积水，见干见湿</p>
        <p>3. 黄叶处理：及时摘除老叶，检查浇水情况</p>
        """
    },
    "室内植物光照需求": {
        "title": "常见室内植物光照需求表",
        "content": """
        <p>不同植物对光照的需求差异较大，合理摆放是养护关键：</p>
        <p>1. 喜光植物（需放在朝南窗台）：</p>
        <ul>
            <li>多肉植物：每天需要4-6小时光照</li>
            <li>太阳花、茉莉：需要充足直射光</li>
        </ul>
        <p>2. 中等光照（可放在朝东或朝西窗台）：</p>
        <ul>
            <li>绿萝、常春藤：适合明亮散射光</li>
        </ul>
        """
    },
    "病虫害防治": {
        "title": "植物常见病虫害防治方法",
        "content": """
        <p>植物常见病虫害及防治方法：</p>
        <p>1. 蚜虫：用清水冲洗，或用肥皂水喷洒</p>
        <p>2. 红蜘蛛：增加空气湿度，用湿布擦拭叶片</p>
        <p>3. 白粉病：及时摘除病叶，保持通风</p>
        """
    }
}

# 存储对话历史
conversations_db = {}


# 健康检查接口 (移除了 /api 前缀，由 router 统一添加)
@router.get("/health")
async def health_check():
    return {"status": "ok", "message": "植物养护AI助手后端运行正常", "timestamp": datetime.now().isoformat()}


# 对话接口
@router.post("/chat")
async def chat_with_ai(message: str = Form(...), conversation_id: Optional[str] = Form(None)):
    if not message.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "你的DeepSeek_API密钥":
        raise HTTPException(status_code=500, detail="DeepSeek API密钥未配置")

    # 处理对话ID
    if not conversation_id:
        conversation_id = str(uuid.uuid4())

    # 获取或创建对话历史
    if conversation_id not in conversations_db:
        conversations_db[conversation_id] = {
            "id": conversation_id,
            "messages": [],
            "created_at": datetime.now().isoformat(),
            "title": message[:20] + "..." if len(message) > 20 else message
        }

    # 构建对话消息
    messages = [
        {"role": "system", "content": PLANT_EXPERT_SYSTEM_PROMPT}
    ]

    # 添加历史消息（最近6轮）
    history_messages = conversations_db[conversation_id]["messages"][-6:]
    messages.extend(history_messages)

    # 添加当前用户消息
    messages.append({"role": "user", "content": message})

    try:
        # 调用DeepSeek API
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "deepseek-chat",
                "messages": messages,
                "max_tokens": 2000,
                "temperature": 0.7,
                "stream": False
            }

            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }

            async with session.post(
                    DEEPSEEK_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise HTTPException(status_code=response.status, detail=f"DeepSeek API错误: {error_text}")

                result = await response.json()
                ai_response = result["choices"][0]["message"]["content"]

        # 保存对话记录
        conversations_db[conversation_id]["messages"].extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": ai_response}
        ])

        return {
            "success": True,
            "message": ai_response,
            "conversation_id": conversation_id,
            "usage": result.get("usage", {})
        }

    except aiohttp.ClientError as e:
        raise HTTPException(status_code=500, detail=f"网络请求错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI服务暂时不可用: {str(e)}")


# 获取知识库列表
@router.get("/knowledge")
async def get_knowledge_list():
    knowledge_list = []
    for key, value in KNOWLEDGE_BASE.items():
        knowledge_list.append({
            "id": key,
            "title": value["title"],
            "preview": value["content"][:100] + "..." if len(value["content"]) > 100 else value["content"]
        })

    return {"knowledge": knowledge_list}


# 获取知识详情
@router.get("/knowledge/{knowledge_id}")
async def get_knowledge_detail(knowledge_id: str):
    if knowledge_id not in KNOWLEDGE_BASE:
        raise HTTPException(status_code=404, detail="知识条目不存在")

    return KNOWLEDGE_BASE[knowledge_id]


# 图片上传和分析接口
@router.post("/analyze-image")
async def analyze_plant_image(image: UploadFile = File(...)):
    # 检查文件类型
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="请上传图片文件")

    # 保存图片
    file_extension = os.path.splitext(image.filename)[1]
    filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join("uploads", filename)

    try:
        with open(file_path, "wb") as buffer:
            content = await image.read()
            buffer.write(content)

        # 这里可以集成真实的图片识别AI服务
        # 目前返回模拟分析结果
        analysis_result = {
            "health": "良好",
            "issues": ["叶片轻微发黄", "可能缺水"],
            "recommendations": [
                "适量增加浇水频率",
                "检查土壤湿度",
                "确保充足散射光照"
            ],
            # 注意：这里的URL路径可能需要根据主应用的静态文件挂载路径调整
            "image_url": f"/uploads/{filename}"
        }

        return {
            "success": True,
            "analysis": analysis_result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片处理失败: {str(e)}")


# 获取对话历史
@router.get("/conversations")
async def get_conversation_history():
    # 返回最近的10个对话
    recent_conversations = list(conversations_db.values())[-10:]
    for conv in recent_conversations:
        # 只返回基本信息，不包含完整消息历史
        conv["message_count"] = len(conv["messages"]) // 2
        if conv["messages"]:
            conv["last_message"] = conv["messages"][-1]["content"][:50] + "..." if len(
                conv["messages"][-1]["content"]) > 50 else conv["messages"][-1]["content"]
        else:
            conv["last_message"] = ""

    return {"conversations": recent_conversations}


# 获取特定对话详情
@router.get("/conversations/{conversation_id}")
async def get_conversation_detail(conversation_id: str):
    if conversation_id not in conversations_db:
        raise HTTPException(status_code=404, detail="对话不存在")

    return conversations_db[conversation_id]

# 注意：
# 1. 移除了 app.mount("/uploads", ...)，请在 main.py 中添加 app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
# 2. 移除了 root() 路由，通常由前端或主API文档接管