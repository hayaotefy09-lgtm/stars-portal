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
        # Counselors
        ('hayaotefy09@gmail.com', 'Haya', 'Otefy', 'pass', 'ProgramStaff', 1),
        ('joshua.q@naischool.ae', 'Joshua', 'Quinn', 'pass', 'ProgramStaff', 1),
        ('nabeera.n@naischool.ae', 'Nabeera', 'Noman', 'pass', 'ProgramStaff', 1),
        ('dummy.counselor@naischool.ae', 'Dummy', 'Counselor', 'pass', 'ProgramStaff', 1),
        ('admin@stars.ae', 'Master', 'Admin', 'pass', 'ProgramStaff', 1),
        # Test Participants
        ('mentor@naischool.ae', 'Test', 'Mentor', 'pass', 'Mentor', 0),
        ('mentee1@naischool.ae', 'Amira', 'Ali Ismael', 'pass', 'Mentee', 0),
        ('mentee2@naischool.ae', 'Raqia', 'Ahmed', 'pass', 'Mentee', 0),
        ('dummy.mentee@naischool.ae', 'Tester', 'Mentee', 'pass', 'Mentee', 0)
    ]
    for email, fn, ln, pw, r, isc in seeding_data:
        cursor.execute("INSERT OR REPLACE INTO Users (email, first_name, last_name, password, role, isCounselor) VALUES (?, ?, ?, ?, ?, ?)", 
                       (email.lower(), fn, ln, pw, r, isc))

    # Basic Pairing Sync
    cursor.execute("INSERT OR IGNORE INTO MentorMenteePair (mentor_email, mentee_email) VALUES ('mentor@naischool.ae', 'mentee1@naischool.ae')")
    cursor.execute("INSERT OR IGNORE INTO MentorMenteePair (mentor_email, mentee_email) VALUES ('mentor@naischool.ae', 'mentee2@naischool.ae')")
    
    conn.commit()
    conn.close()

