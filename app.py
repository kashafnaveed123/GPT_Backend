import warnings
warnings.filterwarnings("ignore")

import os
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import FastAPI, Form, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
from dotenv import load_dotenv
import asyncio
import traceback

# Langchain imports
# from langchain.vectorstores.base import VectorStore
# from langchain_core.vectorstores import VectorStore
# from langchain_community.vectorstores import VectorStore
from langchain_core.vectorstores import VectorStore
# from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI
import google.generativeai as genai

# Auth imports
from auth import (
    UserRegister, UserLogin, Token,
    register_user, login_user, get_current_user,
    get_user_profile, init_db, users_collection
)

# Import IMPROVED chat service
from chat_service import (
    create_chat,
    get_user_chats,
    get_chat_messages,
    add_message_to_chat,
    delete_chat,
    update_chat_title,
    pin_chat,
    archive_chat,
    search_chats,
    get_chat_statistics,
    init_chat_db
)

# Load environment variables
load_dotenv()

from rag_utils import (
    load_md_to_chunks,
    create_qdrant_vectorstore,
    # create_pinecone_vectorstore,
)

# =======================
# Environment Variables
# =======================
GEMINI_API_KEYS = os.getenv("GEMINI_API_KEYS", "")
GEMINI_API_KEY_LIST = [k.strip() for k in GEMINI_API_KEYS.split(",") if k.strip()]
print(f"🔑 Loaded {len(GEMINI_API_KEY_LIST)} Gemini API keys")

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "myChatbot")
# PINECONE_KEY = os.getenv("PINECONE_API_KEY")
# PINECONE_INDEX = os.getenv("PINECONE_INDEX", "demo-vectorstore")
API_KEY = os.getenv("API_KEY", "super-secret-token")

print("="*60)
print("🚀 Starting Enhanced Chatbot Backend with Chat History")
print(f"   Collection: {QDRANT_COLLECTION}")
print("="*60)

# =======================
# Query Limit Configuration
# =======================
AUTHENTICATED_QUERY_LIMIT = 5
UNAUTHENTICATED_QUERY_LIMIT = 3
LIMIT_RESET_HOURS = 24

# In-memory storage for non-authenticated users (IP-based)
ip_query_limits = defaultdict(lambda: {"count": 0, "reset_time": datetime.utcnow() + timedelta(hours=LIMIT_RESET_HOURS)})

print(f"📊 Query Limits: Authenticated={AUTHENTICATED_QUERY_LIMIT}, Public={UNAUTHENTICATED_QUERY_LIMIT}")

# =======================
# 🔥 API KEY ROTATION LOGIC
# =======================
current_key_index = 0

def get_next_api_key():
    """Get next API key in rotation"""
    global current_key_index
    if not GEMINI_API_KEY_LIST:
        return None
    
    key = GEMINI_API_KEY_LIST[current_key_index]
    current_key_index = (current_key_index + 1) % len(GEMINI_API_KEY_LIST)
    return key

def try_all_keys_for_genai_call(prompt: str, max_attempts: int = None):
    """Try calling Gemini API with all available keys until one succeeds"""
    if max_attempts is None:
        max_attempts = len(GEMINI_API_KEY_LIST)
    
    last_error = None
    
    for attempt in range(max_attempts):
        api_key = get_next_api_key()
        if not api_key:
            raise Exception("No API keys available")
        
        try:
            print(f"🔑 Attempt {attempt + 1}/{max_attempts} with key: {api_key[:10]}...")
            
            genai.configure(api_key=api_key)
            
            direct_model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                generation_config={
                    'temperature': 0.3,
                    'max_output_tokens': 2048,
                }
            )
            
            response = direct_model.generate_content(prompt)
            answer = response.text.strip()
            
            print(f"✅ Success with key {attempt + 1}")
            return answer
            
        except Exception as e:
            last_error = e
            print(f"❌ Key {attempt + 1} failed: {str(e)[:100]}")
            
            if attempt == max_attempts - 1:
                raise Exception(f"All {max_attempts} API keys failed. Last error: {str(last_error)}")
            
            continue
    
    raise Exception(f"Failed after {max_attempts} attempts")

