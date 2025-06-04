from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()

embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
vector_store = Chroma(
    collection_name="course",
    embedding_function=embeddings,
    persist_directory="course_db",
)
def check_topic(topic: str):
    #Nếu có topic trong vector store thì trả về topic đó
    embedding = embeddings.embed_query(topic)
    results = vector_store.similarity_search_by_vector(embedding, k=1)

    if results:
        return results[0].metadata.get("course_id")
    return None
    
    

