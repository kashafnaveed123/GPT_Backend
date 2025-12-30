# # test_fixed.py
# import requests
# import time

# BASE_URL = "http://127.0.0.1:8000"
# headers = {"X-API-Key": "super-secret-token"}

# def test_ingest():
#     print("🚀 Ingesting documents...")
#     resp = requests.post(f"{BASE_URL}/ingest_local", headers=headers)
#     print("Ingest Response:", resp.json())
#     return resp.status_code == 200

# def test_query():
#     questions = [
#         "Who is kashaf?",
#         # "what is your specialities?",
#         # "Give me your project list",
#     ]
    
#     for question in questions:
#         print(f"\n❓ Question: {question}")
#         try:
#             resp = requests.post(f"{BASE_URL}/query", headers=headers, data={"q": question, "k": 2})
#             if resp.status_code == 200:
#                 result = resp.json()
#                 print("✅ Answer:", result["answer"])
#                 print("📚 Sources:", len(result["sources"]))
#                 if result["sources"]:
#                     print("📄 First source snippet:", result["sources"][0]["snippet"])
#             else:
#                 print("❌ Failed:", resp.text)
#         except Exception as e:
#             print(f"❌ Exception: {e}")

# if __name__ == "__main__":
#     time.sleep(2)
#     time.sleep(1)
#     if test_ingest():
#         time.sleep(2)
#         test_query()

# # test_new_key.py
# import os
# from dotenv import load_dotenv
# import google.generativeai as genai

# load_dotenv()
# key = os.getenv("GEMINI_API_KEY")

# print(f"API Key: {key[:10]}...")
# print(f"Length: {len(key)}")
# print(f"Starts with AIzaSy: {key.startswith('AIzaSyDjR2_-MNeULeB8MlUg_BVpsMINxt5WV68')}")

# # Test API
# genai.configure(api_key=key)
# model = genai.GenerativeModel('gemini-pro')
# response = model.generate_content("Say hello in one word")
# print(f"✅ Response: {response.text}")


# # test_rest_api.py
# import os
# import requests
# from dotenv import load_dotenv

# load_dotenv()
# key = os.getenv("GEMINI_API_KEY")

# print("="*60)
# print("🧪 Testing Gemini API via REST")
# print("="*60)
# print(f"API Key: {key[:15]}...")
# print()

# # Test 1: List Models
# print("📋 Test 1: List available models")
# url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"

# try:
#     response = requests.get(url)
#     print(f"Status: {response.status_code}")
    
#     if response.status_code == 200:
#         data = response.json()
#         models = data.get('models', [])
#         print(f"✅ Found {len(models)} models:")
#         for model in models[:5]:  # Show first 5
#             print(f"   - {model.get('name')}")
#     else:
#         print(f"❌ Error: {response.text}")
        
# except Exception as e:
#     print(f"❌ Request failed: {e}")

# print()

# # Test 2: Generate Content
# print("🤖 Test 2: Generate content")
# model_name = "gemini-1.5-flash-latest"
# url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"

# payload = {
#     "contents": [{
#         "parts": [{
#             "text": "Say hello in one word"
#         }]
#     }]
# }

# try:
#     response = requests.post(url, json=payload)
#     print(f"Status: {response.status_code}")
    
#     if response.status_code == 200:
#         data = response.json()
#         text = data['candidates'][0]['content']['parts'][0]['text']
#         print(f"✅ Response: {text}")
#     else:
#         print(f"❌ Error: {response.text}")
        
# except Exception as e:
#     print(f"❌ Request failed: {e}")

# print()
# print("="*60)



# # test_backend_direct.py
# import requests
# import json

# print("="*60)
# print("🧪 Testing Backend Query Directly")
# print("="*60)

# # Test query
# url = "http://localhost:8000/api/query"
# headers = {"X-API-Key": "super-secret-token"}
# data = {
#     "q": "Who is Kashaf?",
#     "k": 1
# }

# print(f"📡 Sending request to: {url}")
# print(f"📦 Data: {data}")
# print()

# try:
#     response = requests.post(url, headers=headers, data=data)
#     print(f"📬 Status: {response.status_code}")
#     print(f"📄 Headers: {dict(response.headers)}")
#     print()
    
#     if response.status_code == 200:
#         result = response.json()
#         print(f"✅ Response JSON:")
#         print(json.dumps(result, indent=2))
#         print()
        
#         # Check answer field
#         answer = result.get('answer', '')
#         print(f"📝 Answer: {answer}")
#         print(f"📏 Answer length: {len(answer)} chars")
#         print(f"❓ Answer is empty: {not answer or answer.strip() == ''}")
#         print()
        
#         # Check sources
#         sources = result.get('sources', [])
#         print(f"📚 Sources count: {len(sources)}")
        
#     else:
#         print(f"❌ Error: {response.text}")
        
# except Exception as e:
#     print(f"❌ Request failed: {e}")
#     import traceback
#     traceback.print_exc()

# print("="*60)


"""
Simple Query Test - Just Login and Ask One Question
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def simple_test():
    print("="*60)
    print("🚀 Simple Backend Query Test")
    print("="*60)
    
    # Step 1: Login
    print("\n[1/3] 🔐 Logging in...")
    login_url = f"{BASE_URL}/auth/login"
    login_data = {
        "email": "user@example.com",
        "password": "12345678"
    }
    
    try:
        login_response = requests.post(login_url, json=login_data)
        
        if login_response.status_code == 200:
            token = login_response.json()['access_token']
            print(f"✅ Login successful!")
            print(f"🎫 Token: {token[:30]}...")
        else:
            print(f"❌ Login failed: {login_response.text}")
            print("\n💡 First register a user:")
            print(f"   POST {BASE_URL}/auth/register")
            print('   {"email": "testuser@example.com", "password": "testpass123", "full_name": "Test User"}')
            return
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Is the server running? Start with: uvicorn app:app --reload")
        return
    
    # Step 2: Query Chatbot
    print("\n[2/3] 🤖 Asking chatbot...")
    query_url = f"{BASE_URL}/api/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "q": "Who is Kashaf Naveed?",
        "k": 1
    }
    
    try:
        query_response = requests.post(query_url, json=data, headers=headers)
        
        if query_response.status_code == 200:
            result = query_response.json()
            print(f"✅ Query successful!")
            print(f"\n💬 Question: {data['q']}")
            print(f"\n📝 Answer:\n{result.get('answer', 'No answer')}")
            print(f"\n📊 Stats:")
            print(f"   Answer length: {len(result.get('answer', ''))} chars")
            print(f"   Sources: {len(result.get('sources', []))} documents")
            
            if not result.get('answer') or len(result.get('answer', '').strip()) < 10:
                print("\n⚠️ WARNING: Answer seems empty or too short!")
                print("💡 Possible issues:")
                print("   1. Vector store not loaded")
                print("   2. No documents in /data folder")
                print("   3. Run data ingestion first")
        else:
            print(f"❌ Query failed: {query_response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 3: Check Profile
    print("\n[3/3] 👤 Checking profile...")
    profile_url = f"{BASE_URL}/auth/me"
    
    try:
        profile_response = requests.get(profile_url, headers={"Authorization": f"Bearer {token}"})
        
        if profile_response.status_code == 200:
            profile = profile_response.json()
            print(f"✅ Profile retrieved!")
            print(f"   Name: {profile['full_name']}")
            print(f"   Email: {profile['email']}")
            print(f"   Total Queries: {profile['query_count']}")
        else:
            print(f"❌ Failed: {profile_response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "="*60)
    print("✅ Test complete!")
    print("="*60)

if __name__ == "__main__":
    simple_test()