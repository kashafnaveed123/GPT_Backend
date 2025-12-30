"""
Enhanced Chat Management Service
Handles chat history and messages for authenticated users
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict
from fastapi import HTTPException
from pydantic import BaseModel
from bson import ObjectId
import re

# Import from your auth.py
from auth import db

# MongoDB Collections
chats_collection = db["chats"]
messages_collection = db["messages"]

# =======================
# Pydantic Models
# =======================
class MessageCreate(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[datetime] = None
    sources: Optional[List[dict]] = None

class ChatCreate(BaseModel):
    title: Optional[str] = "New Chat"

class ChatResponse(BaseModel):
    id: str
    user_id: str
    title: str
    preview: str
    created_at: datetime
    updated_at: datetime
    message_count: int

class MessageResponse(BaseModel):
    id: str
    chat_id: str
    role: str
    content: str
    timestamp: datetime
    sources: Optional[List[dict]] = None

# =======================
# Helper Functions
# =======================

def generate_smart_title(content: str, max_length: int = 50) -> str:
    """Generate a smart title from user message"""
    # Remove extra whitespace
    content = re.sub(r'\s+', ' ', content).strip()
    
    # If content is short enough, use it as is
    if len(content) <= max_length:
        return content
    
    # Try to break at sentence boundary
    sentences = re.split(r'[.!?]\s+', content)
    if sentences and len(sentences[0]) <= max_length:
        return sentences[0]
    
    # Try to break at word boundary
    truncated = content[:max_length]
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.7:  # If we can save at least 30% by breaking at word
        return truncated[:last_space] + "..."
    
    # Just truncate
    return truncated + "..."

def categorize_chat_by_date(chat_date: datetime) -> str:
    """Categorize chat into time periods (Today, Yesterday, Last 7 Days, etc.)"""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    last_7_days_start = today_start - timedelta(days=7)
    last_30_days_start = today_start - timedelta(days=30)
    
    if chat_date >= today_start:
        return "Today"
    elif chat_date >= yesterday_start:
        return "Yesterday"
    elif chat_date >= last_7_days_start:
        return "Last 7 Days"
    elif chat_date >= last_30_days_start:
        return "Last 30 Days"
    else:
        # Return month and year
        return chat_date.strftime("%B %Y")

# =======================
# Chat Management Functions
# =======================

async def create_chat(user_id: str, title: str = "New Chat", first_message: Optional[str] = None) -> dict:
    """
    Create a new chat for a user
    If first_message is provided, auto-generate title
    """
    # Auto-generate title if first message provided
    if first_message and title == "New Chat":
        title = generate_smart_title(first_message)
    
    chat_doc = {
        "user_id": str(user_id),
        "title": title,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "is_active": True,
        "message_count": 0,
        "is_pinned": False  # For future pinning feature
    }
    
    result = await chats_collection.insert_one(chat_doc)
    chat_doc["_id"] = result.inserted_id
    
    return {
        "id": str(chat_doc["_id"]),
        "user_id": chat_doc["user_id"],
        "title": chat_doc["title"],
        "preview": first_message[:100] if first_message else "",
        "date": chat_doc["created_at"].isoformat(),
        "category": categorize_chat_by_date(chat_doc["created_at"]),
        "created_at": chat_doc["created_at"].isoformat(),
        "updated_at": chat_doc["updated_at"].isoformat(),
        "message_count": 0,
        "is_pinned": False
    }

async def get_user_chats(user_id: str, include_archived: bool = False) -> Dict[str, List[dict]]:
    """
    Get all chats for a user, grouped by date categories
    Returns: {"Today": [...], "Yesterday": [...], "Last 7 Days": [...], etc.}
    """
    query = {"user_id": str(user_id), "is_active": True}
    if not include_archived:
        query["is_archived"] = {"$ne": True}
    
    chats = await chats_collection.find(query).sort("updated_at", -1).to_list(length=500)
    
    # Group chats by date category
    categorized_chats = {}
    
    for chat in chats:
        # Get first user message as preview
        first_message = await messages_collection.find_one(
            {"chat_id": str(chat["_id"]), "role": "user"},
            sort=[("timestamp", 1)]
        )
        
        # Get message count
        message_count = await messages_collection.count_documents(
            {"chat_id": str(chat["_id"])}
        )
        
        preview = ""
        if first_message:
            preview = first_message["content"][:100]
            if len(first_message["content"]) > 100:
                preview += "..."
        
        # Determine category
        category = categorize_chat_by_date(chat["updated_at"])
        
        chat_data = {
            "id": str(chat["_id"]),
            "user_id": chat["user_id"],
            "title": chat["title"],
            "preview": preview,
            "date": chat["updated_at"].isoformat(),
            "created_at": chat["created_at"].isoformat(),
            "updated_at": chat["updated_at"].isoformat(),
            "message_count": message_count,
            "is_pinned": chat.get("is_pinned", False),
            "is_archived": chat.get("is_archived", False)
        }
        
        # Add to appropriate category
        if category not in categorized_chats:
            categorized_chats[category] = []
        categorized_chats[category].append(chat_data)
    
    # Sort categories in order
    ordered_categories = ["Today", "Yesterday", "Last 7 Days", "Last 30 Days"]
    ordered_result = {}
    
    for cat in ordered_categories:
        if cat in categorized_chats:
            ordered_result[cat] = categorized_chats[cat]
    
    # Add remaining months
    for cat, chats_list in categorized_chats.items():
        if cat not in ordered_categories:
            ordered_result[cat] = chats_list
    
    return ordered_result

async def get_chat_messages(chat_id: str, user_id: str, limit: int = 1000) -> List[dict]:
    """
    Get all messages for a specific chat
    Returns messages in chronological order (oldest first)
    """
    # Verify chat belongs to user
    try:
        chat = await chats_collection.find_one({
            "_id": ObjectId(chat_id),
            "user_id": str(user_id)
        })
    except:
        chat = None
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found or access denied")
    
    messages = await messages_collection.find(
        {"chat_id": chat_id}
    ).sort("timestamp", 1).to_list(length=limit)
    
    return [
        {
            "id": str(msg["_id"]),
            "chat_id": msg["chat_id"],
            "role": msg["role"],
            "content": msg["content"],
            "timestamp": msg["timestamp"].isoformat(),
            "sources": msg.get("sources", [])
        }
        for msg in messages
    ]

async def add_message_to_chat(
    chat_id: str, 
    user_id: str, 
    role: str, 
    content: str,
    sources: Optional[List[dict]] = None,
    auto_title: bool = True
) -> dict:
    """
    Add a message to a chat
    Auto-generates title from first user message if enabled
    """
    # Verify chat belongs to user
    try:
        chat = await chats_collection.find_one({
            "_id": ObjectId(chat_id),
            "user_id": str(user_id)
        })
    except:
        chat = None
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found or access denied")
    
    message_doc = {
        "chat_id": chat_id,
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow(),
        "sources": sources or []
    }
    
    result = await messages_collection.insert_one(message_doc)
    
    # Update chat's updated_at timestamp and increment message count
    await chats_collection.update_one(
        {"_id": ObjectId(chat_id)},
        {
            "$set": {"updated_at": datetime.utcnow()},
            "$inc": {"message_count": 1}
        }
    )
    
    # Auto-generate title from first user message if still "New Chat"
    if auto_title and chat["title"] == "New Chat" and role == "user":
        # Check if this is the first user message
        message_count = await messages_collection.count_documents({
            "chat_id": chat_id,
            "role": "user"
        })
        
        if message_count == 1:  # This is the first user message
            new_title = generate_smart_title(content)
            await chats_collection.update_one(
                {"_id": ObjectId(chat_id)},
                {"$set": {"title": new_title}}
            )
    
    message_doc["_id"] = result.inserted_id
    
    return {
        "id": str(message_doc["_id"]),
        "chat_id": message_doc["chat_id"],
        "role": message_doc["role"],
        "content": message_doc["content"],
        "timestamp": message_doc["timestamp"].isoformat(),
        "sources": message_doc.get("sources", [])
    }

async def delete_chat(chat_id: str, user_id: str, permanent: bool = False) -> bool:
    """
    Delete a chat (soft delete by default, can do hard delete)
    """
    try:
        if permanent:
            # Hard delete: remove chat and all messages
            chat_result = await chats_collection.delete_one({
                "_id": ObjectId(chat_id),
                "user_id": str(user_id)
            })
            
            if chat_result.deleted_count > 0:
                # Delete all messages
                await messages_collection.delete_many({"chat_id": chat_id})
                return True
        else:
            # Soft delete: mark as inactive
            result = await chats_collection.update_one(
                {"_id": ObjectId(chat_id), "user_id": str(user_id)},
                {"$set": {"is_active": False, "deleted_at": datetime.utcnow()}}
            )
            return result.modified_count > 0
    except:
        return False

async def update_chat_title(chat_id: str, user_id: str, title: str) -> bool:
    """Update chat title"""
    try:
        result = await chats_collection.update_one(
            {"_id": ObjectId(chat_id), "user_id": str(user_id)},
            {"$set": {"title": title, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    except:
        return False

async def pin_chat(chat_id: str, user_id: str, pinned: bool = True) -> bool:
    """Pin or unpin a chat"""
    try:
        result = await chats_collection.update_one(
            {"_id": ObjectId(chat_id), "user_id": str(user_id)},
            {"$set": {"is_pinned": pinned, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    except:
        return False

async def archive_chat(chat_id: str, user_id: str, archived: bool = True) -> bool:
    """Archive or unarchive a chat"""
    try:
        result = await chats_collection.update_one(
            {"_id": ObjectId(chat_id), "user_id": str(user_id)},
            {"$set": {"is_archived": archived, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    except:
        return False

async def search_chats(user_id: str, query: str, limit: int = 20) -> List[dict]:
    """
    Search chats by title or message content
    """
    # Search in chat titles
    chat_matches = await chats_collection.find({
        "user_id": str(user_id),
        "is_active": True,
        "title": {"$regex": query, "$options": "i"}
    }).limit(limit).to_list(length=limit)
    
    # Search in messages
    message_matches = await messages_collection.find({
        "content": {"$regex": query, "$options": "i"}
    }).limit(limit).to_list(length=limit)
    
    # Get unique chat IDs
    chat_ids = set([str(chat["_id"]) for chat in chat_matches])
    chat_ids.update([msg["chat_id"] for msg in message_matches])
    
    # Fetch full chat details
    results = []
    for chat_id in chat_ids:
        try:
            chat = await chats_collection.find_one({
                "_id": ObjectId(chat_id),
                "user_id": str(user_id)
            })
            if chat:
                # Get message count
                message_count = await messages_collection.count_documents(
                    {"chat_id": chat_id}
                )
                
                results.append({
                    "id": str(chat["_id"]),
                    "title": chat["title"],
                    "created_at": chat["created_at"].isoformat(),
                    "updated_at": chat["updated_at"].isoformat(),
                    "message_count": message_count
                })
        except:
            continue
    
    return results

async def get_chat_statistics(user_id: str) -> dict:
    """Get statistics about user's chats"""
    total_chats = await chats_collection.count_documents({
        "user_id": str(user_id),
        "is_active": True
    })
    
    total_messages = await messages_collection.count_documents({})
    
    # Get messages in user's chats
    user_chats = await chats_collection.find(
        {"user_id": str(user_id), "is_active": True}
    ).to_list(length=1000)
    
    chat_ids = [str(chat["_id"]) for chat in user_chats]
    
    user_messages = await messages_collection.count_documents({
        "chat_id": {"$in": chat_ids}
    })
    
    return {
        "total_chats": total_chats,
        "total_messages": user_messages,
        "average_messages_per_chat": user_messages / total_chats if total_chats > 0 else 0
    }

# =======================
# Database Initialization
# =======================
async def init_chat_db():
    """Initialize chat-related database indexes"""
    try:
        # Create indexes for chats collection
        await chats_collection.create_index([("user_id", 1), ("is_active", 1)])
        await chats_collection.create_index([("user_id", 1), ("updated_at", -1)])
        await chats_collection.create_index([("user_id", 1), ("is_pinned", -1), ("updated_at", -1)])
        
        # Create indexes for messages collection
        await messages_collection.create_index([("chat_id", 1), ("timestamp", 1)])
        await messages_collection.create_index([("chat_id", 1), ("role", 1)])
        
        # Text index for search
        await chats_collection.create_index([("title", "text")])
        await messages_collection.create_index([("content", "text")])
        
        print("✅ Chat database indexes created")
    except Exception as e:
        print(f"⚠️ Chat database initialization warning: {e}")