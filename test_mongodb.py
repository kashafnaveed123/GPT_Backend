# test_mongodb.py
from pymongo import MongoClient

try:
    client = MongoClient('mongodb+srv://222kashafnaveed:kashafnaveed@cluster0.vdp24.mongodb.net/Chatbot?retryWrites=true&w=majority', serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ MongoDB is running!")
    print(f"Databases: {client.list_database_names()}")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    print("\n💡 Solutions:")
    print("1. Start MongoDB: net start MongoDB")
    print("2. Use Docker: docker run -d -p 27017:27017 mongo")
    print("3. Use MongoDB Atlas (cloud)")