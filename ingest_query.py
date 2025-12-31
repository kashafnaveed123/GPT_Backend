# import requests


# # Your FastAPI server URL
# BASE_URL = "http://127.0.0.1:8000" 
# headers = {"X-API-Key": "super-secret-token"}


# # Step 1: Call the ingest endpoint
# print("🚀 Sending request to /ingest_local ...")
# resp = requests.post(f"{BASE_URL}/ingest_local"  , headers=headers)
# print('response : ', resp.json())
# if resp.status_code == 200:
#     print("✅ Ingestion completed successfully!")
#     print(resp.json())
# else:
#     print("❌ Ingestion failed!")
#     print("Status Code:", resp.status_code)
#     print("Response:", resp.text)







import requests
import os
from pathlib import Path
from typing import List, Dict, Any
import json

# Your FastAPI server URL
BASE_URL = "http://127.0.0.0:8000"
headers = {"X-API-Key": "super-secret-token"}

# Define metadata for each file
FILE_METADATA = {
    "ai-expertise.md": {
        "category": "expertise",
        "topic": "artificial-intelligence",
        "tags": ["AI", "machine-learning", "expertise"],
        "importance": "high"
    },
    "education.md": {
        "category": "background",
        "topic": "education",
        "tags": ["education", "academic", "qualifications"],
        "importance": "high"
    },
    "experience.md": {
        "category": "background",
        "topic": "work-experience",
        "tags": ["experience", "career", "professional"],
        "importance": "high"
    },
    "identity.md": {
        "category": "personal",
        "topic": "identity",
        "tags": ["identity", "personal", "introduction"],
        "importance": "high"
    },
    "projects.md": {
        "category": "portfolio",
        "topic": "projects",
        "tags": ["projects", "portfolio", "work"],
        "importance": "high"
    },
    "skills.md": {
        "category": "expertise",
        "topic": "skills",
        "tags": ["skills", "technical", "capabilities"],
        "importance": "high"
    },
    "work-philosophy.md": {
        "category": "personal",
        "topic": "philosophy",
        "tags": ["philosophy", "values", "approach"],
        "importance": "medium"
    }
}


def load_documents_with_metadata(data_dir: str = "data") -> List[Dict[str, Any]]:
    """
    Load markdown files from the data directory and attach metadata to each document.
    
    Args:
        data_dir: Path to the directory containing markdown files
        
    Returns:
        List of dictionaries containing document content and metadata
    """
    documents = []
    data_path = Path(data_dir)
    
    if not data_path.exists():
        print(f"❌ Data directory '{data_dir}' not found!")
        return documents
    
    # Get all markdown files
    md_files = list(data_path.glob("*.md"))
    
    print(f"📁 Found {len(md_files)} markdown files")
    
    for file_path in md_files:
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            file_name = file_path.name
            
            # Get predefined metadata or create default
            metadata = FILE_METADATA.get(file_name, {
                "category": "general",
                "topic": file_name.replace(".md", ""),
                "tags": [file_name.replace(".md", "")],
                "importance": "medium"
            })
            
            # Add file-specific metadata
            metadata.update({
                "source": file_name,
                "file_path": str(file_path),
                "file_size": os.path.getsize(file_path),
                "file_type": "markdown"
            })
            
            document = {
                "content": content,
                "metadata": metadata
            }
            
            documents.append(document)
            print(f"✅ Loaded: {file_name} ({len(content)} chars)")
            
        except Exception as e:
            print(f"❌ Error loading {file_path.name}: {str(e)}")
    
    return documents


def ingest_documents_with_metadata(documents: List[Dict[str, Any]]) -> bool:
    """
    Send documents with metadata to the FastAPI ingestion endpoint.
    
    Args:
        documents: List of document dictionaries with content and metadata
        
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"\n🚀 Sending {len(documents)} documents to /ingest_local ...")
        
        payload = {
            "documents": documents
        }
        print('payload : ', payload)
        response = requests.post(
            f"{BASE_URL}/ingest_local",
            json=payload,
            headers=headers,
            timeout=300  # 5 minutes timeout for large documents
        )
        resp = response.json()
        print('response resp : ', resp)
        if resp.status_code == 200:
            print("✅ Ingestion completed successfully!")
            # result = response.json()
            print(json.dumps(resp, indent=2))
            return True
        else:
            print("❌ Ingestion failed!")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out!")
        return False
    except Exception as e:
        print(f"❌ Error during ingestion: {str(e)}")
        return False


def main():
    """Main execution function"""
    print("=" * 60)
    print("📚 Document Ingestion with Metadata")
    print("=" * 60)
    
    # Load documents
    documents = load_documents_with_metadata("data")
    
    if not documents:
        print("\n⚠️  No documents found to ingest!")
        return
    
    print(f"\n📊 Summary:")
    print(f"   - Total documents: {len(documents)}")
    print(f"   - Total size: {sum(len(doc['content']) for doc in documents):,} characters")
    
    # Display metadata overview
    print("\n📋 Document Metadata Overview:")
    for doc in documents:
        metadata = doc['metadata']
        print(f"   • {metadata['source']}: {metadata['category']} - {metadata['topic']}")
    
    # Confirm before ingestion
    print("\n" + "=" * 60)
    user_input = input("Proceed with ingestion? (y/n): ").strip().lower()
    
    if user_input == 'y':
        success = ingest_documents_with_metadata(documents)
        if success:
            print("\n🎉 All documents ingested successfully with metadata!")
        else:
            print("\n💔 Ingestion failed!")
    else:
        print("\n🛑 Ingestion cancelled by user.")


if __name__ == "__main__":
    main()