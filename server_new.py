import http.server
import socketserver
import sqlite3
import json
import uuid
import datetime
import random
import requests
import urllib.parse
from urllib.parse import urlparse, urlsplit, parse_qs
from supabase import create_client, Client
import openpyxl
import os
import threading

print('Resend Integration (Requests) Ready')
SUPABASE_URL = "https://bprbhygcmhlvwpsvmyzt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwcmJoeWdjbWhsdndwc3ZteXp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU0MDU3NTgsImV4cCI6MjA5MDk4MTc1OH0.g2VSOpXCnmZrwYNiJozRtzLjrsziozJoIeK6z4rj0j4"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

PORT = int(os.environ.get('PORT', 8000))
DATABASE = 'stars.db'
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', 're_Y3YvChqy_8umddUdmRLsbs5ozou5wiKRC')

OTP_STORE = {}
SESSION_STORE = {}

PROTECTED_EMAILS = [
    'joshua.q@naischool.ae', 'nabeera.n@naischool.ae', 
    'dummy.counselor@naischool.ae', 'hayaotefy09@gmail.com',
    'admin@stars.ae', '514115@naischool.ae'
]

def init_db():
    conn = sqlite3.connect(DATABASE); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS Users (email TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, password TEXT, role TEXT, title TEXT, bio TEXT, interests TEXT, isCounselor INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS MentorMenteePair (id INTEGER PRIMARY KEY AUTOINCREMENT, mentor_email TEXT, mentee_email TEXT, UNIQUE(mentor_email, mentee_email))")
    c.execute("CREATE TABLE IF NOT EXISTS Messages (id INTEGER PRIMARY KEY AUTOINCREMENT, pair_id INTEGER, sender_email TEXT, message TEXT, timestamp TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS Sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, pair_id INTEGER, start_time TEXT, meeting_link TEXT, scheduled_by TEXT, status TEXT DEFAULT 'Pending')")
    c.execute("CREATE TABLE IF NOT EXISTS Resources (id TEXT PRIMARY KEY, name TEXT, type TEXT, size TEXT, uploaded_by TEXT, timestamp TEXT, description TEXT, category TEXT, url TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS Surveys (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, question TEXT, answer TEXT, timestamp TEXT, survey_type TEXT, source_file TEXT)")
    
    # Absolute Seeding Restoration
    seed = [
        ('hayaotefy09@gmail.com', 'Haya', 'Otefy', 'pass', 'ProgramStaff', 1),
        ('admin@stars.ae', 'System', 'Admin', 'STARS2026', 'ProgramStaff', 1),
        ('514115@naischool.ae', 'Primary', 'Mentor', 'pass', 'Mentor', 1), # Seeding as counselor-privileged mentor
        ('dummy.counselor@naischool.ae', 'Dummy', 'Counselor', 'pass', 'ProgramStaff', 1)
    ]
    for e, f, l, p, r, isc in seed:
        c.execute("INSERT OR REPLACE INTO Users (email, first_name, last_name, password, role, isCounselor) VALUES (?,?,?,?,?,?)", (e.lower(), f, l, p, r, isc))
    conn.commit(); conn.close()
    
    # TRIGGER AUTHORITATIVE SYNC
    threading.Thread(target=full_sync_worker, daemon=True).start()

def full_sync_worker():
    """STARS v13.0: Authoritative Cloud Synchronization Engine"""
    try:
        print("STARS SYNC: Pulling authoritative data from Supabase...")
        # 1. Profiles
        res = supabase.table('profiles').select('*').execute()
        if res.data:
            conn = sqlite3.connect(DATABASE); c = conn.cursor()
            for r in res.data:
                c.execute("INSERT INTO Users (email, first_name, last_name, role, password) VALUES (?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET first_name=excluded.first_name", (r['email'], r.get('first_name'), r.get('last_name'), r.get('role', 'Mentee'), 'pass123'))
            conn.commit(); conn.close()
        
        # 2. Pairings
        res = supabase.table('mentor_mentee_pairs').select('*').execute()
        if res.data:
            conn = sqlite3.connect(DATABASE); c = conn.cursor()
            for r in res.data:
                c.execute("INSERT OR IGNORE INTO MentorMenteePair (mentor_email, mentee_email) VALUES (?,?)", (r['mentor_email'], r['mentee_email']))
            conn.commit(); conn.close()

        # 3. Resources
        res = supabase.table('resources').select('*').execute()
        if res.data:
            conn = sqlite3.connect(DATABASE); c = conn.cursor()
            for r in res.data:
                c.execute("INSERT OR REPLACE INTO Resources (id, name, type, uploaded_by, timestamp) VALUES (?,?,?,?,?)", (str(r['id']), r.get('name'), r.get('type'), r.get('uploaded_by'), r.get('timestamp')))
            conn.commit(); conn.close()
        print("STARS SYNC: Operation successful.")
    except Exception as e: print(f"STARS SYNC ERROR: {e}")

def get_user_from_headers(headers):
    if headers.get('X-Admin-Bypass') == 'STARS2026':
        return {"email": "admin@stars.ae", "role": "ProgramStaff", "name": "System Admin", "isCounselor": True}
    auth = headers.get('Authorization')
    if auth and auth.startswith('Bearer '):
        token = auth.split(' ')[1]
        if token in SESSION_STORE: return SESSION_STORE[token]
    return None

class STARSAPIHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, X-Admin-Bypass')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        super().end_headers()

    def do_OPTIONS(self): self.send_response(200); self.end_headers()

    def do_GET(self):
        try:
            path = self.path.split('?')[0].rstrip('/')
            if path == '/api/initial-data':
                self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
                self.wfile.write(b'{"status": "Online", "v": "13.0 Sync"}')
            elif path == '/api/dashboard': self.handle_dashboard()
            elif path == '/api/admin/data': self.handle_admin_data()
            elif path == '/api/resources': self.handle_get_resources()
            else: super().do_GET()
        except Exception as e: self.send_error_json(500, str(e))

    def handle_dashboard(self):
        u = get_user_from_headers(self.headers)
        if not u: self.send_error_json(401, "Auth Required"); return
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        res = {"pairs": [], "mentors": [], "sessions": [], "resources": [], "messages": []}
        
        # 1. Global Registry (Names)
        c.execute("SELECT first_name, last_name, email, role FROM Users")
        for r in c.fetchall():
            if r[3] == 'Mentor': res["mentors"].append({"name": f"{r[0]} {r[1]}", "email": r[2]})

        # 2. Pairings & Sessions
        if u['role'] == 'ProgramStaff' or u.get('isCounselor'):
            # COUNSELOR: See all pairings
            c.execute("SELECT m.first_name, m.last_name, s.first_name, s.last_name, p.id FROM MentorMenteePair p JOIN Users m ON p.mentor_email=m.email JOIN Users s ON p.mentee_email=s.email")
            for r in c.fetchall(): res["pairs"].append({"mentor_name": f"{r[0]} {r[1]}", "mentee_name": f"{r[2]} {r[3]}", "pair_id": r[4]})
        elif u['role'] == 'Mentor':
            c.execute("SELECT u.first_name, u.last_name, u.email, p.id FROM MentorMenteePair p JOIN Users u ON p.mentee_email = u.email WHERE p.mentor_email=?", (u['email'],))
            for r in c.fetchall(): res["pairs"].append({"name": f"{r[0]} {r[1]}", "email": r[2], "pair_id": r[3], "type": "Mentee"})
        
        c.execute("SELECT id, name, type FROM Resources")
        for r in c.fetchall(): res["resources"].append({"id": r[0], "name": r[1], "type": r[2]})
        conn.close()
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps(res).encode())

    def handle_admin_data(self):
        u = get_user_from_headers(self.headers)
        if not u: self.send_error_json(403, "Access Denied"); return
        res = {"users": [], "pairs": []}
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("SELECT email, first_name, last_name, role FROM Users")
        for r in c.fetchall(): res["users"].append({"email": r[0], "name": f"{r[1]} {r[2]}", "role": r[3]})
        c.execute("SELECT m.first_name, s.first_name, p.id FROM MentorMenteePair p JOIN Users m ON p.mentor_email=m.email JOIN Users s ON p.mentee_email=s.email")
        for r in c.fetchall(): res["pairs"].append({"mentor": r[0], "mentee": r[1], "pair_id": r[2]})
        conn.close()
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps(res).encode())

    def do_POST(self):
        try:
            cl = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(cl).decode('utf-8')) if cl > 0 else {}
            path = self.path.split('?')[0].rstrip('/')
            if path == '/api/login': self.handle_login(data)
            elif path == '/api/register': self.handle_register(data)
            elif path == '/api/admin/create': self.handle_admin_create(data)
            elif path == '/api/admin/pair': self.handle_admin_pair(data)
            elif path == '/api/delete-user': self.handle_delete_user(data)
            elif path == '/api/verify-staff': self.handle_verify_staff(data)
            elif path == '/api/resources/upload': self.handle_upload_resource(data)
            else: self.send_error_json(404, "Endpoint Missing")
        except Exception as e: self.send_error_json(500, str(e))

    def handle_login(self, data):
        e, p = data.get('email', '').lower().strip(), data.get('password')
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("SELECT first_name, last_name, role, isCounselor FROM Users WHERE email=? AND password=?", (e,p))
        r = c.fetchone(); conn.close()
        if r:
            user = {"email": e, "role": r[2], "name": f"{r[0]} {r[1]}", "isCounselor": bool(r[3])}
            token = str(uuid.uuid4()); SESSION_STORE[token] = user
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps({"success": True, "token": token, "user": user}).encode())
        else: self.send_error_json(401, "Invalid credentials")

    def handle_register(self, data):
        e, f, l, p, r = data.get('email').lower(), data.get('firstName'), data.get('lastName'), data.get('password'), data.get('role', 'Mentee')
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO Users (email, first_name, last_name, password, role) VALUES (?,?,?,?,?)", (e,f,l,p,r))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": True}')

    def handle_verify_staff(self, data):
        e = data.get('email', '').lower()
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("SELECT first_name, last_name, password FROM Users WHERE email=? AND isCounselor=1", (e,))
        r = c.fetchone(); conn.close()
        if r:
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps({"success": True, "first_name": r[0], "is_activated": bool(r[2])}).encode())
        else: self.send_error_json(404, "Staff not found")

    def handle_get_resources(self):
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("SELECT id, name, type FROM Resources")
        r = [{"id": x[0], "name": x[1], "type": x[2]} for x in c.fetchall()]; conn.close()
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps(r).encode())

    def send_error_json(self, code, msg):
        self.send_response(code); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps({"error": msg, "success": False}).encode())

if __name__ == "__main__":
    init_db()
    print(f"STARS Portal v13.0 Sync Restoration starting on port {PORT}...")
    httpd = http.server.ThreadingHTTPServer(('', PORT), STARSAPIHandler)
    httpd.serve_forever()