def force_database_reset():
    """INFRASTRUCTURE HARDFIX: Dropping and recreating Resources to fix ID Mismatch and Stale Records"""
    print("\n" + "!"*60 + "\nSTARS AUTHORITY: Performing Authoritative Database Hard Reset...\n" + "!"*60 + "\n")
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS Resources")
    c.execute("""
        CREATE TABLE Resources (
            id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT,
            size TEXT,
            uploaded_by TEXT,
            timestamp TEXT,
            description TEXT,
            category TEXT,
            url TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("STARS AUTHORITY: Database Hard Reset Complete.")

# CORE RESOURCE MANIFEST: Fallback data for critical documents
CORE_RESOURCES = [
    {
        "id": "core-guide-2024",
        "name": "STARS Program Guide 2024",
        "type": "PDF",
        "size": "1.2 MB",
        "uploaded_by": "admin@stars.ae",
        "timestamp": "2024-01-01 12:00:00",
        "description": "Comprehensive guide for the 2024 STARS Mentorship Program cycle.",
        "category": "Curriculum",
        "url": "/api/resources/placeholder" # Fallback if sync fails
    },
    {
        "id": "core-handbook-2024",
        "name": "Mentorship Handbook",
        "type": "PDF",
        "size": "0.9 MB",
        "uploaded_by": "admin@stars.ae",
        "timestamp": "2024-01-01 12:00:00",
        "description": "Best practices and guidelines for Mentors and Mentees.",
        "category": "Curriculum",
        "url": "/api/resources/placeholder"
    },
    {
        "id": "core-reflection-template",
        "name": "Reflection Template",
        "type": "DOCX",
        "size": "0.1 MB",
        "uploaded_by": "admin@stars.ae",
        "timestamp": "2024-01-01 12:00:00",
        "description": "Weekly reflection document for mentees to track their growth.",
        "category": "Assignments",
        "url": "/api/resources/placeholder"
    },
    {
        "id": "core-logo-pack",
        "name": "STARS Logo Pack",
        "type": "ZIP",
        "size": "5.4 MB",
        "uploaded_by": "admin@stars.ae",
        "timestamp": "2024-01-01 12:00:00",
        "description": "Branding assets and logos for presentations and materials.",
        "category": "Assets",
        "url": "/api/resources/placeholder"
    }
]

def sync_from_supabase():
    """Non-blocking sync trigger for high-responsiveness"""
    threading.Thread(target=sync_from_supabase_worker, daemon=True).start()

def sync_from_supabase_worker():
    """Authoritative Pull of Cloud Registry (Executed in Background)"""
    try:
        # --- BOOTSTRAP CORE MANIFEST ---
        # Ensures critical records always have stable IDs and valid structure
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Ensure table exists with correct schema
        c.execute("""
            CREATE TABLE IF NOT EXISTS Resources (
                id TEXT PRIMARY KEY,
                name TEXT,
                type TEXT,
                size TEXT,
                uploaded_by TEXT,
                timestamp TEXT,
                description TEXT,
                category TEXT,
                url TEXT
            )
        """)
        
        for cr in CORE_RESOURCES:
            c.execute("""
                INSERT INTO Resources (id, name, type, size, uploaded_by, timestamp, description, category, url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name, description=excluded.description
            """, (cr['id'], cr['name'], cr['type'], cr['size'], cr['uploaded_by'], cr['timestamp'], cr['description'], cr['category'], cr['url']))
        conn.commit()
        conn.close()

        # --- PROFILE SYNC ---
        print("STARS AUTHORITY: Synchronizing local registry from Supabase cloud...")
        res = supabase.table('profiles').select('*').execute()
        
        # PRE-FETCH CORE NAMES FOR FILTERING
        core_names = [cr['name'] for cr in CORE_RESOURCES]

        if res.data:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            for r in res.data:
                c.execute("""
                    INSERT INTO Users (email, first_name, last_name, bio, interests, title, role, password)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(email) DO UPDATE SET
                        first_name=excluded.first_name,
                        last_name=excluded.last_name,
                        bio=excluded.bio,
                        interests=excluded.interests,
                        title=excluded.title,
                        role=excluded.role
                """, (r['email'], r.get('first_name'), r.get('last_name'), r.get('bio'), r.get('interests'), r.get('title'), r.get('role', 'Mentee'), 'pass123'))
            conn.commit()
            conn.close()

        # --- RESOURCE SYNC ---
        print("STARS AUTHORITY: Synchronizing Library (Resources)...")
        res_r = supabase.table('resources').select('*').execute()
        if res_r.data:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            for r in res_r.data:
                # Exhaustive Metadata Recovery (handles all possible cloud schema variations)
                name = r.get('name') or r.get('Name') or r.get('NAME') or r.get('title') or r.get('Title') or 'Resource'
                if name in core_names: continue

                rtype = r.get('type') or r.get('Type') or r.get('file_type') or 'PDF'
                desc = r.get('description') or r.get('Description') or r.get('desc') or r.get('summary') or r.get('Summary') or ''
                cat = r.get('category') or r.get('Category') or r.get('cat') or 'General'
                
                url = (r.get('url') or r.get('Url') or r.get('URL') or 
                       r.get('file_url') or r.get('fileUrl') or r.get('fileURL') or
                       r.get('link') or r.get('Link') or r.get('LINK') or
                       r.get('path') or r.get('Path') or r.get('path_url') or '')

                # 2. STRATEGIC MERGE: Never overwrite local Source-of-Truth with Cloud nulls
                c.execute("SELECT url, description, category FROM Resources WHERE id=?", (str(r.get('id')),))
                existing = c.fetchone()
                
                # Use cloud values if they exist, otherwise keep local
                final_url = url if url else (existing[0] if existing else '')
                final_desc = desc if desc else (existing[1] if existing else '')
                final_cat = cat if cat else (existing[2] if existing else 'General')

                # 3. ANTI-GHOSTING PROTECTION: Skip if recently deleted in this session
                if str(r.get('id')) in DELETED_RESOURCES_BLOCKLIST:
                    print(f"STARS SYNC: Skipping ghost resource {r.get('id')}")
                    continue

                c.execute("""
                    INSERT INTO Resources (id, name, type, size, uploaded_by, timestamp, description, category, url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name, type=excluded.type, size=excluded.size,
                        uploaded_by=excluded.uploaded_by, timestamp=excluded.timestamp,
                        description=?, category=?, url=?
                """, (str(r.get('id')), name, rtype, r.get('size', '0.5 MB'), r.get('uploaded_by',''), r.get('timestamp',''), final_desc, final_cat, final_url))
            conn.commit()
            conn.close()
            print(f"STARS AUTHORITY: Resource sync successful. {len(res_r.data)} items updated.")
            
    except Exception as e:
        print(f"STARS SYNC ERROR: {e}")

def global_sync_surveys():
    import glob, os, sqlite3, openpyxl, datetime
    files = glob.glob("survey_*.xlsx")
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    for excel_path in files:
        filename = os.path.basename(excel_path)
        survey_type = 'General'
        if 'pre' in filename.lower(): survey_type = 'Pre-Session'
        elif 'post' in filename.lower(): survey_type = 'Post-Session'
        elif 'during' in filename.lower(): survey_type = 'During-Session'
        try:
            wb = openpyxl.load_workbook(excel_path, data_only=True)
            sheet = wb.active
            headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]
            email_idx = -1
            name_idx = -1
            for i, h in enumerate(headers):
                if h == 'Email': email_idx = i
                if h in ['Mentee Name', 'Name']: name_idx = i
            if email_idx == -1: email_idx = next((i for i, h in enumerate(headers) if 'email' in h.lower()), -1)
            if name_idx == -1: name_idx = next((i for i, h in enumerate(headers) if 'name' in h.lower()), -1)
            if email_idx == -1: continue
            for row in sheet.iter_rows(min_row=2, values_only=True):
                email = str(row[email_idx] or "").lower().strip()
                if not email or email == 'anonymous': continue
                ts_val = row[2] or row[1] or datetime.datetime.now()
                ts = ts_val.strftime("%Y-%m-%d %H:%M:%S") if isinstance(ts_val, datetime.datetime) else str(ts_val)
                for i, (h, a) in enumerate(zip(headers, row)):
                    if i <= 2 or i == email_idx or i == name_idx: continue
                    if not h or a is None: continue
                    c.execute("INSERT OR IGNORE INTO Surveys (user_email, question, answer, timestamp, survey_type, source_file) VALUES (?, ?, ?, ?, ?, ?)", (email, h, str(a), ts, survey_type, filename))
        except Exception as e: print(f"BOOT SYNC ERROR ({filename}): {e}")
    conn.commit()
    conn.close()
    print("AUTHORITATIVE STARTUP SYNC COMPLETE.")

global_sync_surveys()

def get_user_from_headers(headers):
    auth_header = headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    
    # 1. Check local session store (legacy/counselor logic)
    user = SESSION_STORE.get(token)
    if user: return user
    
    # 2. Check Supabase Auth
    try:
        sb_user = supabase.auth.get_user(token)
        if sb_user and sb_user.user:
            email = sb_user.user.email
            # Fetch profile to get role from 'profiles' table
            res = supabase.table('profiles').select('*').eq('email', email).execute()
            if res.data:
                profile = res.data[0]
                return {
                    "email": email.strip(),
                    "role": profile.get('role', 'Mentee'),
                    "name": f"{profile.get('first_name', '')} {profile.get('last_name', '')}",
                    "isCounselor": str(profile.get('role')).lower() == 'programstaff' or email.lower().strip() in [e.lower().strip() for e in PROTECTED_EMAILS]
                }
    except Exception as e:
        print(f"Supabase Token Verification Failed: {e}")
        
    return None

def send_stars_email(to_email, subject, body_text):
    print(f"DEBUG: Send to {to_email}...")
    to_email_clean = to_email.strip()
    otp_code = body_text.split(':')[-1].strip() if ':' in body_text else body_text
    html_content = f"<h2>STARS Portal Access</h2><p>Your OTP: {otp_code}</p>"
    try:
        url = "https://api.resend.com/emails"
        headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
        payload = {"from": "STARS Portal <onboarding@resend.dev>", "to": [to_email_clean], "subject": subject, "html": html_content}
        response = requests.post(url, json=payload, headers=headers)
        return response.status_code in [200, 201]
    except Exception as e:
        print(f"RESEND ERR: {e}")
        return False

def is_approved_admin(user):
    if not user: return False
    approved = ['hayaotefy09@gmail.com', 'joshua.q@naischool.ae', 'nabeera.n@naischool.ae', 'dummy.counselor@naischool.ae']
    return user.get('email', '').lower() in [e.lower() for e in approved]

class STARSAPIHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, Accept, Origin, X-Requested-With, X-Admin-Bypass')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE, PATCH, PUT')
        self.send_header('Access-Control-Max-Age', '86400')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, Accept, Origin, X-Requested-With, X-Admin-Bypass')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE, PATCH, PUT')
        self.end_headers()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if self.path.startswith('/api/hard-delete'):
            try:
                table = params.get('table', ['users'])[0]
                did = params.get('id', [None])[0]
                email = params.get('email', [None])[0]
                local_table = 'Users'
                cloud_table = 'users'
                if table.lower() in ['session', 'sessions']: local_table = 'Sessions'; cloud_table = 'sessions'
                elif table.lower() in ['pair', 'pairs']: local_table = 'MentorMenteePair'; cloud_table = 'mentor_mentee_pairs'

                conn = sqlite3.connect(DATABASE); c = conn.cursor()
                if email and local_table == 'Users': c.execute("DELETE FROM Users WHERE email = ?", (email,))
                else: c.execute(f"DELETE FROM {local_table} WHERE id = ?", (did,))
                conn.commit(); conn.close()

                if local_table == 'Users':
                    if did: supabase.table('profiles').delete().eq('id', did).execute()
                    elif email: supabase.table('profiles').delete().eq('email', email).execute()
                else:
                    supabase.table(cloud_table).delete().eq('id', did).execute()
                
                self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
                self.wfile.write(b'{"success": true}'); return
            except Exception as e:
                self.send_response(500); self.end_headers(); return
        self.send_response(404); self.end_headers()

    def do_GET(self):
        try:
            raw_path = self.path.split('?')[0].rstrip('/')
            if not raw_path: raw_path = '/'
            query = urlsplit(self.path).query
            params = parse_qs(query)

            if raw_path == '/api/initial-data': self.get_initial_data(); return
            elif raw_path == '/api/dashboard': self.handle_dashboard_routing(); return
            elif raw_path == '/api/resources': self.handle_get_resources(); return
            elif raw_path == '/api/survey/analytics': self.handle_survey_analytics(); return
            elif raw_path.startswith('/api/link-profile'):
                email, uid = params.get('email', [None])[0], params.get('id', [None])[0]
                if email and uid: self.handle_link_profile(email, uid)
                return
            elif raw_path.startswith('/api/messages'):
                pair_id = params.get('pair_id', [None])[0]
                self.handle_get_messages(pair_id); return
            elif raw_path.startswith('/api/admin/data'):
                self.handle_admin_data_routing(); return
            return super().do_GET()
        except Exception as e:
            self.send_error_json(500, str(e))

    def handle_dashboard_routing(self):
        try:
            user = get_user_from_headers(self.headers)
            if not user: self.send_response(401); self.end_headers(); return
            sync_from_supabase()
            email, role, is_c = user.get('email'), user.get('role'), user.get('isCounselor')
            conn = sqlite3.connect(DATABASE); c = conn.cursor()
            res = {"pairs": [], "mentors": [], "sessions": [], "messages": [], "resources": [], "surveys": []}
            
            c.execute("SELECT u.first_name, u.last_name, u.email, u.bio, u.interests, u.title, u.role, (SELECT COUNT(*) FROM MentorMenteePair p WHERE p.mentor_email = u.email) as pair_count FROM Users u")
            all_u = c.fetchall()
            res["mentors"] = [{"name": f"{r[0]} {r[1]}", "email": r[2], "bio": r[3] or '', "interests": r[4] or '', "title": r[5] or 'STARS MENTOR', "role": r[6], "is_paired": r[7] > 0} for r in all_u if r[6] == 'Mentor']

            if role == 'Mentor':
                c.execute("SELECT u.first_name, u.last_name, u.email, p.id FROM MentorMenteePair p JOIN Users u ON p.mentee_email = u.email WHERE p.mentor_email=?", (email,))
                for r in c.fetchall(): res["pairs"].append({"name": f"{r[0]} {r[1]}", "email": r[2], "pair_id": r[3], "type": "Mentee"})
            elif role == 'Mentee':
                c.execute("SELECT u.first_name, u.last_name, u.email, p.id FROM MentorMenteePair p JOIN Users u ON p.mentor_email = u.email WHERE p.mentee_email=?", (email,))
                for r in c.fetchall(): res["pairs"].append({"name": f"{r[0]} {r[1]}", "email": r[2], "pair_id": r[3], "type": "Mentor"})
            elif is_c or role == 'ProgramStaff':
                c.execute("SELECT m.first_name, m.last_name, s.first_name, s.last_name, p.id, m.email, s.email FROM MentorMenteePair p JOIN Users m ON p.mentor_email = m.email JOIN Users s ON p.mentee_email = s.email")
                for r in c.fetchall(): res["pairs"].append({"mentor_name": f"{r[0]} {r[1]}", "mentee_name": f"{r[2]} {r[3]}", "mentor_email": r[5], "mentee_email": r[6], "pair_id": r[4]})

            c.execute("SELECT id, name, type, size, category, description, url FROM Resources")
            res["resources"] = [{"id": r[0], "name": r[1], "type": r[2], "size": r[3], "category": r[4], "description": r[5], "url": r[6]} for r in c.fetchall()]
            
            conn.close()
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(res).encode())
        except Exception as e:
            self.send_error_json(500, str(e))

    def handle_link_profile(self, email, uid):
        try:
            conn = sqlite3.connect(DATABASE); c = conn.cursor()
            c.execute("UPDATE Users SET id = ? WHERE email = ?", (uid, email))
            conn.commit(); conn.close()
            supabase.table('profiles').update({"id": uid}).eq('email', email).execute()
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(b'{"success": true}')
        except Exception as e: self.send_error_json(500, str(e))

    def handle_admin_data_routing(self):
        user = get_user_from_headers(self.headers)
        if not is_approved_admin(user): self.send_response(403); self.end_headers(); return
        self.handle_admin_data()

    def do_POST(self):
        try:
            raw_path = self.path.split('?')[0].rstrip('/')
            if not raw_path: raw_path = '/'
            cl = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(cl).decode('utf-8')) if cl > 0 else {}
            
            if raw_path == '/api/login' or raw_path == '/api/verify_password': self.handle_login(data)
            elif raw_path == '/api/visitor': self.handle_visitor(data)
            elif raw_path == '/api/visitor/verify': self.handle_visitor_verify(data)
            elif raw_path == '/api/resources/upload': self.handle_upload_resource(data)
            elif raw_path == '/api/resources/delete': self.handle_delete_resource(data)
            elif raw_path == '/api/messages': self.handle_send_message(data)
            elif raw_path == '/api/register': self.handle_register(data)
            elif raw_path == '/api/sessions/schedule': self.handle_schedule(data)
            elif raw_path == '/api/survey/submit': self.handle_survey_submit(data)
            elif raw_path.startswith('/api/admin'): self.handle_admin_routing(raw_path, data)
            else: self.send_error_json(404, "Not Found")
        except Exception as e: self.send_error_json(500, str(e))

    def handle_admin_routing(self, path, data):
        if 'create' in path: self.handle_admin_create(data)
        elif 'pair' in path: self.handle_admin_pair(data)
        elif 'delete' in path: self.handle_admin_delete(data)
        elif 'update_profile' in path: self.handle_admin_update_profile(data)
        elif 'data' in path: self.handle_admin_data()

    def handle_admin_create(self, data):
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        email, fn, ln, role = data.get('email'), data.get('firstName'), data.get('lastName'), data.get('role')
        try:
             c.execute("INSERT OR REPLACE INTO Users (email, first_name, last_name, password, role) VALUES (?, ?, ?, ?, ?)", (email, fn, ln, '', role))
             conn.commit()
             supabase.table('profiles').upsert({'email': email, 'first_name': fn, 'last_name': ln, 'role': role}, on_conflict='email').execute()
             self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')
        finally: conn.close()
             
    def handle_admin_pair(self, data):
        conn = sqlite3.connect(DATABASE)
        m, e = data.get('mentor'), data.get('mentee')
        try:
             conn.execute("INSERT OR IGNORE INTO MentorMenteePair (mentor_email, mentee_email) VALUES (?, ?)", (m, e))
             conn.commit()
             supabase.table('mentor_mentee_pairs').upsert({'mentor_email': m, 'mentee_email': e}, on_conflict='mentor_email,mentee_email').execute()
             self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')
        finally: conn.close()

    def handle_schedule(self, data):
        u = get_user_from_headers(self.headers)
        if not u: self.send_response(401); self.end_headers(); return
        pid, start, link = data.get('pair_id'), data.get('start_time'), data.get('link', '')
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("INSERT INTO Sessions (pair_id, start_time, meeting_link, scheduled_by) VALUES (?, ?, ?, ?)", (pid, start, link, u['email']))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_register(self, data):
        e, pwd = data.get('email'), data.get('password')
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("UPDATE Users SET password=? WHERE email=?", (pwd, e))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def verify_password(self, email, pwd):
        email = email.lower().strip()
        if (email == 'admin@stars.ae' and pwd == 'STARS2026') or (email == 'dummy.counselor@naischool.ae' and pwd == 'pass'):
             return {"firstName": "STARS", "lastName": "Admin", "role": "ProgramStaff", "isCounselor": True}
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("SELECT first_name, last_name, role FROM Users WHERE email=? AND password=?", (email, pwd))
        r = c.fetchone(); conn.close()
        if r: return {"firstName": r[0], "lastName": r[1], "role": r[2], "isCounselor": r[2] == 'ProgramStaff'}
        return None

    def handle_login(self, data):
        u = self.verify_password(data.get('email'), data.get('password'))
        if u:
            token = str(uuid.uuid4())
            SESSION_STORE[token] = u
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"success": True, "token": token, "user": u}).encode())
        else: self.send_error_json(401, "Failed")

    def get_initial_data(self):
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
        self.wfile.write(b'{"status": "Online"}')

    def handle_visitor(self, data):
        otp = str(random.randint(100000, 999999))
        OTP_STORE[data.get('email')] = {"otp": otp, "fname": data.get('firstName'), "lname": data.get('lastName')}
        print(f"OTP for {data.get('email')}: {otp}")
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_visitor_verify(self, data):
        e, c = data.get('email'), data.get('code')
        if e in OTP_STORE and OTP_STORE[e]['otp'] == c:
            token = str(uuid.uuid4())
            user = {"role": "Visitor", "name": f"{OTP_STORE[e]['fname']} {OTP_STORE[e]['lname']}"}
            SESSION_STORE[token] = user
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps({"success": True, "token": token, "user": user}).encode())
        else: self.send_response(401); self.end_headers()

    def handle_send_message(self, data):
        u = get_user_from_headers(self.headers)
        if not u: self.send_response(401); self.end_headers(); return
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("INSERT INTO Messages (pair_id, sender_email, message, timestamp) VALUES (?, ?, ?, ?)", (data.get('pair_id'), u['email'], data.get('message'), ts))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_get_resources(self):
        try:
            res = supabase.table('resources').select('*').execute()
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(res.data or []).encode())
        except: self.send_response(500); self.end_headers()

    def handle_upload_resource(self, data):
        u = get_user_from_headers(self.headers)
        if not u: self.send_error_json(403, "Access Denied"); return
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            payload = {"name": data.get('name'), "type": data.get('type'), "timestamp": ts, "uploaded_by": u['email']}
            res = supabase.table('resources').insert(payload).execute()
            rid = res.data[0]['id']
            conn = sqlite3.connect(DATABASE); c = conn.cursor()
            c.execute("INSERT INTO Resources (id, name, type, uploaded_by, timestamp, category, description, url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                      (rid, data.get('name'), data.get('type'), u['email'], ts, data.get('category'), data.get('description'), data.get('url')))
            conn.commit(); conn.close()
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')
        except Exception as e: self.send_error_json(500, str(e))

    def send_error_json(self, code, message):
        self.send_response(code); self.send_header('Content-type', 'application/json'); self.end_headers()
        self.wfile.write(json.dumps({"success": False, "error": message}).encode())

    def handle_delete_resource(self, data):
        rid = data.get('id')
        DELETED_RESOURCES_BLOCKLIST.add(str(rid))
        supabase.table('resources').delete().eq('id', rid).execute()
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("DELETE FROM Resources WHERE id=?", (rid,))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_get_messages(self, pair_id):
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("SELECT sender_email, message, timestamp FROM Messages WHERE pair_id=? ORDER BY id ASC", (pair_id,))
        m = [{"sender": r[0], "message": r[1], "timestamp": r[2]} for r in c.fetchall()]; conn.close()
        self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
        self.wfile.write(json.dumps(m).encode())

    def handle_admin_update_profile(self, data):
        e, t, b, i = data.get('email'), data.get('title'), data.get('bio'), data.get('interests')
        supabase.table('profiles').update({"title": t, "bio": b, "interests": i}).eq('email', e).execute()
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        c.execute("UPDATE Users SET title=?, bio=?, interests=? WHERE email=?", (t, b, i, e))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_survey_submit(self, data):
        u = get_user_from_headers(self.headers)
        if not u: self.send_response(401); self.end_headers(); return
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st = data.get('survey_type', 'General')
        conn = sqlite3.connect(DATABASE); c = conn.cursor()
        for q, a in data.items():
            if q != 'survey_type': c.execute("INSERT INTO Surveys (user_email, question, answer, timestamp, survey_type) VALUES (?, ?, ?, ?, ?)", (u['email'], q, str(a), ts, st))
        conn.commit(); conn.close()
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_survey_analytics(self):
        self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
        self.wfile.write(b'{"surveys": [], "trends": []}')

    def handle_admin_data(self):
        res = supabase.table('profiles').select('*').execute()
        data = {"users": [{"email": r['email'], "name": f"{r.get('first_name','')} {r.get('last_name','')}", "role": r.get('role')} for r in res.data], "pairs": []}
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
        self.wfile.write(json.dumps(data).encode())

# Execute Boot Sequence
if __name__ == "__main__":
    print(">>> STARS BOOT: Initializing Database...")
    init_db()
    
    print(f">>> STARS BOOT: Starting ThreadingHTTPServer on port {PORT}...")
    server_address = ('', PORT)
    httpd = http.server.ThreadingHTTPServer(server_address, STARSAPIHandler)
    print(f"STARS Portal Live: Listening on port {PORT} (THREADED)")
    httpd.serve_forever()
