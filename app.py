import json
import os
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
import asyncio
from dotenv import load_dotenv
from check_talk import is_programming_question, is_small_talk
from create_prompt import create_prompt
load_dotenv()
from auth import get_current_user

from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.authentication import (
    AuthenticationBackend, AuthCredentials, SimpleUser
)

# Khởi tạo FastAPI
app = FastAPI()
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

# Định nghĩa input model
class QueryInput(BaseModel):
    question: str

# Hàm truy xuất từ ChromaDB
def retrieve_from_chromadb(question: str, top_k: int = 3, threshold: float = 0.3):
    # Truy vấn ChromaDB
    # results = vector_store.similarity_search_with_score(question, k=top_k)
    
    # # Lọc kết quả với độ khớp > 0.8 (score là cosine similarity)
    # filtered_results = [
    # (doc.page_content, score) for doc, score in results if score > 0.95
    # ]
    # print(filtered_results)
    retrieved_docs = vector_store.as_retriever(search_type="mmr", search_kwargs={"k": 3})
    results = retrieved_docs.get_relevant_documents(question)
    print(results)
    return results
    # print(results)
    # 3. Lọc kết quả với độ tương đồng >= threshold
    filtered_results = [
        (doc.page_content, doc.metadata, score)
        for doc, score in results
        if score >= threshold
    ]
    # print(filtered_results)
    return filtered_results

# Endpoint FastAPI
@app.post("/api/chat/message")
async def query_endpoint(input: QueryInput):
# , user: dict = Depends(get_current_user)
    question = input.question
    # Bước 1: Kiểm tra small talk
    # if await is_small_talk(question):
    #     return {"message": "Xin chào, tôi là trợ lý lập trình. Tôi có thể giúp gì cho bạn?"}
    # if re.search(r'\b(xin chào|hello|hi|cảm ơn|bye)\b', question.lower()):
    #     return {"message": "Xin chào, tôi là trợ lý lập trình. Tôi có thể giúp gì cho bạn?"}
    # # Bước 2: Kiểm tra câu hỏi lập trình
    # if not await is_programming_question(question):
    #     return {"message": "Câu hỏi không liên quan đến lập trình C, vui lòng hỏi về lập trình."}

    # Bước 3: Truy xuất từ ChromaDB
    retrieved_docs = retrieve_from_chromadb(question)
    if not retrieved_docs:
        return {"message": "Không tìm thấy thông tin phù hợp trong giáo trình (độ khớp < 0.8)."}
    # Bước 4: Tạo prompt
    prompt = create_prompt(question, retrieved_docs, "understand")

    # Hàm stream phản hồi từ LLM
    async def stream_llm_response():
        try:
            async for chunk in llm.astream(prompt):
                yield chunk.content
        except Exception as e:
            yield f"Lỗi khi tạo phản hồi: {str(e)}"

    return StreamingResponse(stream_llm_response(), media_type="text/plain")
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))  # Mặc định cổng 8000 cho FastAPI
    uvicorn.run(app, host=os.getenv("HOST", "localhost"), port=port)

# Chạy ứng dụng: uvicorn main:app --reload