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
CLOUD_RESOURCE_COLUMNS = ['id', 'name', 'type', 'size', 'uploaded_by', 'timestamp']

PORT = int(os.environ.get('PORT', 8000))
DATABASE = 'stars.db'
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', 're_Y3YvChqy_8umddUdmRLsbs5ozou5wiKRC')

OTP_STORE = {}
SESSION_STORE = {}
DELETED_RESOURCES_BLOCKLIST = set()

# AUTHORITY: Master Registry of high-clearance emails
PROTECTED_EMAILS = [
    'joshua.q@naischool.ae', 
    'nabeera.n@naischool.ae', 
    'dummy.counselor@naischool.ae', 
    'hayaotefy09@gmail.com',
    'admin@stars.ae',
    'admin@stars.ae'
]

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS Users (
        email TEXT PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        password TEXT,
        role TEXT,
        title TEXT,
        bio TEXT,
        interests TEXT,
        isCounselor INTEGER DEFAULT 0
    )''')
    try: cursor.execute("ALTER TABLE Users ADD COLUMN title TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE Users ADD COLUMN bio TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE Users ADD COLUMN interests TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE Users ADD COLUMN isCounselor INTEGER DEFAULT 0")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS MentorMenteePair (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mentor_email TEXT,
        mentee_email TEXT,
        UNIQUE(mentor_email, mentee_email)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS Messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pair_id INTEGER,
        sender_email TEXT,
        message TEXT,
        timestamp TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS Sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pair_id INTEGER,
        start_time TEXT,
        meeting_link TEXT,
        scheduled_by TEXT,
        status TEXT DEFAULT 'Pending'
    )''')
    try: cursor.execute("ALTER TABLE Sessions ADD COLUMN scheduled_by TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE Sessions ADD COLUMN status TEXT DEFAULT 'Pending'")
    except: pass
    try: cursor.execute("ALTER TABLE Sessions ADD COLUMN participants TEXT DEFAULT ''")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS Resources (
        id TEXT PRIMARY KEY,
        name TEXT,
        type TEXT,
        size TEXT,
        uploaded_by TEXT,
        timestamp TEXT,
        description TEXT,
        category TEXT,
        url TEXT
    )''')
    try: cursor.execute("ALTER TABLE Resources ADD COLUMN description TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE Resources ADD COLUMN category TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE Resources ADD COLUMN url TEXT")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS Surveys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        question TEXT,
        answer TEXT,
        timestamp TEXT,
        survey_type TEXT,
        source_file TEXT
    )''')
    try: cursor.execute("ALTER TABLE Surveys ADD COLUMN source_file TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE Surveys ADD COLUMN survey_type TEXT")
    except: pass
    try: cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_survey_unique ON Surveys (user_email, question, timestamp, survey_type)")
    except: pass

    # Unified Seeding (Restoration Parity)
    seeding_data = [
        ('hayaotefy09@gmail.com', 'Haya', 'Otefy', 'pass', 'ProgramStaff', 1),
        ('joshua.q@naischool.ae', 'Joshua', 'Quinn', 'pass', 'ProgramStaff', 1),
        ('nabeera.n@naischool.ae', 'Nabeera', 'Noman', 'pass', 'ProgramStaff', 1),
        ('dummy.counselor@naischool.ae', 'Dummy', 'Counselor', 'pass', 'ProgramStaff', 1),
        ('admin@stars.ae', 'Master', 'Admin', 'STARS2026', 'ProgramStaff', 1),
        ('mentor@naischool.ae', 'Test', 'Mentor', 'pass', 'Mentor', 0),
        ('mentee1@naischool.ae', 'Amira', 'Ali Ismael', 'pass', 'Mentee', 0),
        ('mentee2@naischool.ae', 'Raqia', 'Ahmed', 'pass', 'Mentee', 0),
        ('dummy.mentee@naischool.ae', 'Tester', 'Mentee', 'pass', 'Mentee', 0)
    ]
    for email, fn, ln, pw, r, isc in seeding_data:
        cursor.execute("INSERT OR REPLACE INTO Users (email, first_name, last_name, password, role, isCounselor) VALUES (?, ?, ?, ?, ?, ?)", 
                       (email.lower(), fn, ln, pw, r, isc))

    conn.commit()
    conn.close()