# =======================
# Configure Initial Gemini
# =======================
if not GEMINI_API_KEY_LIST:
    print("⚠️ WARNING: GEMINI_API_KEYS not found in .env file!")
    llm = None
else:
    print(f"✅ Gemini API Keys loaded: {len(GEMINI_API_KEY_LIST)} keys")
    try:
        genai.configure(api_key=GEMINI_API_KEY_LIST[0])
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.3,
            max_retries=2,
            max_output_tokens=1024,
            google_api_key=GEMINI_API_KEY_LIST[0]
        )
        print(f"✅ Gemini initialized with first key")
    except Exception as e:
        print(f"⚠️ Initial LLM setup failed: {e}")
        llm = None

# =======================
# Global Variables
# =======================
VECTOR_STORE: Optional[VectorStore] = None
LOCAL_QDRANT_PATH = Path("local_qdrant")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# =======================
# Helper Functions for Query Limits
# =======================
def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"

async def check_authenticated_user_limit(user_id: str) -> dict:
    """Check if authenticated user has exceeded query limit"""
    from bson import ObjectId
    
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
    except:
        user = await users_collection.find_one({"_id": user_id})
    
    if not user:
        return {"allowed": False, "message": "User not found"}
    
    query_count = user.get("query_count", 0)
    last_reset = user.get("limit_reset_time")
    
    current_time = datetime.utcnow()
    if not last_reset or current_time > last_reset:
        try:
            await users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "query_count": 0,
                        "limit_reset_time": current_time + timedelta(hours=LIMIT_RESET_HOURS)
                    }
                }
            )
        except:
            await users_collection.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "query_count": 0,
                        "limit_reset_time": current_time + timedelta(hours=LIMIT_RESET_HOURS)
                    }
                }
            )
        query_count = 0
        last_reset = current_time + timedelta(hours=LIMIT_RESET_HOURS)
    
    if query_count >= AUTHENTICATED_QUERY_LIMIT:
        time_until_reset = last_reset - current_time if last_reset else timedelta(0)
        hours_remaining = max(0, int(time_until_reset.total_seconds() / 3600))
        
        return {
            "allowed": False,
            "message": f"Daily query limit ({AUTHENTICATED_QUERY_LIMIT}) reached. Resets in {hours_remaining} hours.",
            "limit": AUTHENTICATED_QUERY_LIMIT,
            "current": query_count,
            "reset_in_hours": hours_remaining
        }
    
    return {
        "allowed": True,
        "limit": AUTHENTICATED_QUERY_LIMIT,
        "current": query_count,
        "remaining": AUTHENTICATED_QUERY_LIMIT - query_count
    }

def check_unauthenticated_user_limit(ip_address: str) -> dict:
    """Check if non-authenticated user (by IP) has exceeded query limit"""
    current_time = datetime.utcnow()
    ip_data = ip_query_limits[ip_address]
    
    if current_time > ip_data["reset_time"]:
        ip_data["count"] = 0
        ip_data["reset_time"] = current_time + timedelta(hours=LIMIT_RESET_HOURS)
    
    if ip_data["count"] >= UNAUTHENTICATED_QUERY_LIMIT:
        time_until_reset = ip_data["reset_time"] - current_time
        hours_remaining = max(0, int(time_until_reset.total_seconds() / 3600))
        
        return {
            "allowed": False,
            "message": f"Query limit ({UNAUTHENTICATED_QUERY_LIMIT}) reached. Please login for more queries or wait {hours_remaining} hours.",
            "limit": UNAUTHENTICATED_QUERY_LIMIT,
            "current": ip_data["count"],
            "reset_in_hours": hours_remaining
        }
    
    return {
        "allowed": True,
        "limit": UNAUTHENTICATED_QUERY_LIMIT,
        "current": ip_data["count"],
        "remaining": UNAUTHENTICATED_QUERY_LIMIT - ip_data["count"]
    }

async def increment_query_count(user_id: str = None, ip_address: str = None):
    """Increment query count for user or IP"""
    if user_id:
        from bson import ObjectId
        try:
            await users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$inc": {"query_count": 1}}
            )
        except:
            await users_collection.update_one(
                {"_id": user_id},
                {"$inc": {"query_count": 1}}
            )
    elif ip_address:
        ip_query_limits[ip_address]["count"] += 1

