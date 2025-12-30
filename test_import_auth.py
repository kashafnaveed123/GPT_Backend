# test_auth_imports.py
try:
    import passlib
    from passlib.context import CryptContext
    print("✅ passlib imported")
    
    from jose import jwt
    print("✅ python-jose imported")
    
    import motor.motor_asyncio
    print("✅ motor imported")
    
    import pymongo
    print("✅ pymongo imported")
    
    from pydantic import EmailStr
    print("✅ pydantic[email] imported")
    
    import google.generativeai as genai
    print("✅ google-generativeai imported")
    
    from langchain_google_genai import ChatGoogleGenerativeAI
    print("✅ langchain-google-genai imported")
    
    print("\n🎉 All authentication packages are working!")
    
except ImportError as e:
    print(f"❌ Error: {e}")