import json
from supabase import create_client, Client

SUPABASE_URL = "https://bprbhygcmhlvwpsvmyzt.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwcmJoeWdjbWhsdndwc3ZteXp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQwNTc1OCwiZXhwIjoyMDkwOTgxNzU4fQ.7D45a-CI4ZSW8oRYiUgQNaRoikX735iHAZh_wPC116I"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

with open('local_users.json', 'r') as f:
    users = json.load(f)

print(f"Syncing {len(users)} users to STARS 'profiles' table...")
for u in users:
    try:
        res = supabase.table('profiles').select('email').eq('email', u['email']).execute()
        if not res.data:
            supabase.table('profiles').insert({
                "email": u['email'],
                "first_name": u.get('first_name', u.get('name', 'User')),
                "last_name": u.get('last_name', ''),
                "role": u.get('role', 'Mentee')
            }).execute()
            print(f"Created profile: {u['email']}")
        else:
            print(f"Profile exists: {u['email']}")
    except Exception as e:
        print(f"Error: {e}")
