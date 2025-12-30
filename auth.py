"""
Authentication Module for Personal Chatbot
Handles user registration, login, and JWT token management
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
import os
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# =======================
# Configuration
# =======================
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb+srv://222kashafnaveed:kashafnaveed@cluster0.vdp24.mongodb.net/Chatbot?retryWrites=true&w=majority")
DB_NAME = os.getenv("DB_NAME", "Chatbot")

# =======================
# Password Hashing
# =======================
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")
security = HTTPBearer()

# =======================
# Database Connection
# =======================
try:
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DB_NAME]
    users_collection = db["users"]
    print(f"✅ MongoDB connection initialized: {MONGODB_URL}")
except Exception as e:
    print(f"❌ MongoDB connection error: {e}")
    raise

# =======================
# Pydantic Models
# =======================
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    created_at: datetime
    is_active: bool = True

# =======================
# Helper Functions
# =======================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    # bcrypt has 72 byte limit, truncate if needed
    if len(password.encode('utf-8')) > 72:
        password = password[:72]
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_user_by_email(email: str):
    """Get user from database by email"""
    return await users_collection.find_one({"email": email.lower()})

async def get_user_by_id(user_id: str):
    """Get user from database by ID"""
    try:
        return await users_collection.find_one({"_id": ObjectId(user_id)})
    except:
        return None

# =======================
# Authentication Dependency
# =======================
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Dependency to get current authenticated user from JWT token
    Usage: current_user = Depends(get_current_user)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    user = await get_user_by_id(user_id)
    
    if user is None:
        raise credentials_exception
    
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user

# =======================
# Auth Functions
# =======================
async def register_user(user_data: UserRegister) -> dict:
    """Register a new user"""
    
    # Check if user already exists
    existing_user = await get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    
    new_user = {
        "email": user_data.email.lower(),
        "full_name": user_data.full_name,
        "hashed_password": hashed_password,
        "created_at": datetime.utcnow(),
        "is_active": True,
        "query_count": 0,  # Initialize query count
        "limit_reset_time": datetime.utcnow() + timedelta(hours=24),  # Set initial reset time
        "last_login": None
    }
    
    result = await users_collection.insert_one(new_user)
    new_user["_id"] = result.inserted_id
    
    # Create access token
    access_token = create_access_token(
        data={"sub": str(new_user["_id"]), "email": new_user["email"]}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(new_user["_id"]),
            "email": new_user["email"],
            "full_name": new_user["full_name"],
            "created_at": new_user["created_at"].isoformat()
        }
    }

async def login_user(user_data: UserLogin) -> dict:
    """Login user and return JWT token"""
    
    # Get user from database
    user = await get_user_by_email(user_data.email)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Verify password
    if not verify_password(user_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Update last login
    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )
    
    # Create access token
    access_token = create_access_token(
        data={"sub": str(user["_id"]), "email": user["email"]}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "created_at": user["created_at"].isoformat()
        }
    }

async def get_user_profile(user_id: str) -> dict:
    """Get user profile information"""
    user = await get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "full_name": user["full_name"],
        "created_at": user["created_at"].isoformat(),
        "last_login": user.get("last_login").isoformat() if user.get("last_login") else None,
        "query_count": user.get("query_count", 0),
        "is_active": user.get("is_active", True)
    }

# =======================
# Database Initialization
# =======================
async def init_db():
    """Initialize database with indexes"""
    try:
        # Test MongoDB connection first
        await client.admin.command('ping')
        
        # Create unique index on email
        await users_collection.create_index("email", unique=True)
        print("✅ Database indexes created")
    except Exception as e:
        print(f"⚠️ MongoDB connection failed: {e}")
        print("⚠️ Running without MongoDB - authentication will not work!")
        print("💡 Please start MongoDB or use MongoDB Atlas")