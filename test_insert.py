import os
import json
from supabase import create_client

SUPABASE_URL = "https://bprbhygcmhlvwpsvmyzt.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwcmJoeWdjbWhsdndwc3ZteXp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQwNTc1OCwiZXhwIjoyMDkwOTgxNzU4fQ.7D45a-CI4ZSW8oRYiUgQNaRoikX735iHAZh_wPC116I"
client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

for table in ['profiles', 'users', 'Registry']:
    try:
        print(f"Testing {table} with all columns...")
        res = client.table(table).insert({"email": "test12345@test.com", "full_name": "Test User", "first_name": "Test", "last_name": "User", "password": "pw", "role": "Mentee"}).execute()
        print("Success:", res.data)
    except Exception as e:
        print("Error:", str(e))
        
    try:
        print(f"Testing {table} with minimal columns...")
        res = client.table(table).insert({"email": "test12345@test.com", "first_name": "Test", "last_name": "User", "role": "Mentee"}).execute()
        print("Success:", res.data)
    except Exception as e:
        print("Error:", str(e))
        
    try:
        print(f"Testing {table} with name and email...")
        res = client.table(table).insert({"email": "test12345@test.com", "name": "Test User", "role": "Mentee"}).execute()
        print("Success:", res.data)
    except Exception as e:
        print("Error:", str(e))
