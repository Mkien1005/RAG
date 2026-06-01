import datetime
import os
from bson import ObjectId
from fastapi import FastAPI, HTTPException, Depends, Request, Response, status
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordBearer
import asyncio
from langchain_chroma import Chroma
from langchain_openai.embeddings import OpenAIEmbeddings
from check_topic import check_topic
from model import generate_course_structure, process_response_stream
from schema import ChatRequest, CourseRequest
from motor.motor_asyncio import AsyncIOMotorClient
from jose import JWTError, jwt
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
# Load biến môi trường từ file .env
load_dotenv()
MONGO_URL = os.getenv("MONGODB_URI")
ACCESS_KEY = os.getenv("ACCESS_KEY")
JWT_PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY").replace("\\n", "\n")
ALGORITHM = os.getenv("ALGORITHM", "RS256")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Khởi tạo FastAPI app
app = FastAPI()
# Cấu hình CORS
origins = os.getenv("ORIGINS").split(",")
# Khởi tạo vector store
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
vector_store = Chroma(
    collection_name="course",
    embedding_function=embeddings,
    persist_directory="course_db",
)
print(origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,     # Các nguồn được phép truy cập
    allow_credentials=True,    # Cho phép chia sẻ thông tin xác thực (cookie, header)
    allow_methods=["*"],       # Cho phép tất cả các phương thức HTTP (GET, POST, PUT, DELETE...)
    allow_headers=["*"],       # Cho phép tất cả các headers
    expose_headers=["x-session-id"]
)
client = AsyncIOMotorClient(MONGO_URL)
db = client.get_database("test")
sessions_collection = db.get_collection("sessions")
messages_collection = db.get_collection("messages")
courses_collection = db.get_collection("courses")
chapters_collection = db.get_collection("chapters")
sections_collection = db.get_collection("sections")
# Hàm kiểm tra API key
# Dependency for extracting and verifying JWT token
async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        # Decode and verify JWT token
        payload = jwt.decode(token, JWT_PUBLIC_KEY, algorithms=[ALGORITHM])
        request.state.user = payload  # Attach user payload to request.state
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Endpoint POST để stream câu trả lời
@app.post("/api/chat/message")
async def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    try:
        message = request.message
        history = request.history
        session_id = request.sessionId
        if session_id:
            print(session_id)
            session = await sessions_collection.find_one({"_id": ObjectId(session_id)})
            print(session)
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
            "content": message,
            "sender": "user",
            "timestamp": datetime.datetime.now(),
        }
        user_message_result = await messages_collection.insert_one(user_message)

        # Tạo generator stream + lưu dữ liệu sau khi kết thúc
        async def event_stream():
            try:
                chunks = []
                async for chunk in process_response_stream(user["gpa"], message, history):
                    chunks.append(chunk)
                    yield chunk

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
                print(f"Error in event_stream: {str(e)}")
                yield "OpenAI quota exceeded. Please contact to admin to request for more quota."
        response = StreamingResponse(event_stream(), media_type="text/plain")
        response.headers["X-Session-Id"] = str(session["_id"])
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.get("/api/chat/sessions")
async def get_sessions(user: dict = Depends(get_current_user)):
    #lấy danh sách từ mới nhất đến cũ nhất
    sessions = await sessions_collection.find({"user_id": user["sub"]}).sort("created_at", -1).to_list(None)
    for session in sessions:
        session["_id"] = str(session["_id"])
        session["messages"] = [str(message_id) for message_id in session["messages"]]
    return sessions

@app.get("/api/chat/messages/{session_id}")
async def get_messages(session_id: str, user: dict = Depends(get_current_user)):
    messages = await messages_collection.find({"session_id": ObjectId(session_id)}).to_list(None)
    for message in messages:
        message["_id"] = str(message["_id"])
        message["session_id"] = str(message["session_id"])
    return messages

