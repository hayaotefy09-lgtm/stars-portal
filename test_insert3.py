import os
import json
from supabase import create_client

SUPABASE_URL = "https://bprbhygcmhlvwpsvmyzt.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwcmJoeWdjbWhsdndwc3ZteXp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQwNTc1OCwiZXhwIjoyMDkwOTgxNzU4fQ.7D45a-CI4ZSW8oRYiUgQNaRoikX735iHAZh_wPC116I"
client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

payloads = [
    {"email": "test_fall@test.com", "first_name": "Test", "last_name": "Fall", "role": "Mentee", "password": "pass"},
    {"email": "test_fall@test.com", "first_name": "Test", "last_name": "Fall", "role": "Mentee"},
    {"email": "test_fall@test.com", "role": "Mentee"},
    {"email": "test_fall@test.com"}
]

for p in payloads:
    try:
        print(f"Testing profiles with payload {p}...")
        res = client.table('profiles').insert(p).execute()
        print("Success:", res.data)
        break
    except Exception as e:
        print("Error:", str(e))
    
