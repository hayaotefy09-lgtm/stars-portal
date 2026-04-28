import os
import json
from supabase import create_client

SUPABASE_URL = "https://bprbhygcmhlvwpsvmyzt.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwcmJoeWdjbWhsdndwc3ZteXp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQwNTc1OCwiZXhwIjoyMDkwOTgxNzU4fQ.7D45a-CI4ZSW8oRYiUgQNaRoikX735iHAZh_wPC116I"
client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

for table in ['whiteboard', 'Whiteboard', 'Notes', 'mentor_notes']:
    print(f"Testing table {table}...")
    try:
        res = client.table(table).select('*').limit(1).execute()
        print(f"Success for {table}:", res.data)
        break
    except Exception as e:
        print(f"Error for {table}:", str(e))

