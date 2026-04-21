import os
from supabase import create_client, Client
SUPABASE_URL = "https://bprbhygcmhlvwpsvmyzt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwcmJoeWdjbWhsdndwc3ZteXp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU0MDU3NTgsImV4cCI6MjA5MDk4MTc1OH0.g2VSOpXCnmZrwYNiJozRtzLjrsziozJoIeK6z4rj0j4"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    res = supabase.table('resources').select('*').limit(1).execute()
    if res.data:
        print("COLUMNS FOUND:", list(res.data[0].keys()))
    else:
        print("TABLE EMPTY, NO SCHEMA HINT")
except Exception as e:
    print("SCHEMA ERROR:", e)
