import requests
import json

url = "https://bprbhygcmhlvwpsvmyzt.supabase.co/rest/v1/"
headers = {
    "apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwcmJoeWdjbWhsdndwc3ZteXp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQwNTc1OCwiZXhwIjoyMDkwOTgxNzU4fQ.7D45a-CI4ZSW8oRYiUgQNaRoikX735iHAZh_wPC116I"
}

res = requests.get(url, headers=headers)
schema = res.json()
print("Tables in schema:")
for def_name, def_data in schema.get('definitions', {}).items():
    if "whiteboard" in def_name.lower() or "notes" in def_name.lower():
        print(f"--- {def_name} ---")
        print(json.dumps(def_data.get('properties', {}), indent=2))