@app.delete("/api/chat/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    await messages_collection.delete_many({"session_id": ObjectId(session_id)})
    await sessions_collection.delete_one({"_id": ObjectId(session_id)})
    return {"message": "Session deleted successfully"}

# @app.get("/api/chat/sessions/{session_id}")
# async def get_session(session_id: str, user: dict = Depends(get_current_user)):
#     session = await sessions_collection.find_one({"_id": ObjectId(session_id)})
#     session["_id"] = str(session["_id"])
#     session["messages"] = [str(message_id) for message_id in session["messages"]]  
#     return session
co = {
    "course_title": "Khóa học Lập trình C",
    "description": "Khóa học cung cấp kiến thức cơ bản và nâng cao về lập trình C, từ việc hiểu các thành phần ngôn ngữ đến việc sử dụng các cấu trúc điều khiển và lập trình hàm.",
    "chapters": [
        {
            "chapter_title": "Giới thiệu về Lập trình C",
            "chapter_description": "Chương này sẽ giới thiệu tổng quan về lập trình, các thuật ngữ cơ bản, và cấu trúc của một chương trình C."        
        },
        {
            "chapter_title": "Các thành phần trong Ngôn ngữ C",
            "chapter_description": "Chương này sẽ đi sâu vào các thành phần cơ bản của ngôn ngữ C, bao gồm từ khóa, tên biến, kiểu dữ liệu và cách khai báo biến."
        },
        {
            "chapter_title": "Cấu trúc điều khiển",
            "chapter_description": "Chương này sẽ trình bày các cấu trúc điều khiển như rẽ nhánh và lặp, giúp lập trình viên điều khiển luồng chương trình."
        },
        {
            "chapter_title": "Hàm trong Lập trình C",
            "chapter_description": "Chương này sẽ giải thích về hàm, cách khai báo và sử dụng hàm, cũng như khái niệm truyền tham số và đệ quy."       
        },
        {
            "chapter_title": "Kiểu dữ liệu Mảng",
            "chapter_description": "Chương này sẽ trình bày về kiểu dữ liệu mảng trong C, bao gồm mảng một chiều và mảng hai chiều."
        },
        {
            "chapter_title": "Kiểu dữ liệu Chuỗi Ký tự",
            "chapter_description": "Chương này sẽ khám phá khái niệm chuỗi ký tự và các thao tác cơ bản trên chuỗi trong ngôn ngữ C."
        },
        {
            "chapter_title": "Kiểu cấu trúc (struct)",
            "chapter_description": "Chương này sẽ giới thiệu về kiểu cấu trúc trong C, cách định nghĩa và sử dụng kiểu dữ liệu này."
        },
        {
            "chapter_title": "Con trỏ và Địa chỉ",
            "chapter_description": "Chương này sẽ trình bày về con trỏ, cách sử dụng con trỏ với biến và mảng, cũng như cấp phát bộ nhớ động."
        }
    ]
}
@app.post("/api/chat/generate-course")
async def generate_course(request: CourseRequest, user: dict = Depends(get_current_user)):
    try:
        topic = request.topic
        existing_course_id = check_topic(topic)
        if existing_course_id:
            existing_course = await courses_collection.find_one({
                "_id": ObjectId(existing_course_id)
            })
            print(existing_course)
            if existing_course:
                #check user_ids có chứa user["sub"] không
                if user["sub"] not in existing_course.get("user_ids", []):
                    existing_course["user_ids"].append(user["sub"])
                    await courses_collection.update_one({"_id": ObjectId(existing_course_id)}, {"$set": {"user_ids": existing_course["user_ids"]}})
                existing_course["_id"] = str(existing_course["_id"])
                #lấy chi tiết các chapter từ MongoDB để trả về trong course
                chapters = []
                for chapter_id in existing_course["chapters"]:
                    chapter = await chapters_collection.find_one({"_id": chapter_id})
                    if chapter:
                        sections = []
                        #lấy ra các section tương ứng với chapter_id
                        sections = await sections_collection.find({"chapter_id": chapter_id}).to_list(None)
                        if sections:
                            for section in sections:
                                section["_id"] = str(section["_id"])
                                sections.append(section)
                            chapter["sections"] = sections
                        chapter["_id"] = str(chapter["_id"])
                        chapters.append(chapter)
                existing_course["chapters"] = chapters
                return jsonable_encoder(existing_course)
        course_structure = generate_course_structure(topic)
        # course_structure = co
        print(1)
        if "error" in course_structure:
            raise HTTPException(status_code=400, detail=course_structure["error"])
                # 1. Lưu từng chapter vào DB và lấy danh sách _id
        chapter_ids = []
        chapters = []
        for chapter in course_structure["chapters"]:

            chapter_doc = {
                "title": chapter["chapter_title"],
                "description": chapter.get("chapter_description", ""),
                "sections": chapter.get("sections", []),
                "created_at": datetime.datetime.now(),
                "updated_at": datetime.datetime.now(),
            }
            result = await chapters_collection.insert_one(chapter_doc)
            chapter_doc["_id"] = str(result.inserted_id)
            chapter_ids.append(result.inserted_id)
            #lưu result vào chapters lọc lại id thành string
            chapters.append(chapter_doc)
            #lưu sections vào DB
            section_ids = []
            chapter_doc["sections"] = []
            for section in chapter_doc["sections"]:
                section_doc = {
                    "title": section["section_title"],
                    "description": section["section_description"],
                    "chapter_id": chapter_doc["_id"],
                    "created_at": datetime.datetime.now(),
                    "updated_at": datetime.datetime.now(),
                }
                result = await sections_collection.insert_one(section_doc)
                section_doc["_id"] = str(result.inserted_id)
                section_ids.append(result.inserted_id)
                chapter_doc["sections"].append(section_doc)
        # 2. Tạo course và lưu danh sách _id của chapters
        course = {
            "user_ids": [user["sub"]],
            "course_title": course_structure["course_title"],
            "description": course_structure["description"],
            "chapters": chapter_ids,
            "created_at": datetime.datetime.now(),
            "updated_at": datetime.datetime.now(),
        }
        # 3. Trả về course (convert ObjectId -> str)
        result = await courses_collection.insert_one(course)
        course["_id"] = str(result.inserted_id)
        vector_store.add_texts(texts=[course_structure["course_title"]], metadatas=[{"course_id": course["_id"]}])
                # Lấy chi tiết các chapter từ MongoDB để trả về trong course
        course["chapters"] = chapters

        return jsonable_encoder(course)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.get("/api/chat/courses/{course_id}")
async def get_courses(course_id: str, user: dict = Depends(get_current_user)):
    #lấy danh sách course từ DB 
    course = await courses_collection.find_one({"_id": ObjectId(course_id)})
    if course:
        course["_id"] = str(course["_id"])
        # Nếu user_ids không chứa user["sub"] thì thêm user["sub"] vào user_ids
        if user["sub"] not in course.get("user_ids", []):
            course["user_ids"].append(user["sub"])
            await courses_collection.update_one({"_id": ObjectId(course_id)}, {"$set": {"user_ids": course["user_ids"]}})
        # Convert ObjectId nếu chapter_id đang là string
        chapter_ids = [ObjectId(ch_id) if isinstance(ch_id, str) else ch_id for ch_id in course.get("chapters", [])]

        # Truy vấn danh sách chapters tương ứng
        chapters = await chapters_collection.find({"_id": {"$in": chapter_ids}}).to_list(None)
        
        # Chuyển ObjectId -> str để trả về
        for ch in chapters:
            ch["_id"] = str(ch["_id"])
            ch["user_id"] = str(ch.get("user_id", ""))

        # Thay thế danh sách chapters trong course
        course["chapters"] = chapters

    return course

@app.get("/api/chat/courses")
async def get_courses(user: dict = Depends(get_current_user)):
    #lấy danh sách course từ DB 
    courses = await courses_collection.find({"user_ids": user["sub"]}).to_list(None)
    for course in courses:
        course["_id"] = str(course["_id"])
        course["chapters"] = []
    return jsonable_encoder(courses)

@app.delete("/api/chat/courses/{course_id}")
async def delete_course(course_id: str, user: dict = Depends(get_current_user)):
    course = await courses_collection.find_one({"_id": ObjectId(course_id)})
    if course:
        course["user_ids"].remove(user["sub"])
        await courses_collection.update_one({"_id": ObjectId(course_id)}, {"$set": {"user_ids": course["user_ids"]}})
    return {"message": "Course deleted successfully"}

@app.head("/")
def check_server(response: Response):
    response.status_code = 200
    return

# Chạy ứng dụng FastAPI
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))  # Mặc định cổng 8000 cho FastAPI
    uvicorn.run(app, host=os.getenv("HOST", "localhost"), port=port)
