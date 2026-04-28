import os
from supabase import create_client, Client

SUPABASE_URL = "https://bprbhhygcmhlvwpsvmyzt.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwcmJoeWdjbWhsdndwc3ZteXp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQwNTc1OCwiZXhwIjoyMDkwOTgxNzU4fQ.7D45a-CI4ZSW8oRYiUgQNaRoikX735iHAZh_wPC116I"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print("--- STARS DIAGNOSTIC ---")
for table in ['users', 'profiles', 'Registry', 'Staff', 'resources', 'whiteboard']:
    try:
        res = supabase.table(table).select('*', count='exact').limit(0).execute()
        print(f"Table '{table}': EXISTS, Count: {res.count}")
    except Exception as e:
        print(f"Table '{table}': ERROR ({e})")

print("\nChecking for admin@stars.ae in 'users'...")
try:
    res = supabase.table('users').select('*').eq('email', 'admin@stars.ae').execute()
    if res.data:
        print("FOUND admin@stars.ae:", res.data[0])
    else:
        print("NOT FOUND admin@stars.ae")
except Exception as e:
    print("SEARCH ERROR:", e)
