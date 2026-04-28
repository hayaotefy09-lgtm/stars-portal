import os
import json
import datetime
from supabase import create_client

SUPABASE_URL = "https://bprbhygcmhlvwpsvmyzt.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwcmJoeWdjbWhsdndwc3ZteXp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQwNTc1OCwiZXhwIjoyMDkwOTgxNzU4fQ.7D45a-CI4ZSW8oRYiUgQNaRoikX735iHAZh_wPC116I"
client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

payload1 = {
    "created_by": "test@test.com",
    "content": "test",
    "timestamp": datetime.datetime.now().isoformat(),
    "category": "Session Note"
}

payload2 = {
    "mentor_name": "Test",
    "mentor_email": "test@test.com",
    "note": "test",
    "created_at": datetime.datetime.now().isoformat()
}

try:
    print("Testing Payload 1...")
    res = client.table("whiteboard").insert(payload1).execute()
    print("Payload 1 Success!", res.data)
except Exception as e:
    print("Payload 1 Error:", str(e))

try:
    print("\nTesting Payload 2...")
    res = client.table("whiteboard").insert(payload2).execute()
    print("Payload 2 Success!", res.data)
except Exception as e:
    print("Payload 2 Error:", str(e))

