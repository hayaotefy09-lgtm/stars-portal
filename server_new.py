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
DELETED_RESOURCES_BLOCKLIST = set()

PROTECTED_EMAILS = [
    'joshua.q@naischool.ae', 
    'nabeera.n@naischool.ae', 
    'dummy.counselor@naischool.ae', 
    'hayaotefy09@gmail.com',
    'admin@stars.ae',
    '514115@naischool.ae'
]

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS Users (
        email TEXT PRIMARY KEY,
        first_name TEXT, last_name TEXT, password TEXT, role TEXT,
        title TEXT, bio TEXT, interests TEXT, isCounselor INTEGER DEFAULT 0
    )''')
    for col in ['title', 'bio', 'interests']:
        try: cursor.execute(f"ALTER TABLE Users ADD COLUMN {col} TEXT")
        except: pass
    try: cursor.execute("ALTER TABLE Users ADD COLUMN isCounselor INTEGER DEFAULT 0")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS MentorMenteePair (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mentor_email TEXT, mentee_email TEXT, UNIQUE(mentor_email, mentee_email)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS Messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, pair_id INTEGER, sender_email TEXT, message TEXT, timestamp TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS Sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, pair_id INTEGER, start_time TEXT, 
        meeting_link TEXT, scheduled_by TEXT, status TEXT DEFAULT 'Pending'
    )''')
    for col in ['scheduled_by', 'status', 'participants']:
        try: cursor.execute(f"ALTER TABLE Sessions ADD COLUMN {col} TEXT")
        except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS Resources (
        id TEXT PRIMARY KEY, name TEXT, type TEXT, size TEXT, uploaded_by TEXT, 
        timestamp TEXT, description TEXT, category TEXT, url TEXT
    )''')
    for col in ['description', 'category', 'url']:
        try: cursor.execute(f"ALTER TABLE Resources ADD COLUMN {col} TEXT")
        except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS Surveys (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, question TEXT, answer TEXT, 
        timestamp TEXT, survey_type TEXT, source_file TEXT
    )''')
    try: cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_survey_unique ON Surveys (user_email, question, timestamp, survey_type)")
    except: pass

    # Authoritative Seeding
    seeding_data = [
        ('hayaotefy09@gmail.com', 'Haya', 'Otefy', 'pass', 'ProgramStaff', 1),
        ('admin@stars.ae', 'Master', 'Admin', 'STARS2026', 'ProgramStaff', 1),
        ('514115@naischool.ae', 'Primary', 'Mentor', 'pass', 'Mentor', 0),
        ('dummy.counselor@naischool.ae', 'Dummy', 'Counselor', 'pass', 'ProgramStaff', 1)
    ]
    for email, fn, ln, pw, r, isc in seeding_data:
        cursor.execute("INSERT OR REPLACE INTO Users (email, first_name, last_name, password, role, isCounselor) VALUES (?, ?, ?, ?, ?, ?)", (email.lower(), fn, ln, pw, r, isc))
    conn.commit(); conn.close()

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
            if path == '/api/initial-data': self.get_initial_data()
            elif path == '/api/dashboard': self.handle_dashboard()
            elif path == '/api/admin/data': self.handle_admin_data()
            elif path == '/api/resources': self.handle_get_resources()
            elif path == '/api/messages':
                 self.handle_get_messages(parse_qs(urlsplit(self.path).query).get('pair_id', [None])[0])
            else: super().do_GET()
        except Exception as e: self.send_error_json(500, str(e))

    def handle_dashboard(self):
        u = get_user_from_headers(self.headers)
        if not u: self.send_error_json(401, "Unauthorized"); return
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        res = {"pairs": [], "mentors": [], "sessions": [], "resources": []}
        # 1. Mentors
        c.execute("SELECT first_name, last_name, email FROM Users WHERE role='Mentor'")
        for r in c.fetchall(): res["mentors"].append({"name": f"{r[0]} {r[1]}", "email": r[2]})
        # 2. Role Specific Data
        if u['role'] == 'Mentor':
            c.execute("SELECT u.first_name, u.last_name, u.email, p.id FROM MentorMenteePair p JOIN Users u ON p.mentee_email = u.email WHERE p.mentor_email=?", (u['email'],))
            for r in c.fetchall(): res["pairs"].append({"name": f"{r[0]} {r[1]}", "email": r[2], "pair_id": r[3]})
        # 3. Resources
        c.execute("SELECT id, name, type FROM Resources")
        for r in c.fetchall(): res["resources"].append({"id": r[0], "name": r[1], "type": r[2]})
        conn.close()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
        self.wfile.write(json.dumps(res).encode())

    def do_POST(self):
        try:
            cl = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(cl).decode('utf-8')) if cl > 0 else {}
            path = self.path.split('?')[0].rstrip('/')
            if path == '/api/login' or path == '/api/verify_password': self.handle_login(data)
            elif path == '/api/register': self.handle_register(data)
            elif path == '/api/admin/create': self.handle_admin_create(data)
            elif path == '/api/admin/pair': self.handle_admin_pair(data)
            elif path == '/api/admin/update_profile': self.handle_admin_update_profile(data)
            elif path == '/api/delete-user' or path == '/api/admin/delete': self.handle_delete_user(data)
            elif path == '/api/resources/upload': self.handle_upload_resource(data)
            elif path == '/api/sessions/schedule': self.handle_schedule_session(data)
            elif path == '/api/messages': self.handle_send_message(data)
            elif path == '/api/survey/submit': self.handle_survey_submit(data)
            elif path == '/api/verify-staff': self.handle_verify_staff(data)
            else: self.send_error_json(404, f"Endpoint {path} not found")
        except Exception as e: self.send_error_json(500, str(e))

    def handle_login(self, data):
        e, p = data.get('email', '').lower().strip(), data.get('password')
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("SELECT first_name, last_name, role, isCounselor FROM Users WHERE email=? AND password=?", (e, p))
        r = c.fetchone(); conn.close()
        if r:
            user = {"email": e, "role": r[2], "name": f"{r[0]} {r[1]}", "isCounselor": bool(r[3])}
            token = str(uuid.uuid4()); SESSION_STORE[token] = user
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps({"success": True, "token": token, "user": user}).encode())
        else: self.send_error_json(401, "Invalid credentials")

    def handle_register(self, data):
        e, f, l, p, r = data.get('email').lower().strip(), data.get('firstName'), data.get('lastName'), data.get('password'), data.get('role', 'Mentee')
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO Users (email, first_name, last_name, password, role) VALUES (?, ?, ?, ?, ?)", (e, f, l, p, r))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_admin_create(self, data):
        e, f, l, r = data.get('email').lower(), data.get('firstName'), data.get('lastName'), data.get('role')
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO Users (email, first_name, last_name, role, password) VALUES (?, ?, ?, ?, ?)", (e, f, l, r, 'pass'))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_admin_pair(self, data):
        m, s = data.get('mentor').lower(), data.get('mentee').lower()
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO MentorMenteePair (mentor_email, mentee_email) VALUES (?, ?)", (m, s))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_delete_user(self, data):
        e = data.get('email').lower()
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("DELETE FROM Users WHERE email=?", (e,)); conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_upload_resource(self, data):
        u = get_user_from_headers(self.headers)
        if not u: self.send_error_json(401, "Auth Required"); return
        rid = str(uuid.uuid4())[:8]
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("INSERT INTO Resources (id, name, type, uploaded_by, timestamp) VALUES (?, ?, ?, ?, ?)", (rid, data.get('name'), data.get('type'), u['email'], datetime.datetime.now().strftime("%Y-%m-%d")))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_schedule_session(self, data):
        u = get_user_from_headers(self.headers)
        if not u: self.send_error_json(401, "Auth Required"); return
        p, t, l = data.get('pair_id'), data.get('start_time'), data.get('link', '')
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("INSERT INTO Sessions (pair_id, start_time, meeting_link, scheduled_by) VALUES (?, ?, ?, ?)", (p, t, l, u['email']))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_send_message(self, data):
        u = get_user_from_headers(self.headers)
        if not u: self.send_error_json(401, "Auth Required"); return
        p, m = data.get('pair_id'), data.get('message')
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("INSERT INTO Messages (pair_id, sender_email, message, timestamp) VALUES (?, ?, ?, ?)", (p, u['email'], m, datetime.datetime.now().strftime("%H:%M")))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_survey_submit(self, data):
        u = get_user_from_headers(self.headers)
        if not u: self.send_error_json(401, "Auth Required"); return
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        for q, a in data.items():
            if q != 'survey_type': c.execute("INSERT INTO Surveys (user_email, question, answer, survey_type) VALUES (?, ?, ?, ?)", (u['email'], q, str(a), data.get('survey_type')))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_verify_staff(self, data):
        e = data.get('email', '').lower()
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("SELECT first_name, last_name, password FROM Users WHERE email=? AND isCounselor=1", (e,))
        r = c.fetchone(); conn.close()
        if r:
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps({"success": True, "first_name": r[0], "is_activated": bool(r[2])}).encode())
        else: self.send_error_json(404, "Staff not found")

    def handle_admin_data(self):
        u = get_user_from_headers(self.headers)
        if not u: self.send_error_json(401, "Unauthorized"); return
        res = {"users": [], "pairs": []}
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("SELECT email, first_name, last_name, role FROM Users")
        for r in c.fetchall(): res["users"].append({"email": r[0], "name": f"{r[1]} {r[2]}", "role": r[3]})
        c.execute("SELECT m.first_name, s.first_name, p.id FROM MentorMenteePair p JOIN Users m ON p.mentor_email=m.email JOIN Users s ON p.mentee_email=s.email")
        for r in c.fetchall(): res["pairs"].append({"mentor": r[0], "mentee": r[1], "pair_id": r[2]})
        conn.close()
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps(res).encode())

    def get_initial_data(self):
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(b'{"status": "Online", "v": "11.0 Total"}')

    def send_error_json(self, code, msg):
        self.send_response(code); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps({"error": msg, "success": False}).encode())

if __name__ == "__main__":
    init_db()
    print(f"STARS Portal v11.0 Total Restoration starting on port {PORT}...")
    httpd = http.server.ThreadingHTTPServer(('', PORT), STARSAPIHandler)
    httpd.serve_forever()
