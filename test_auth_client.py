"""
Test client for authentication and chatbot API
Usage: python test_auth_client.py
"""

import requests
import json

BASE_URL = "http://localhost:8000"

class ChatbotClient:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.token = None
        self.headers = {}
    
    def register(self, email: str, password: str, full_name: str):
        """Register a new user"""
        url = f"{self.base_url}/auth/register"
        data = {
            "email": email,
            "password": password,
            "full_name": full_name
        }
        
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            result = response.json()
            self.token = result["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
            print(f"✅ Registration successful!")
            print(f"   User: {result['user']['full_name']}")
            print(f"   Email: {result['user']['email']}")
            return result
        else:
            print(f"❌ Registration failed: {response.text}")
            return None
    
    def login(self, email: str, password: str):
        """Login user"""
        url = f"{self.base_url}/auth/login"
        data = {
            "email": email,
            "password": password
        }
        
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            result = response.json()
            self.token = result["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
            print(f"✅ Login successful!")
            print(f"   User: {result['user']['full_name']}")
            print(f"   Token: {self.token[:20]}...")
            return result
        else:
            print(f"❌ Login failed: {response.text}")
            return None
    
    def get_profile(self):
        """Get user profile"""
        url = f"{self.base_url}/auth/me"
        
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n👤 User Profile:")
            print(f"   Name: {result['full_name']}")
            print(f"   Email: {result['email']}")
            print(f"   Queries: {result['query_count']}")
            print(f"   Member since: {result['created_at']}")
            return result
        else:
            print(f"❌ Failed to get profile: {response.text}")
            return None
    
    def query(self, question: str, k: int = 1):
        """Query the chatbot"""
        url = f"{self.base_url}/api/query"
        data = {
            "q": question,
            "k": k
        }
        
        response = requests.post(url, json=data, headers=self.headers)
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n💬 Query: {question}")
            print(f"📝 Answer: {result['answer']}")
            print(f"📚 Sources: {len(result['sources'])} documents")
            return result
        else:
            print(f"❌ Query failed: {response.text}")
            return None
    
    def verify_token(self):
        """Verify if token is valid"""
        url = f"{self.base_url}/auth/verify"
        
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Token is valid")
            print(f"   User ID: {result['user_id']}")
            return result
        else:
            print(f"❌ Token verification failed")
            return None


def main():
    """Test the chatbot with authentication"""
    client = ChatbotClient()
    
    print("="*60)
    print("🤖 Chatbot Authentication Test Client")
    print("="*60)
    
    # Test 1: Register new user
    print("\n[TEST 1] Registering new user...")
    client.register(
        email="test@example.com",
        password="testpass123",
        full_name="Test User"
    )
    
    # Test 2: Verify token
    print("\n[TEST 2] Verifying token...")
    client.verify_token()
    
    # Test 3: Get profile
    print("\n[TEST 3] Getting user profile...")
    client.get_profile()
    
    # Test 4: Query chatbot
    print("\n[TEST 4] Querying chatbot...")
    client.query("What technologies does Kashaf know?")
    
    # Test 5: Another query
    print("\n[TEST 5] Another query...")
    client.query("Tell me about Kashaf's experience")
    
    # Test 6: Get updated profile (should show query count)
    print("\n[TEST 6] Getting updated profile...")
    client.get_profile()
    
    # Test 7: Login with existing user
    print("\n[TEST 7] Testing login with existing user...")
    client2 = ChatbotClient()
    client2.login("test@example.com", "testpass123")
    client2.get_profile()
    
    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60)


if __name__ == "__main__":
    main()