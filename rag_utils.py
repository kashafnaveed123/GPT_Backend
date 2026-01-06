# from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
# # from langchain_pinecone import PineconeVectorStore
# from langchain_community.vectorstores import Pinecone
from langchain_core.documents import Document
from pathlib import Path
import re

def get_embedding_model():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

def load_md_to_chunks(md_path: str):
    """Load a Markdown file and split it into chunks."""
    
    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', text)  
    text = re.sub(r'[ \t]+', ' ', text) 
    emoji_pattern = re.compile(r'[\x00-\x1F\x7F]', flags=re.UNICODE)
    text = emoji_pattern.sub('', text)

       # Convert chunks to Document 
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=450, 
        chunk_overlap=100 , separators=["\n\n", "\n", ".", "!", "?"])  
    chunks = splitter.split_text(text) 
    doc_list = []
    for i, chunk in enumerate(chunks):
        metadata = {
            "source": "kashaf_profile",
            "chunk_no": i + 1,
            "filename": Path(md_path).name
        }
        doc_list.append(Document(page_content=chunk, metadata=metadata))
    
    return doc_list

def create_qdrant_vectorstore(docs, url, api_key, collection):
    embeddings = get_embedding_model()
    return QdrantVectorStore.from_documents(
        docs, embeddings, url=url, api_key=api_key, collection_name=collection
    )

# def create_pinecone_vectorstore(docs, api_key, index_name):
#     embeddings = get_embedding_model()
#     return PineconeVectorStore.from_documents(
#         docs, embeddings, index_name=index_name
#     )