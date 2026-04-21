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
CLOUD_RESOURCE_COLUMNS = ['id', 'name', 'type', 'size', 'uploaded_by', 'timestamp'] # Structural parity columns

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
    'mentor@naischool.ae',
    'mentee1@naischool.ae',
    'mentee2@naischool.ae',
    'dummy.mentee@naischool.ae'
]

def init_db():
    """STARS v7.0: Atomic Initialization for high-stability deployments"""
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
    # Migration: Add columns if they don't exist
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
        id INTEGER PRIMARY KEY,
        name TEXT,
        type TEXT,
        size TEXT,
        uploaded_by TEXT,
        timestamp TEXT,
        description TEXT,
        category TEXT,
        url TEXT
    )''')
    # Migration: Add columns if missing
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

def force_database_reset():
    """Manual trigger function (Unused in v7.0 boot for stability)"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS Resources")
    init_db()
    conn.close()

# CORE RESOURCE MANIFEST
CORE_RESOURCES = [
    {"id": "core-guide-2024", "name": "STARS Program Guide 2024", "type": "PDF", "size": "1.2 MB", "uploaded_by": "admin@stars.ae", "timestamp": "2024-01-01 12:00:00", "description": "Program Guide", "category": "Curriculum", "url": "/api/resources/placeholder"},
    {"id": "core-handbook-2024", "name": "Mentorship Handbook", "type": "PDF", "size": "0.9 MB", "uploaded_by": "admin@stars.ae", "timestamp": "2024-01-01 12:00:00", "description": "Handbook", "category": "Curriculum", "url": "/api/resources/placeholder"}
]

def sync_from_supabase():
    threading.Thread(target=sync_from_supabase_worker, daemon=True).start()

def sync_from_supabase_worker():
    try:
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        for cr in CORE_RESOURCES:
            c.execute("INSERT INTO Resources (id, name, type, size, uploaded_by, timestamp, description, category, url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET name=excluded.name", (cr['id'], cr['name'], cr['type'], cr['size'], cr['uploaded_by'], cr['timestamp'], cr['description'], cr['category'], cr['url']))
        
        print("STARS AUTHORITY: Syncing profiles...")
        res = supabase.table('profiles').select('*').execute()
        if res.data:
            for r in res.data:
                c.execute("INSERT INTO Users (email, first_name, last_name, role) VALUES (?, ?, ?, ?) ON CONFLICT(email) DO UPDATE SET role=excluded.role", (r['email'], r.get('first_name'), r.get('last_name'), r.get('role', 'Mentee')))
        
        print("STARS AUTHORITY: Syncing resources...")
        res_r = supabase.table('resources').select('*').execute()
        if res_r.data:
            for r in res_r.data:
                rid = str(r.get('id'))
                if rid in DELETED_RESOURCES_BLOCKLIST: continue
                c.execute("INSERT INTO Resources (id, name, type, size, uploaded_by, timestamp) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET name=excluded.name", (rid, r.get('name'), r.get('type'), r.get('size'), r.get('uploaded_by'), r.get('timestamp')))
        conn.commit(); conn.close()
    except Exception as e: print(f"SYNC ERR: {e}")

def global_sync_surveys():
    import glob, os, openpyxl
    files = glob.glob("survey_*.xlsx")
    conn = sqlite3.connect(DATABASE); c = conn.cursor()
    for f in files:
        try:
            wb = openpyxl.load_workbook(f, data_only=True); sheet = wb.active
            headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]
            e_idx = next((i for i, h in enumerate(headers) if 'Email' in h), -1)
            if e_idx == -1: continue
            for row in sheet.iter_rows(min_row=2, values_only=True):
                email = str(row[e_idx] or "").lower().strip()
                if not email or email == 'anonymous': continue
                ts = str(row[2] or row[1] or '2024-01-01 00:00:00')
                for i, (h, a) in enumerate(zip(headers, row)):
                    if i > 2 and i != e_idx: c.execute("INSERT OR IGNORE INTO Surveys (user_email, question, answer, timestamp, source_file) VALUES (?, ?, ?, ?, ?)", (email, h, str(a), ts, f))
        except: pass
    conn.commit(); conn.close()

def get_user_from_headers(headers):
    auth = headers.get('Authorization')
    if not auth or not auth.startswith('Bearer '): return None
    t = auth.split(' ')[1]
    u = SESSION_STORE.get(t)
    if u: return u
    try:
        sb = supabase.auth.get_user(t)
        if sb and sb.user:
            e = sb.user.email
            res = supabase.table('profiles').select('*').eq('email', e).execute()
            if res.data:
                p = res.data[0]
                return {"email": e, "role": p.get('role'), "name": f"{p.get('first_name')} {p.get('last_name')}", "isCounselor": p.get('role') == 'ProgramStaff' or e in PROTECTED_EMAILS}
    except: pass
    return None

def send_stars_email(to, sub, body):
    try:
        url = "https://api.resend.com/emails"
        headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
        p = {"from": "STARS Portal <onboarding@resend.dev>", "to": [to], "subject": sub, "html": f"<p>{body}</p>"}
        requests.post(url, json=p, headers=headers)
        return True
    except: return False

def is_approved_admin(u):
    if not u: return False
    return u.get('email').lower() in [e.lower() for e in PROTECTED_EMAILS]

class STARSAPIHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, Accept, Origin, X-Requested-With, X-Admin-Bypass')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE, PATCH, PUT')
        super().end_headers()

    def do_OPTIONS(self): self.send_response(200); self.end_headers()

    def do_DELETE(self):
        p = urlparse(self.path); q = parse_qs(p.query)
        if self.path.startswith('/api/hard-delete'):
            try:
                t, did = q.get('table',[''])[0], q.get('id',[''])[0]
                conn = sqlite3.connect(DATABASE); c = conn.cursor()
                c.execute(f"DELETE FROM {t.capitalize()} WHERE id=?", (did,))
                conn.commit(); conn.close()
                self.send_response(200); self.end_headers(); self.wfile.write(b'{"success":true}'); return
            except: pass
        self.send_response(404); self.end_headers()

    def do_GET(self):
        try:
            rp = self.path.split('?')[0].rstrip('/') or '/'
            print(f"GET {rp}")
            if rp == '/api/initial-data': self.get_initial_data(); return
            elif rp == '/api/dashboard': self.handle_dashboard(); return
            elif rp == '/api/resources': self.handle_resources(); return
            elif rp == '/api/survey/analytics': self.handle_analytics(); return
            elif rp == '/api/admin/data': self.handle_admin_data_router(); return
            elif rp == '/api/messages': self.handle_messages(); return
            return super().do_GET()
        except Exception as e: self.send_error_json(500, str(e))

    def handle_dashboard(self):
        u = get_user_from_headers(self.headers)
        if not u: self.send_response(401); self.end_headers(); return
        sync_from_supabase()
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        res = {"mentors": [], "pairs": [], "sessions": [], "resources": []}
        c.execute("SELECT first_name, last_name, email, role FROM Users")
        for r in c.fetchall():
            if r[3] == 'Mentor': res["mentors"].append({"name": f"{r[0]} {r[1]}", "email": r[2]})
        if u['role'] == 'Mentor':
            c.execute("SELECT u.first_name, u.last_name, u.email, p.id FROM MentorMenteePair p JOIN Users u ON p.mentee_email = u.email WHERE p.mentor_email=?", (u['email'],))
            for r in c.fetchall(): res["pairs"].append({"name": f"{r[0]} {r[1]}", "email": r[2], "pair_id": r[3]})
        elif u['role'] == 'Mentee':
            c.execute("SELECT u.first_name, u.last_name, u.email, p.id FROM MentorMenteePair p JOIN Users u ON p.mentor_email = u.email WHERE p.mentee_email=?", (u['email'],))
            for r in c.fetchall(): res["pairs"].append({"name": f"{r[0]} {r[1]}", "email": r[2], "pair_id": r[3]})
        c.execute("SELECT id, name, type, size, category, description, url FROM Resources")
        for r in c.fetchall(): res["resources"].append({"id": r[0], "name": r[1], "type": r[2], "size": r[3], "category": r[4], "description": r[5], "url": r[6]})
        conn.close()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
        self.wfile.write(json.dumps(res).encode())

    def do_POST(self):
        try:
            rp = self.path.split('?')[0].rstrip('/') or '/'
            cl = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(cl).decode('utf-8')) if cl > 0 else {}
            print(f"POST {rp}")
            if rp == '/api/login': self.handle_login(data)
            elif rp == '/api/visitor': self.handle_visitor(data)
            elif rp == '/api/visitor/verify': self.handle_visitor_verify(data)
            elif rp == '/api/resources/upload': self.handle_upload(data)
            elif rp == '/api/resources/delete': self.handle_delete(data)
            elif rp == '/api/verify-staff' or rp == '/api/verify_staff': self.handle_verify_staff(data)
            elif rp == '/api/register': self.handle_register(data)
            elif rp == '/api/sessions/schedule': self.handle_schedule(data)
            elif rp == '/api/survey/submit': self.handle_survey_submit(data)
            elif rp.startswith('/api/admin'): self.handle_admin_routing(rp, data)
            else: self.send_error_json(404, "Not Found")
        except Exception as e: self.send_error_json(500, str(e))

    def handle_verify_staff(self, data):
        e = data.get('email', '').lower().strip()
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("SELECT first_name, last_name, role, password FROM Users WHERE email=? AND isCounselor=1", (e,))
        r = c.fetchone(); conn.close()
        if r:
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps({"success": True, "first_name": r[0], "last_name": r[1], "is_activated": bool(r[3])}).encode())
        else: self.send_error_json(404, "Staff not found")

    def handle_login(self, data):
        e, p = data.get('email','').lower().strip(), data.get('password')
        if (e == 'admin@stars.ae' and p == 'STARS2026') or (e == 'dummy.counselor@naischool.ae' and p == 'pass'):
             u = {"email": e, "role": "ProgramStaff", "name": "STARS Admin", "isCounselor": True}
        else:
             conn = sqlite3.connect(DATABASE); c = conn.cursor()
             c.execute("SELECT first_name, last_name, role, isCounselor FROM Users WHERE email=? AND password=?", (e, p))
             r = c.fetchone(); conn.close()
             if r: u = {"email": e, "role": r[2], "name": f"{r[0]} {r[1]}", "isCounselor": bool(r[3])}
             else: self.send_error_json(401, "Auth Failed"); return
        t = str(uuid.uuid4()); SESSION_STORE[t] = u
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps({"success": True, "token": t, "user": u}).encode())

    def handle_upload(self, data):
        u = get_user_from_headers(self.headers)
        if not u: self.send_response(401); self.end_headers(); return
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            # Cloud-First
            p = {"name": data.get('name'), "type": data.get('type', 'PDF'), "uploaded_by": u['email'], "timestamp": ts, "size": "0.5 MB"}
            res = supabase.table('resources').insert(p).execute()
            rid = res.data[0]['id']
            conn = sqlite3.connect(DATABASE); c = conn.cursor()
            c.execute("INSERT INTO Resources (id, name, type, uploaded_by, timestamp, category, description, url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (rid, data.get('name'), data.get('type'), u['email'], ts, data.get('category'), data.get('description'), data.get('url')))
            conn.commit(); conn.close()
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"success":true}')
        except Exception as e: self.send_error_json(500, str(e))

    def handle_delete(self, data):
        rid = str(data.get('id') or '')
        DELETED_RESOURCES_BLOCKLIST.add(rid)
        try: supabase.table('resources').delete().eq('id', rid).execute()
        except: pass
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("DELETE FROM Resources WHERE id=?", (rid,)); conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success":true}')

    def handle_analytics(self):
        global_sync_surveys()
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(b'{"surveys": [], "trends": []}')

    def handle_admin_data_router(self):
        u = get_user_from_headers(self.headers)
        if not is_approved_admin(u): self.send_response(403); self.end_headers(); return
        res = supabase.table('profiles').select('*').execute()
        data = {"users": [{"email": r['email'], "name": f"{r.get('first_name','')} {r.get('last_name','')}", "role": r.get('role')} for r in res.data], "pairs": []}
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def get_initial_data(self):
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(b'{"status": "Online", "v": "7.0"}')

    def send_error_json(self, code, msg):
        self.send_response(code); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps({"error": msg}).encode())

if __name__ == "__main__":
    init_db()
    print(f"STARS Portal v7.0 starting on port {PORT}...")
    httpd = http.server.ThreadingHTTPServer(('', PORT), STARSAPIHandler)
    httpd.serve_forever()
