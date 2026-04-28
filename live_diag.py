import os
from supabase import create_client, Client

SUPABASE_URL = "https://bprbhygcmhlvwpsvmyzt.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwcmJoeWdjbWhsdndwc3ZteXp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQwNTc1OCwiZXhwIjoyMDkwOTgxNzU4fQ.7D45a-CI4ZSW8oRYiUgQNaRoikX735iHAZh_wPC116I"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print("--- STARS LIVE DIAGNOSTIC ---")
tables_to_check = ['users', 'profiles', 'Registry', 'Staff', 'resources', 'whiteboard', 'sessions', 'mentor_mentee_pairs']

for table in tables_to_check:
    try:
        res = supabase.table(table).select('*', count='exact').limit(1).execute()
        print(f"Table '{table}': EXISTS, Count: {res.count}, Sample: {res.data[0] if res.data else 'EMPTY'}")
    except Exception as e:
        print(f"Table '{table}': ERROR ({e})")

print("\nSearching for dummy.counselor@naischool.ae...")
for table in ['users', 'profiles', 'Registry', 'Staff']:
    try:
        res = supabase.table(table).select('*').eq('email', 'dummy.counselor@naischool.ae').execute()
        if res.data:
            print(f"FOUND in '{table}':", res.data[0])
    except: pass
