import datetime
from bson import ObjectId
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from create_prompt import create_prompt
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from pymongo.server_api import ServerApi

load_dotenv()

MONGO_URL = os.getenv("MONGODB_URL")
client = AsyncIOMotorClient(MONGO_URL)
db = client.get_database("test")
sessions_collection = db.get_collection("sessions")
messages_collection = db.get_collection("messages")

# Khởi tạo embeddings và mô hình
embeddings_model = OpenAIEmbeddings(model="text-embedding-3-large")
llm = ChatOpenAI(temperature=0.5, model='gpt-4o-mini', streaming=True)

# Kết nối ChromaDB
CHROMA_PATH = "./chroma_db"  # Thay bằng đường dẫn thư mục ChromaDB của bạn
vector_store = Chroma(
    collection_name="example_collection",
    embedding_function=embeddings_model,
    persist_directory=CHROMA_PATH,
)

# Hàm truy xuất từ ChromaDB
def retrieve_from_chromadb(question: str, top_k: int = 3):
    # Truy vấn ChromaDB
    retrieved_docs = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": top_k})
    print("retrieved_docs", retrieved_docs)
    results = retrieved_docs.invoke(question)
    return results

async def get_sessions(user):
    cursor = sessions_collection.find({"user_id": user["sub"]}).sort("created_at", -1)
    sessions = await cursor.to_list(length=None)
    for session in sessions:
        session["_id"] = str(session["_id"])
        session["messages"] = [str(message_id) for message_id in session["messages"]]
    return sessions

async def get_messages_by_session_id(session_id, user):
    session = await sessions_collection.find_one({"_id": ObjectId(session_id), "user_id": user["sub"]})
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên hội thoại")
    messages = await messages_collection.find({"session_id": ObjectId(session_id)}).to_list(None)
    if not messages:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin nhắn hoặc không có quyền truy cập")
    for message in messages:
        message["_id"] = str(message["_id"])
        message["session_id"] = str(message["session_id"])
    return messages

async def ask(request, user):
    question = request.message
    # history = request.history
    session_id = request.sessionId
    if session_id:
        session = await sessions_collection.find_one({"_id": ObjectId(session_id)})
        if not session:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên hội thoại")
    else:
        session = {
        "user_id": user["sub"],
        "messages": [],
        "created_at": datetime.datetime.now(),
        "updated_at": datetime.datetime.now(),
        }
        result = await sessions_collection.insert_one(session)
        session["_id"] = result.inserted_id

    # Lưu tin nhắn người dùng
    user_message = {
        "session_id": session["_id"],
        "content": question,
        "sender": "user",
        "timestamp": datetime.datetime.now(),
    }
    user_message_result = await messages_collection.insert_one(user_message)

    retrieved_docs = retrieve_from_chromadb(question)
    if not retrieved_docs:
        return {"message": "Không tìm thấy thông tin."}
    # Bước 4: Tạo prompt
    prompt = create_prompt(question, retrieved_docs, user["bloomLevel"])

    # Hàm stream phản hồi từ LLM
    async def stream_llm_response():
        try:
            chunks = []
            async for chunk in llm.astream(prompt):
                chunks.append(chunk.content)
                yield chunk.content
            # Sau khi stream kết thúc: lưu phản hồi vào MongoDB
            rag_message = {
                "session_id": session["_id"],
                "content": ''.join(chunks),
                "sender": "rag",
                "timestamp": datetime.datetime.now(),
            }
            rag_message_result = await messages_collection.insert_one(rag_message)

            # Cập nhật session
            await sessions_collection.update_one(
                {"_id": session["_id"]},
                {"$push": {
                    "messages": {
                        "$each": [user_message_result.inserted_id, rag_message_result.inserted_id]
                    }
                }}
            )
        except Exception as e:
            yield f"Lỗi khi tạo phản hồi: {str(e)}"
    response = StreamingResponse(stream_llm_response(), media_type="text/plain")
    response.headers["X-Session-Id"] = str(session["_id"])
    return response