def sync_from_supabase():
    threading.Thread(target=sync_from_supabase_worker, daemon=True).start()

def sync_from_supabase_worker():
    """Authoritative Pull of Cloud Registry (Executed in Background)"""
    try:
        res = supabase.table('profiles').select('*').execute()
        if res.data:
            conn = sqlite3.connect(DATABASE); c = conn.cursor()
            for r in res.data:
                c.execute("""INSERT INTO Users (email, first_name, last_name, bio, interests, title, role, password)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                             ON CONFLICT(email) DO UPDATE SET first_name=excluded.first_name, role=excluded.role""", 
                          (r['email'], r.get('first_name'), r.get('last_name'), r.get('bio'), r.get('interests'), r.get('title'), r.get('role', 'Mentee'), 'pass123'))
            conn.commit(); conn.close()
    except Exception as e: print(f"STARS SYNC ERROR: {e}")

def get_user_from_headers(headers):
    # Bypass Logic for Admin Console (Legacy Parity)
    if headers.get('X-Admin-Bypass') == 'STARS2026':
        return {"email": "admin@stars.ae", "role": "ProgramStaff", "name": "Master Admin", "isCounselor": True}
    
    auth_header = headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '): return None
    token = auth_header.split(' ')[1]
    user = SESSION_STORE.get(token)
    if user: return user
    try:
        sb_user = supabase.auth.get_user(token)
        if sb_user and sb_user.user:
            email = sb_user.user.email
            res = supabase.table('profiles').select('*').eq('email', email).execute()
            if res.data:
                profile = res.data[0]
                return {"email": email.strip(), "role": profile.get('role', 'Mentee'), "name": f"{profile.get('first_name', '')} {profile.get('last_name', '')}", "isCounselor": profile.get('role') == 'ProgramStaff' or email.lower().strip() in [e.lower() for e in PROTECTED_EMAILS]}
    except: pass
    return None

def is_approved_admin(user):
    if not user: return False
    return user.get('email', '').lower() in [e.lower() for e in PROTECTED_EMAILS]

class STARSAPIHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, Accept, Origin, X-Requested-With, X-Admin-Bypass')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE, PATCH, PUT')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self): self.send_response(200); self.end_headers()

    def do_GET(self):
        try:
            raw_path = self.path.split('?')[0].rstrip('/') or '/'
            print(f">>> STARS API INCOMING: GET {raw_path}")
            query = urlsplit(self.path).query; params = parse_qs(query)
            if raw_path == '/api/initial-data': self.get_initial_data(); return
            elif raw_path == '/api/dashboard': self.handle_dashboard_routing(); return
            elif raw_path == '/api/resources': self.handle_get_resources(); return
            elif raw_path.startswith('/api/admin/data'): self.handle_admin_data_routing(); return
            elif raw_path.startswith('/api/messages'): self.handle_get_messages(params.get('pair_id', [None])[0]); return
            return super().do_GET()
        except Exception as e: self.send_error_json(500, str(e))

    def handle_dashboard_routing(self):
        try:
            user = get_user_from_headers(self.headers)
            if not user: self.send_response(401); self.end_headers(); return
            sync_from_supabase()
            email, role, is_c = user.get('email'), user.get('role'), user.get('isCounselor')
            conn = sqlite3.connect(DATABASE); c = conn.cursor()
            res = {"pairs": [], "mentors": [], "sessions": [], "resources": [], "surveys": []}

            c.execute("SELECT first_name, last_name, email, bio, interests, title, role, (SELECT COUNT(*) FROM MentorMenteePair p WHERE p.mentor_email = Users.email) FROM Users")
            for r in c.fetchall():
                if r[6] == 'Mentor': res["mentors"].append({"name": f"{r[0]} {r[1]}", "email": r[2], "bio": r[3] or '', "interests": r[4] or '', "title": r[5] or 'STARS MENTOR', "role": r[6], "is_paired": r[7] > 0})

            if role == 'Mentor':
                c.execute("SELECT u.first_name, u.last_name, u.email, p.id FROM MentorMenteePair p JOIN Users u ON p.mentee_email = u.email WHERE p.mentor_email=?", (email,))
                for r in c.fetchall(): res["pairs"].append({"name": f"{r[0]} {r[1]}", "email": r[2], "pair_id": r[3], "type": "Mentee"})
                c.execute("SELECT s.id, s.start_time, s.pair_id, u.first_name, u.last_name, s.meeting_link, s.status, s.participants FROM Sessions s JOIN MentorMenteePair p ON s.pair_id = p.id JOIN Users u ON p.mentee_email = u.email WHERE p.mentor_email=?", (email,))
                for r in c.fetchall(): res["sessions"].append({"id": r[0], "start_time": r[1], "pair_id": r[2], "partner_name": f"{r[3]} {r[4]}", "meeting_link": r[5], "status": r[6], "participants": r[7]})
            elif role == 'Mentee':
                c.execute("SELECT u.first_name, u.last_name, u.email, p.id FROM MentorMenteePair p JOIN Users u ON p.mentor_email = u.email WHERE p.mentee_email=?", (email,))
                for r in c.fetchall(): res["pairs"].append({"name": f"{r[0]} {r[1]}", "email": r[2], "pair_id": r[3], "type": "Mentor"})
                c.execute("SELECT s.id, s.start_time, s.pair_id, u.first_name, u.last_name, s.meeting_link, s.status, s.participants FROM Sessions s JOIN MentorMenteePair p ON s.pair_id = p.id JOIN Users u ON p.mentor_email = u.email WHERE p.mentee_email=?", (email,))
                for r in c.fetchall(): res["sessions"].append({"id": r[0], "start_time": r[1], "pair_id": r[2], "partner_name": f"{r[3]} {r[4]}", "meeting_link": r[5], "status": r[6], "participants": r[7]})
            elif is_c or role == 'ProgramStaff':
                c.execute("SELECT m.first_name, m.last_name, s.first_name, s.last_name, p.id, m.email, s.email FROM MentorMenteePair p JOIN Users m ON p.mentor_email = m.email JOIN Users s ON p.mentee_email = s.email")
                for r in c.fetchall(): res["pairs"].append({"mentor_name": f"{r[0]} {r[1]}", "mentee_name": f"{r[2]} {r[3]}", "mentor_email": r[5], "mentee_email": r[6], "pair_id": r[4]})
                c.execute("SELECT s.id, s.start_time, s.pair_id, m.first_name, m.last_name, me.first_name, me.last_name, s.meeting_link, s.status FROM Sessions s LEFT JOIN MentorMenteePair p ON s.pair_id = p.id LEFT JOIN Users m ON p.mentor_email = m.email LEFT JOIN Users me ON p.mentee_email = me.email")
                for r in c.fetchall(): res["sessions"].append({"id": r[0], "start_time": r[1], "pair_id": r[2], "partner_name": f"{r[3]} {r[4]} <-> {r[5]} {r[6]}", "meeting_link": r[7], "status": r[8]})

            c.execute("SELECT id, name, type, size, category, description, url FROM Resources")
            for r in c.fetchall(): res["resources"].append({"id": r[0], "name": r[1], "type": r[2], "size": r[3], "category": r[4], "description": r[5], "url": r[6]})
            conn.close()
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(res).encode())
        except Exception as e: self.send_error_json(500, str(e))

    def handle_admin_data_routing(self):
        user = get_user_from_headers(self.headers)
        if not is_approved_admin(user): self.send_response(403); self.end_headers(); return
        
        registry_data = {"users": [], "pairs": []}
        try:
            conn = sqlite3.connect(DATABASE); c = conn.cursor()
            c.execute("SELECT first_name, last_name, email, role FROM Users")
            for r in c.fetchall():
                registry_data["users"].append({"name": f"{r[0]} {r[1]}", "email": r[2], "role": r[3]})
            c.execute("""SELECT m.first_name, m.last_name, s.first_name, s.last_name, p.id, m.email, s.email 
                         FROM MentorMenteePair p JOIN Users m ON p.mentor_email = m.email JOIN Users s ON p.mentee_email = s.email""")
            for r in c.fetchall():
                registry_data["pairs"].append({"mentor": f"{r[0]} {r[1]} ({r[2]})", "mentee": f"{r[3]} {r[4]} ({r[5]})", "pair_id": r[4]})
            conn.close()
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(registry_data).encode())
        except Exception as e: self.send_error_json(500, str(e))

    def handle_login(self, data):
        email, pwd = data.get('email', '').strip().lower(), data.get('password')
        if (email == 'admin@stars.ae' and pwd == 'STARS2026') or (email == 'dummy.counselor@naischool.ae' and pwd == 'pass'):
             u = {"email": email, "role": "ProgramStaff", "name": "STARS Admin", "isCounselor": True, "firstName": "STARS", "lastName": "Admin"}
        else:
             conn = sqlite3.connect(DATABASE); c = conn.cursor()
             c.execute("SELECT first_name, last_name, role, isCounselor FROM Users WHERE email=? AND password=?", (email, pwd))
             r = c.fetchone(); conn.close()
             if r: u = {"email": email, "role": r[2], "name": f"{r[0]} {r[1]}", "isCounselor": bool(r[3]), "firstName": r[0], "lastName": r[1]}
             else: self.send_error_json(401, "Invalid credentials."); return
        token = str(uuid.uuid4()); SESSION_STORE[token] = u
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps({"success": True, "token": token, "user": u}).encode())

    def do_POST(self):
        try:
            cl = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(cl).decode('utf-8')) if cl > 0 else {}
            raw_path = self.path.split('?')[0].rstrip('/')
            if raw_path == '/api/login' or raw_path == '/api/verify_password': self.handle_login(data)
            elif raw_path == '/api/admin/create': self.handle_admin_create(data)
            elif raw_path == '/api/admin/pair': self.handle_admin_pair(data)
            elif raw_path == '/api/admin/update_profile': self.handle_admin_update_profile(data)
            elif raw_path == '/api/resources/upload': self.handle_upload_resource(data)
            elif raw_path == '/api/resources/delete': self.handle_delete_resource(data)
            elif raw_path == '/api/sessions/schedule': self.handle_schedule(data)
            elif raw_path.startswith('/api/survey/submit'): self.handle_survey_submit(data)
            else: self.send_error_json(404, "Not Found")
        except Exception as e: self.send_error_json(500, str(e))

    def handle_admin_create(self, data):
        e, f, l, r = data.get('email'), data.get('firstName'), data.get('lastName'), data.get('role')
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO Users (email, first_name, last_name, role) VALUES (?, ?, ?, ?)", (e, f, l, r))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_admin_pair(self, data):
        m, s = data.get('mentor'), data.get('mentee')
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO MentorMenteePair (mentor_email, mentee_email) VALUES (?, ?)", (m, s))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_admin_update_profile(self, data):
        e, t, b, i = data.get('email'), data.get('title', ''), data.get('bio', ''), data.get('interests', '')
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("UPDATE Users SET title=?, bio=?, interests=? WHERE email=?", (t, b, i, e))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_upload_resource(self, data):
        user = get_user_from_headers(self.headers)
        if not user: self.send_error_json(401, "Auth Required"); return
        rid = str(uuid.uuid4())[:8]
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("INSERT INTO Resources (id, name, type, uploaded_by, timestamp) VALUES (?, ?, ?, ?, ?)", 
                  (rid, data.get('name'), data.get('type'), user['email'], datetime.datetime.now().strftime("%Y-%m-%d")))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_get_resources(self):
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("SELECT id, name, type, size, uploaded_by, timestamp FROM Resources")
        r = [{"id": x[0], "name": x[1], "type": x[2]} for x in c.fetchall()]; conn.close()
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps(r).encode())

    def get_initial_data(self):
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(b'{"status": "Online", "v": "9.3 Bypass"}')

    def send_error_json(self, code, msg):
        self.send_response(code); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps({"error": msg}).encode())

if __name__ == "__main__":
    init_db()
    print(f"STARS Portal v9.3 Bypass Restoration starting on port {PORT}...")
    httpd = http.server.ThreadingHTTPServer(('', PORT), STARSAPIHandler)
    httpd.serve_forever()