# =======================
# Load Vectorstore
# =======================
def load_existing_vectorstore():
    global VECTOR_STORE
    
    try:
        if QDRANT_URL and QDRANT_API_KEY:
            print(f"🔗 Connecting to remote Qdrant: {QDRANT_URL}")
            client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
            VECTOR_STORE = QdrantVectorStore(
                embedding=embeddings,
                client=client,
                collection_name=QDRANT_COLLECTION,
            )
            print(f"✅ Connected to Qdrant: {QDRANT_COLLECTION}")
            return

        if LOCAL_QDRANT_PATH.exists():
            print(f"📂 Loading local Qdrant from: {LOCAL_QDRANT_PATH}")
            local_client = QdrantClient(path=str(LOCAL_QDRANT_PATH))
            VECTOR_STORE = QdrantVectorStore(
                embedding=embeddings,
                client=local_client,
                collection_name=QDRANT_COLLECTION,
            )
            print(f"✅ Loaded local Qdrant")
            return

        print("⚠️ No vectorstore found. Run /ingest_local to create one.")

    except Exception as e:
        print(f"❌ Vectorstore load failed: {e}")
        traceback.print_exc()

# =======================
# FastAPI Initialization
# =======================
@asynccontextmanager
async def lifespan(app):
    print("📦 Loading vectorstore...")
    load_existing_vectorstore()
    print("🔐 Initializing database...")
    await init_db()
    print("💬 Initializing chat database...")
    await init_chat_db() 
    print("✅ Startup complete\n")
    yield
    print("\n👋 Shutting down...")

