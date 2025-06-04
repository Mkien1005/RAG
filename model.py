import re
import json
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma

# Cấu hình
CHROMA_PATH = r"chroma_db1/chroma_db"

# Khởi tạo embeddings và mô hình
embeddings_model = OpenAIEmbeddings(model="text-embedding-3-large")
llm = ChatOpenAI(temperature=0.5, model='gpt-4o-mini')

# Kết nối với cơ sở dữ liệu Chroma
vector_store = Chroma(
    collection_name="example_collection",
    embedding_function=embeddings_model,
    persist_directory=CHROMA_PATH,
)

# Thiết lập retriever
# Trên 0.8
num_results = 3
retriever = vector_store.as_retriever(search_kwargs={'k': num_results})

results = vector_store.get()
metadatas = results["metadatas"]
# Trích xuất danh sách các heading (nếu có trường 'heading')
headings = [meta.get("heading") for meta in metadatas if "heading" in meta]
def get_instruction_by_gpa(gpa: float,use_gpa: bool) -> str:
    if not use_gpa:
        return "Hãy giải thích một cách dễ hiểu và chi tiết."
    if gpa < 6.0:
        return "Hãy giải thích từng bước một cách dễ hiểu như đang dạy người mới bắt đầu."
    elif gpa < 8.0:
        return "Hãy giải thích rõ ràng và đưa ra một vài ví dụ minh họa."
    else:
        return "Trả lời ngắn gọn, tập trung vào trọng tâm và bản chất vấn đề."
# kiểm tra small top(matching keyword, thêm prompt có phải small top hay không), kiểm tra có phải câu hỏi lập trình hay không, nếu không thì không trả lời
async def process_response_stream(student_gpa: float, message: str, history: list):
    docs = retriever.invoke(message)
    if not docs:
        yield "Tôi không có đủ dữ liệu để trả lời"
        return

    knowledge = "\n\n".join([doc.page_content for doc in docs])

    rag_prompt = f"""
Bạn là một trợ lý AI chuyên dạy lập trình cho sinh viên trường Đại học CNTT & Truyền thông (ICTU). Hãy trả lời bằng tiếng Việt, rõ ràng, dễ hiểu và bám sát kiến thức sau:

Tài liệu tham khảo:
{knowledge}

Sinh viên có trình độ học lực ở mức GPA: {student_gpa} (chỉ sử dụng để điều chỉnh độ khó của câu trả lời, không cần nhắc đến trong nội dung).
Câu hỏi của sinh viên:
"{message}"

Yêu cầu:
- Trả lời trực tiếp, không cần mở đầu xã giao.
- Không nhắc lại câu hỏi trong câu trả lời.
- GPA < 6.0: Giải thích đơn giản, ví dụ thực tế, tránh dùng thuật ngữ phức tạp.
- 6.0 ≤ GPA ≤ 8.0: Giải thích rõ ràng từng bước, có ví dụ lập trình cụ thể.
- GPA > 8.0: Trả lời chuyên sâu, dùng thuật ngữ học thuật và liên hệ kiến thức nâng cao.
- Nếu sinh viên hỏi đoạn mã: Giải thích từng dòng, nêu logic hoạt động, gợi ý viết tốt hơn.
- Nếu hỏi lý thuyết: Trình bày kèm ví dụ lập trình (ngôn ngữ C).
- Nếu câu hỏi chỉ là lời chào (ví dụ "xin chào", "hello", "hi"), chỉ cần chào lại thân thiện, không cần code, không cần giải thích, không cần tài liệu tham khảo.

Luôn động viên sinh viên học tiếp và đưa ra gợi ý học phù hợp nếu có thể.
"""


    async for response in llm.astream(rag_prompt):
        yield response.content


def generate_course_structure(topic):
    prompt = f"""
Tôi có danh sách các heading sau đây cho khóa học:
[DANH SÁCH CÁC HEADING]
{headings}

Từ các heading đã cho, lọc ra các heading liên quan đến chủ đề '{topic}' và tạo thành cấu trúc khóa học hoàn chỉnh với các chương (chapters) và các phần (sections). Mỗi chương nên chứa các phần nội dung liên quan đến nhau.

Output cần trả về theo định dạng JSON như sau:
{{
    "course_title": "Tên khóa học",
    "description": "Mô tả ngắn gọn về khóa học",
    "chapters": [
        {{
            "chapter_title": "Tên chương 1",
            "chapter_description": "Mô tả về chương",
            "sections": [
                {{
                    "section_title": "Tên phần 1",
                    "section_description": "Mô tả chi tiết các bước học, kiến thức cốt lõi cần nắm, phương pháp tiếp cận nội dung này. Nêu rõ mục tiêu đầu ra sau khi học phần này."
                }}
            ]
        }}
    ]
}}

Một số yêu cầu:
1. Sắp xếp các heading theo trình tự logic để việc học hiệu quả.
2. Đặt tên chương mang tính khái quát và bao trùm các phần bên trong.
3. Tạo mô tả ngắn gọn cho mỗi chương, giải thích chương đó sẽ đề cập đến những gì.
4. Mỗi section cần mô tả *cách học cụ thể*, ví dụ: học qua lý thuyết nào, làm ví dụ gì, cần thực hành ra sao, đạt được gì sau khi học xong.
5. Mỗi section_description tối thiểu 3 câu.

Nếu topic không liên quan đến các heading, hãy trả lời "Tôi không có đủ dữ liệu để trả lời".
"""
    response = llm.invoke(prompt)
    return parse_course_result(response.content)

def parse_course_result(raw_result: str):
    # 1. Xóa các ký hiệu Markdown ```json ... ```
    json_str = re.sub(r"^```json|```$", "", raw_result.strip(), flags=re.MULTILINE).strip()
    
    # 2. Parse chuỗi JSON thành dict
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        return {"error": "Invalid JSON format"}