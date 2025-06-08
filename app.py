import json
import os
from fastapi import Depends, FastAPI
from pydantic import BaseModel
import asyncio
from dotenv import load_dotenv
from ask import ask, get_sessions, get_messages_by_session_id
from check_talk import is_programming_question, is_small_talk
load_dotenv()
from auth import get_current_user
# Khởi tạo FastAPI
app = FastAPI()

# Định nghĩa input model
class QueryInput(BaseModel):
    question: str
    sessionId: str

@app.get("/api/chat/sessions")
async def getSessions(user: dict = Depends(get_current_user)):
    #lấy danh sách từ mới nhất đến cũ nhất
    return await get_sessions(user)


@app.get("/api/chat/messages/{session_id}")
async def get_messages(session_id: str, user: dict = Depends(get_current_user)):
    return await get_messages_by_session_id(session_id, user)

# Endpoint FastAPI
@app.post("/api/chat/message")
async def query_endpoint(request: QueryInput, user: dict = Depends(get_current_user)):
    # Bước 1: Kiểm tra small talk
    # if await is_small_talk(question):
    #     return {"message": "Xin chào, tôi là trợ lý lập trình. Tôi có thể giúp gì cho bạn?"}
    # if re.search(r'\b(xin chào|hello|hi|cảm ơn|bye)\b', question.lower()):
    #     return {"message": "Xin chào, tôi là trợ lý lập trình. Tôi có thể giúp gì cho bạn?"}
    # # Bước 2: Kiểm tra câu hỏi lập trình
    # if not await is_programming_question(question):
    #     return {"message": "Câu hỏi không liên quan đến lập trình C, vui lòng hỏi về lập trình."}

    # Bước 3: Truy xuất từ ChromaDB
    return await ask(request, user)
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))  # Mặc định cổng 8000 cho FastAPI
    uvicorn.run(app, host=os.getenv("HOST", "localhost"), port=port)

# Chạy ứng dụng: uvicorn app:app --reload