app = FastAPI(
    title="Enhanced Personal Chatbot Backend",
    version="4.0",
    description="ChatGPT-like chat history with authentication and query limits",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =======================
# AUTHENTICATION ROUTES
# =======================
@app.post("/auth/register", response_model=Token)
async def register(user_data: UserRegister):
    """Register a new user"""
    print(f"\n📝 New user registration: {user_data.email}")
    return await register_user(user_data)

@app.post("/auth/login", response_model=Token)
async def login(user_data: UserLogin):
    """Login user and return JWT token"""
    print(f"\n🔐 User login: {user_data.email}")
    return await login_user(user_data)

@app.get("/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    return await get_user_profile(str(current_user["_id"]))

@app.get("/auth/verify")
async def verify_token(current_user: dict = Depends(get_current_user)):
    """Verify if token is valid"""
    return {
        "valid": True,
        "user_id": str(current_user["_id"]),
        "email": current_user["email"]
    }

# =======================
# Internal Query Function
# =======================
async def query_rag_internal(
    q: str, 
    k: int = 1, 
    user_id: Optional[str] = None, 
    ip_address: Optional[str] = None,
    chat_id: Optional[str] = None
):
    """Internal query function with query limit checking and chat history"""
    print(f"\n{'='*60}")
    print(f"🔍 Processing Query: '{q}'")
    if user_id:
        print(f"👤 Authenticated User ID: {user_id}")
        if chat_id:
            print(f"💬 Chat ID: {chat_id}")
    else:
        print(f"🌐 Non-authenticated IP: {ip_address}")
    print(f"{'='*60}")
    
    global VECTOR_STORE
    
    try:
        # Check query limits
        if user_id:
            limit_check = await check_authenticated_user_limit(str(user_id))
        elif ip_address:
            limit_check = check_unauthenticated_user_limit(ip_address)
        else:
            return {
                "answer": "Unable to process request.",
                "sources": [],
                "error": "No user identification"
            }
        
        if not limit_check["allowed"]:
            print(f"❌ Query limit exceeded")
            return {
                "answer": limit_check["message"],
                "sources": [],
                "limit_exceeded": True,
                "limit_info": limit_check
            }
        
        print(f"✅ Query limit check passed: {limit_check['current']}/{limit_check['limit']}")
        
        if VECTOR_STORE is None:
            print("❌ VECTOR_STORE is None")
            return {
                "answer": "Knowledge base not initialized.",
                "sources": []
            }

        print(f"📚 Searching vectorstore...")
        try:
            docs = VECTOR_STORE.similarity_search(q, k=k)
            print(f"📄 Retrieved {len(docs)} documents")
        except Exception as search_error:
            print(f"❌ Search error: {search_error}")
            traceback.print_exc()
            return {
                "answer": "Error searching the knowledge base.",
                "sources": []
            }
        
        if not docs:
            print("⚠️ No documents found")
            return {
                "answer": "I don't have enough information to answer this question.",
                "sources": []
            }

        context = "\n\n".join([doc.page_content[:500] for doc in docs])
        print(f"📝 Context length: {len(context)} chars")

        prompt = f"""You are answering as Kashaf Naveed — a professional MERN + AI Developer.
Answer clearly, concisely and professionally in 3-4 sentences.

Context:
{context}

Question: {q}

Answer:"""
        
        print(f"🤖 Calling Gemini API with key rotation...")
        try:
            answer = await asyncio.to_thread(try_all_keys_for_genai_call, prompt)
            print(f"✅ Response received")
            print(f"📏 Answer length: {len(answer)} chars")
            
        except Exception as llm_error:
            print(f"❌ All API keys failed: {llm_error}")
            traceback.print_exc()
            answer = "I encountered an error while processing your question."
        
        if not answer:
            answer = "I'm Kashaf's AI assistant — I may not have this detail, but I can help you explore it."
        
        # Increment query count AFTER successful query
        await increment_query_count(user_id=str(user_id) if user_id else None, ip_address=ip_address)
        
        sources = [
            {
                "page_no": doc.metadata.get("chunk_no", "N/A"),
                "source": doc.metadata.get("source", "Unknown"),
                # "file_name": doc.metadata.get("filename", "Unknown"),
                "snippet": doc.page_content[:200] + "...",
            }
            for doc in docs
        ]

        # ✨ SAVE TO CHAT HISTORY (only for authenticated users with chat_id)
        if user_id and chat_id:
            try:
                # Save user message
                await add_message_to_chat(
                    chat_id=chat_id,
                    user_id=str(user_id),
                    role="user",
                    content=q,
                    auto_title=True  # Auto-generate title from first message
                )
                
                # Save assistant response
                await add_message_to_chat(
                    chat_id=chat_id,
                    user_id=str(user_id),
                    role="assistant",
                    content=answer,
                    sources=sources,
                    auto_title=False  # Don't update title from assistant messages
                )
                print(f"💾 Messages saved to chat history")
            except Exception as save_error:
                print(f"⚠️ Failed to save to chat history: {save_error}")

        print(f"✅ Query processed successfully\n")
        return {
            "answer": answer,
            "sources": sources,
            "limit_info": {
                "current": limit_check["current"] + 1,
                "limit": limit_check["limit"],
                "remaining": limit_check["remaining"] - 1
            },
            "chat_id": chat_id, 
            "messages_saved": True if (user_id and chat_id) else False
        }
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        traceback.print_exc()
        return {
            "answer": f"An error occurred: {str(e)}",
            "sources": []
        }

# =======================
# CHATBOT QUERY ROUTES
# =======================
@app.post("/query")
async def query_rag(
    request: Request,
    q: str = Form(...),
    k: int = Form(1),
    chat_id: Optional[str] = Form(None), 
    current_user: dict = Depends(get_current_user)
):
    """Protected query endpoint - requires authentication"""
    user_id = current_user.get("_id")
    return await query_rag_internal(q, k, user_id=user_id, chat_id=chat_id)

@app.post("/api/query")
async def api_query_rag(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """API query endpoint - requires authentication"""
    try:
        body = await request.json()
        q = body.get("q")
        k = int(body.get("k", 1))
        chat_id = body.get("chat_id")
        if not q:
            raise HTTPException(status_code=400, detail="Missing 'q' parameter")
        
        user_id = current_user.get("_id")
        result = await query_rag_internal(q, k, user_id=user_id, chat_id=chat_id)
        return JSONResponse(result)
    
    except Exception as e:
        print(f"❌ API query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =======================
# PUBLIC QUERY ROUTES
# =======================
@app.post("/query/public")
async def query_rag_public(
    request: Request,
    q: str = Form(...),
    k: int = Form(1)
):
    """Public query endpoint - no authentication required, IP-based limits"""
    ip_address = get_client_ip(request)
    print(f"🌐 Public query from IP: {ip_address}")
    return await query_rag_internal(q, k, ip_address=ip_address)

@app.post("/api/query/public")
async def api_query_rag_public(request: Request):
    """Public API query endpoint - no authentication required"""
    try:
        body = await request.json()
        q = body.get("q")
        k = int(body.get("k", 1))
        
        if not q:
            raise HTTPException(status_code=400, detail="Missing 'q' parameter")
        
        ip_address = get_client_ip(request)
        print(f"🌐 Public API query from IP: {ip_address}")
        result = await query_rag_internal(q, k, ip_address=ip_address)
        return JSONResponse(result)
    
    except Exception as e:
        print(f"❌ API query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =======================
# ENHANCED CHAT MANAGEMENT ROUTES
# =======================

@app.post("/chats/create")
async def create_new_chat(
    title: Optional[str] = Form("New Chat"),
    first_message: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new chat
    Auto-generates title if first_message is provided
    """
    user_id = str(current_user.get("_id"))
    return await create_chat(user_id, title, first_message)

@app.get("/chats")
async def list_chats(
    include_archived: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all chats for current user, grouped by date
    Returns: {"Today": [...], "Yesterday": [...], "Last 7 Days": [...], etc.}
    """
    user_id = str(current_user.get("_id"))
    return await get_user_chats(user_id, include_archived)

@app.get("/chats/{chat_id}/messages")
async def get_messages(
    chat_id: str,
    limit: int = 1000,
    current_user: dict = Depends(get_current_user)
):
    """Get all messages in a chat"""
    user_id = str(current_user.get("_id"))
    return await get_chat_messages(chat_id, user_id, limit)

@app.delete("/chats/{chat_id}")
async def remove_chat(
    chat_id: str,
    permanent: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Delete a chat (soft delete by default, permanent if specified)"""
    user_id = str(current_user.get("_id"))
    success = await delete_chat(chat_id, user_id, permanent)
    if success:
        return {"message": "Chat deleted successfully", "permanent": permanent}
    raise HTTPException(status_code=404, detail="Chat not found")

@app.put("/chats/{chat_id}/title")
async def rename_chat(
    chat_id: str,
    title: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Update chat title"""
    user_id = str(current_user.get("_id"))
    success = await update_chat_title(chat_id, user_id, title)
    if success:
        return {"message": "Chat title updated successfully", "title": title}
    raise HTTPException(status_code=404, detail="Chat not found")

@app.put("/chats/{chat_id}/pin")
async def toggle_pin_chat(
    chat_id: str,
    pinned: bool = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Pin or unpin a chat"""
    user_id = str(current_user.get("_id"))
    success = await pin_chat(chat_id, user_id, pinned)
    if success:
        return {"message": f"Chat {'pinned' if pinned else 'unpinned'} successfully"}
    raise HTTPException(status_code=404, detail="Chat not found")

@app.put("/chats/{chat_id}/archive")
async def toggle_archive_chat(
    chat_id: str,
    archived: bool = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Archive or unarchive a chat"""
    user_id = str(current_user.get("_id"))
    success = await archive_chat(chat_id, user_id, archived)
    if success:
        return {"message": f"Chat {'archived' if archived else 'unarchived'} successfully"}
    raise HTTPException(status_code=404, detail="Chat not found")

@app.get("/chats/search")
async def search_user_chats(
    q: str,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Search chats by title or content"""
    user_id = str(current_user.get("_id"))
    return await search_chats(user_id, q, limit)

@app.get("/chats/statistics")
async def get_statistics(current_user: dict = Depends(get_current_user)):
    """Get chat statistics for current user"""
    user_id = str(current_user.get("_id"))
    return await get_chat_statistics(user_id)

# =======================
# QUERY LIMIT INFO ROUTES
# =======================
@app.get("/query/limits")
async def get_query_limits(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Get query limit information for authenticated user"""
    user_id = str(current_user.get("_id"))
    limit_info = await check_authenticated_user_limit(user_id)
    return limit_info

@app.get("/query/limits/public")
async def get_query_limits_public(request: Request):
    """Get query limit information for non-authenticated user"""
    ip_address = get_client_ip(request)
    limit_info = check_unauthenticated_user_limit(ip_address)
    return limit_info

# =======================
# ADMIN ROUTES
# =======================
def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Legacy API key verification for admin routes"""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

@app.post("/ingest_local", dependencies=[Depends(verify_api_key)])
async def ingest_local(use_qdrant: bool = True):
    """Ingest Markdown files - admin only"""
    global VECTOR_STORE

    folder_path = Path("data")
    md_files = list(folder_path.glob("*.md"))
    
    if not md_files:
        raise HTTPException(status_code=400, detail="No markdown files in /data folder")

    print(f"📂 Found {len(md_files)} markdown files")
    
    all_docs = []
    for md_file in md_files:
        docs = load_md_to_chunks(str(md_file))
        all_docs.extend(docs)
        print(f"   ✅ {md_file.name}: {len(docs)} chunks")

    if use_qdrant and QDRANT_URL and QDRANT_API_KEY:
        VECTOR_STORE = QdrantVectorStore.from_documents(
            documents=all_docs,
            embedding=embeddings,
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            collection_name=QDRANT_COLLECTION,
        )
        store_type = "Qdrant"
    else:
        print("⚠️ Qdrant config missing, skipping Qdrant ingestion.")
        # VECTOR_STORE = create_pinecone_vectorstore(all_docs, PINECONE_KEY, PINECONE_INDEX)
        # store_type = "Pinecone"

    print(f"✅ Ingested {len(all_docs)} docs into {store_type}")
    
    return {
        "status": "ok",
        "indexed_docs": len(all_docs),
        "vector_store": store_type
    }

# =======================
# PUBLIC ROUTES
# =======================
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "backend": "Enhanced Chatbot v4.0 with Chat History",
        "vectorstore_loaded": VECTOR_STORE is not None,
        "api_keys_available": len(GEMINI_API_KEY_LIST),
        "query_limits": {
            "authenticated": AUTHENTICATED_QUERY_LIMIT,
            "public": UNAUTHENTICATED_QUERY_LIMIT,
            "reset_hours": LIMIT_RESET_HOURS
        }
    }

@app.get("/")
async def root():
    """Root endpoint with API documentation"""
    return {
        "message": "Enhanced Personal Chatbot Backend - ChatGPT-like Features",
        "version": "4.0",
        "status": "running",
        "features": [
            "🔐 User authentication with JWT",
            "💬 Chat history with auto-title generation",
            "📅 Date-based chat categorization",
            "📌 Pin/Archive chats",
            "🔍 Search functionality",
            "⚡ Query rate limiting"
        ],
        "query_limits": {
            "authenticated_users": f"{AUTHENTICATED_QUERY_LIMIT} queries per day",
            "public_users": f"{UNAUTHENTICATED_QUERY_LIMIT} queries per day"
        },
        "endpoints": {
            "auth": {
                "register": "POST /auth/register",
                "login": "POST /auth/login",
                "profile": "GET /auth/me",
                "verify": "GET /auth/verify"
            },
            "chatbot": {
                "query_authenticated": "POST /query (requires auth + chat_id)",
                "api_query_authenticated": "POST /api/query (requires auth + chat_id)",
                "query_public": "POST /query/public (no auth, 3 queries/day)",
                "api_query_public": "POST /api/query/public (no auth, 3 queries/day)"
            },
            "chats": {
                "create": "POST /chats/create",
                "list": "GET /chats (grouped by date)",
                "messages": "GET /chats/{chat_id}/messages",
                "delete": "DELETE /chats/{chat_id}?permanent=false",
                "rename": "PUT /chats/{chat_id}/title",
                "pin": "PUT /chats/{chat_id}/pin",
                "archive": "PUT /chats/{chat_id}/archive",
                "search": "GET /chats/search?q=query",
                "statistics": "GET /chats/statistics"
            },
            "limits": {
                "check_authenticated": "GET /query/limits",
                "check_public": "GET /query/limits/public"
            },
            "admin": {
                "ingest": "POST /ingest_local (requires API key)",
                "health": "GET /health"
            }
        }
    }