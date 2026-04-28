import os
from supabase import create_client, Client

SUPABASE_URL = "https://bprbhygcmhlvwpsvmyzt.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwcmJoeWdjbWhsdndwc3ZteXp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQwNTc1OCwiZXhwIjoyMDkwOTgxNzU4fQ.7D45a-CI4ZSW8oRYiUgQNaRoikX735iHAZh_wPC116I"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print("--- STARS SCHEMA DIAGNOSTIC ---")
tables = ['profiles', 'Registry', 'Staff', 'users', 'Whiteboard', 'resources']

for t in tables:
    try:
        res = supabase.table(t).select('*').limit(1).execute()
        if res.data:
            print(f"Table '{t}' Columns: {list(res.data[0].keys())}")
        else:
            print(f"Table '{t}' is EMPTY.")
    except Exception as e:
        print(f"Table '{t}' Error: {e}")
