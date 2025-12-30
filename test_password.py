# test_password.py
from passlib.context import CryptContext

# Test with argon2
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

try:
    password = "12345678"
    hashed = pwd_context.hash(password)
    print(f"✅ Password hashed successfully: {hashed[:50]}...")
    
    # Verify
    is_valid = pwd_context.verify(password, hashed)
    print(f"✅ Password verification: {is_valid}")
    
except Exception as e:
    print(f"❌ Error: {e}")