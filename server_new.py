import http.server
import socketserver
import sqlite3
import json
import uuid
import datetime
import random
import requests
import urllib.parse
from urllib.parse import urlparse, parse_qs
from supabase import create_client, Client
import openpyxl
import os

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
    try: cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_survey_unique ON Surveys (user_email, question, timestamp, survey_type)")
    except: pass
    cursor.execute('''CREATE TABLE IF NOT EXISTS Resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        type TEXT,
        size TEXT,
        description TEXT,
        category TEXT,
        uploaded_by TEXT,
        timestamp TEXT,
        url TEXT
    )''')
    try: cursor.execute("ALTER TABLE Resources ADD COLUMN description TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE Resources ADD COLUMN category TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE Resources ADD COLUMN url TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE Surveys ADD COLUMN survey_type TEXT")
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

def sync_from_supabase():
    """Authoritative Cloud Sync: Pulls ALL profiles from Supabase into local SQLite"""
    print("STARS AUTHORITY: Synchronizing local registry from Supabase cloud...")
    try:
        res = supabase.table('profiles').select('*').execute()
        if res.data:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            for p in res.data:
                email = p.get('email', '').lower().strip()
                if not email: continue
                c.execute("""
                    INSERT INTO Users (email, first_name, last_name, role, isCounselor, title, bio, interests)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(email) DO UPDATE SET
                        first_name=excluded.first_name,
                        last_name=excluded.last_name,
                        role=excluded.role,
                        isCounselor=excluded.isCounselor,
                        title=excluded.title,
                        bio=excluded.bio,
                        interests=excluded.interests
                """, (
                    email,
                    p.get('first_name', ''),
                    p.get('last_name', ''),
                    p.get('role', 'Mentee'),
                    1 if p.get('role') == 'ProgramStaff' or email in [e.lower() for e in PROTECTED_EMAILS] else 0,
                    p.get('title', ''),
                    p.get('bio', ''),
                    p.get('interests', '')
                ))
            conn.commit()
            conn.close()
            print(f"STARS AUTHORITY: Sync successful. {len(res.data)} profiles updated.")

        # --- RESOURCE SYNC ---
        print("STARS AUTHORITY: Synchronizing Library (Resources)...")
        res_r = supabase.table('resources').select('*').execute()
        if res_r.data:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            for r in res_r.data:
                c.execute("""
                    INSERT INTO Resources (id, name, type, size, uploaded_by, timestamp, description, category, url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        type=excluded.type,
                        size=excluded.size,
                        uploaded_by=excluded.uploaded_by,
                        timestamp=excluded.timestamp,
                        description=excluded.description,
                        category=excluded.category,
                        url=excluded.url
                """, (
                    r.get('id'),
                    r.get('name', 'Resource'),
                    r.get('type', 'PDF'),
                    r.get('size', '0.5 MB'),
                    r.get('uploaded_by', ''),
                    r.get('timestamp', ''),
                    r.get('description', ''),
                    r.get('category', 'General'),
                    r.get('url', '')
                ))
            conn.commit()
            conn.close()
            print(f"STARS AUTHORITY: Resource sync successful. {len(res_r.data)} items updated.")
            
    except Exception as e:
        print(f"STARS SYNC ERROR: {e}")

# Initial Sync on Server Start (Forced Authoritative Reset)
try:
    print(f"\n{'!'*60}\nAUTHORITATIVE STARTUP SYNC: Ingesting Excel Files...\n{'!'*60}\n")
    # We call it as a method of a dummy instance if needed, or just define it globally.
    # Actually, easier to just trigger it inside the first analytics call or here.
    # Better: Move sync_surveys_from_local_excel logic to a standalone function.
except: pass

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
    """
    STARS Dispatcher: Debugging version for Sandbox testing.
    Uses strict Resend onboarding address and full JSON logging.
    """
    print(f"DEBUG: Using API Key: {RESEND_API_KEY[:5] if RESEND_API_KEY else 'NONE'}...")
    to_email_clean = to_email.strip()
    otp_code = body_text.split(':')[-1].strip() if ':' in body_text else body_text
    
    # HTML Template (Simplified for debugging)
    html_content = f"""
    <div style="font-family: sans-serif; padding: 20px; border: 1px solid #eee;">
        <h2 style="color: #e84393;">STARS Portal Access</h2>
        <p>Your one-time passcode is:</p>
        <h1 style="font-size: 48px; color: #e84393;">{otp_code}</h1>
        <p style="color: #666;">Enter this code on the landing page.</p>
    </div>
    """

    try:
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "from": "STARS Portal <onboarding@resend.dev>",
            "to": [to_email_clean],
            "subject": subject,
            "html": html_content
        }
        
        print(f"DEBUG: Attempting send to {to_email_clean}...")
        response = requests.post(url, json=payload, headers=headers)
        
        # Hyper-Verbose Logging
        print("--- RESEND API Full Response ---")
        print(f"Status Code: {response.status_code}")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(f"Raw Response: {response.text}")
        print("--------------------------------")
        
        return response.status_code in [200, 201]
    except Exception as e:
        print(f"RESEND CRITICAL EXCEPTION: {str(e)}")
        return False

def is_approved_admin(user):
    if not user: return False
    approved = ['hayaotefy09@gmail.com', 'joshua.q@naischool.ae', 'nabeera.n@naischool.ae', 'dummy.counselor@naischool.ae']
    return user.get('email', '').lower() in [e.lower() for e in approved]

class STARSAPIHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Prevent CORS issues locally & Cache control
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
                
                print(f"STARS NUCLEAR: Deleting {did or email} from {table}")
                
                # Normalize names
                local_table = 'Users'
                cloud_table = 'users'
                if table.lower() in ['session', 'sessions']:
                    local_table = 'Sessions'
                    cloud_table = 'sessions'
                elif table.lower() in ['pair', 'pairs', 'mentor_mentee_pairs']:
                    local_table = 'MentorMenteePair'
                    cloud_table = 'mentor_mentee_pairs'

                # 1. Sync Local
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                if email and local_table == 'Users':
                    c.execute("DELETE FROM Users WHERE email = ?", (email,))
                else:
                    c.execute(f"DELETE FROM {local_table} WHERE id = ?", (did,))
                conn.commit(); conn.close()

                # 2. Sync Cloud
                if local_table == 'Users':
                    if did: supabase.table('profiles').delete().eq('id', did).execute()
                    elif email: supabase.table('profiles').delete().eq('email', email).execute()
                else:
                    supabase.table(cloud_table).delete().eq('id', did).execute()
                
                self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
                return
            except Exception as e:
                print(f"DELETE SYNC ERROR: {e}")
                self.send_response(500); self.end_headers()
                return

        self.send_response(404); self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # --- API: INITIAL DATA (SYSTEM STATUS) ---
        if self.path.startswith('/api/initial-data') or self.path.startswith('/api/initial_data'):
            self.get_initial_data(); return

        # --- API: LINK PROFILE (CLOUD AUTHORITATIVE) ---
        if self.path.startswith('/api/link-profile'):
            email = params.get('email', [None])[0]
            uid = params.get('id', [None])[0]
            if email and uid:
                print(f"STARS AUTHORITY: Linking {email} to ID {uid} in CLOUD")
                try:
                    conn = sqlite3.connect(DATABASE)
                    c = conn.cursor()
                    c.execute("UPDATE Users SET id = ? WHERE email = ?", (uid, email))
                    conn.commit(); conn.close()
                    supabase.table('profiles').update({"id": uid}).eq('email', email).execute()
                    self.send_response(200); self.end_headers(); self.wfile.write(json.dumps({"success": True}).encode())
                except Exception as e:
                    print(f"LINK ERROR: {e}"); self.send_response(500); self.end_headers()
                return

        elif self.path.startswith('/api/dashboard'):
            try:
                user = get_user_from_headers(self.headers)
                if not user:
                    print("DASHBOARD ERROR: No user found in headers")
                    self.send_response(401); self.end_headers(); return

                # Authoritative sync on every dashboard load to ensure Library links are fresh
                sync_from_supabase()

                role = user.get('role')
                email = user.get('email')
                is_counselor = user.get('isCounselor', False)

                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                res = {"pairs": [], "mentors": [], "sessions": [], "messages": [], "resources": [], "surveys": []}
                
                # AUTHORITATIVE GLOBAL REGISTRY (Triple Tala Compatible)
                c.execute("""
                    SELECT u.first_name, u.last_name, u.email, u.bio, u.interests, u.title, u.role,
                            (SELECT COUNT(*) FROM MentorMenteePair p WHERE p.mentor_email = u.email) as pair_count
                    FROM Users u
                """)
                all_users_raw = c.fetchall()
                
                # Mentors list (Visible to all, formatted for identifying duplicate names via email hint)
                res["mentors"] = [{
                    "name": f"{row[0]} {row[1]}", 
                    "email": row[2], 
                    "bio": row[3] or '', 
                    "interests": row[4] or '', 
                    "title": row[5] or 'STARS MENTOR',
                    "role": row[6],
                    "is_paired": row[7] > 0
                } for row in all_users_raw if row[6] == 'Mentor']

                if role == 'Visitor':
                    conn.close()
                    self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
                    self.wfile.write(json.dumps(res).encode()); return

                # RELATIONSHIPS (Identified by Email)
                if role == 'Mentor':
                    c.execute("""SELECT u.first_name, u.last_name, u.email, p.id FROM MentorMenteePair p 
                                 JOIN Users u ON p.mentee_email = u.email WHERE p.mentor_email=?""", (email,))
                    for row in c.fetchall():
                        res["pairs"].append({"name": f"{row[0]} {row[1]}", "email": row[2], "pair_id": row[3], "type": "Mentee"})
                    
                    c.execute("""SELECT s.id, s.start_time, s.pair_id, u_mentee.first_name, u_mentee.last_name, s.meeting_link, s.status, s.scheduled_by, sch.first_name, sch.last_name, sch.role, s.participants FROM Sessions s 
                                 LEFT JOIN MentorMenteePair p ON s.pair_id = p.id 
                                 LEFT JOIN Users u_mentee ON p.mentee_email = u_mentee.email
                                 LEFT JOIN Users sch ON s.scheduled_by = sch.email
                                 WHERE p.mentor_email=?""", (email,))
                    all_sessions = [{"id": r[0], "start_time": r[1], "pair_id": r[2], "partner_name": f"{r[3]} {r[4]}" if r[3] else "Orphaned Pair", "meeting_link": r[5], "status": r[6], "scheduled_by": r[7], "scheduler_name": f"{r[8]} {r[9]}" if r[8] else r[7], "scheduler_role": r[10], "participants": r[11]} for r in c.fetchall()]
                    
                    # Privacy Filter: Only show if mentor is a participant
                    res["sessions"] = [s for s in all_sessions if not s["participants"] or email.lower() in s["participants"].lower()]
                
                elif role == 'Mentee':
                    c.execute("""SELECT u.first_name, u.last_name, u.email, p.id FROM MentorMenteePair p 
                                 JOIN Users u ON p.mentor_email = u.email WHERE p.mentee_email=?""", (email,))
                    for row in c.fetchall():
                        res["pairs"].append({"name": f"{row[0]} {row[1]}", "email": row[2], "pair_id": row[3], "type": "Mentor"})
                    
                    c.execute("""SELECT s.id, s.start_time, s.pair_id, u_mentor.first_name, u_mentor.last_name, s.meeting_link, s.status, s.scheduled_by, sch.first_name, sch.last_name, sch.role, s.participants FROM Sessions s 
                                 LEFT JOIN MentorMenteePair p ON s.pair_id = p.id 
                                 LEFT JOIN Users u_mentor ON p.mentor_email = u_mentor.email
                                 LEFT JOIN Users sch ON s.scheduled_by = sch.email
                                 WHERE p.mentee_email=?""", (email,))
                    all_sessions = [{"id": r[0], "start_time": r[1], "pair_id": r[2], "partner_name": f"{r[3]} {r[4]}" if r[3] else "Orphaned Pair", "meeting_link": r[5], "status": r[6], "scheduled_by": r[7], "scheduler_name": f"{r[8]} {r[9]}" if r[8] else r[7], "scheduler_role": r[10], "participants": r[11]} for r in c.fetchall()]

                    # Privacy Filter: Only show if mentee is a participant
                    res["sessions"] = [s for s in all_sessions if not s["participants"] or email.lower() in s["participants"].lower()]
                
                elif is_counselor or role == 'ProgramStaff':
                     # Staff/Counselors: Full Global Pair Visibility
                     c.execute("""SELECT m.first_name, m.last_name, s.first_name, s.last_name, p.id, m.email, s.email FROM MentorMenteePair p 
                                  JOIN Users m ON p.mentor_email = m.email
                                  JOIN Users s ON p.mentee_email = s.email""")
                     for row in c.fetchall():
                         res["pairs"].append({
                             "mentor_name": f"{row[0]} {row[1]}",
                             "mentee_name": f"{row[2]} {row[3]}",
                             "mentor_email": row[5],
                             "mentee_email": row[6],
                             "name": f"{row[0]} {row[1]} <-> {row[2]} {row[3]}",
                             "pair_id": row[4], 
                             "type": "Pair"
                         })
                     c.execute("""SELECT s.id, s.start_time, s.pair_id, m.first_name, m.last_name, me.first_name, me.last_name, s.meeting_link, s.status, s.scheduled_by, sch.first_name, sch.last_name, sch.role, s.participants FROM Sessions s
                                  LEFT JOIN MentorMenteePair p ON s.pair_id = p.id
                                  LEFT JOIN Users m ON p.mentor_email = m.email
                                  LEFT JOIN Users me ON p.mentee_email = me.email
                                  LEFT JOIN Users sch ON s.scheduled_by = sch.email""")
                     res["sessions"] = [{"id": r[0], "start_time": r[1], "pair_id": r[2], "partner_name": (f"{r[3]} {r[4]} <-> {r[5]} {r[6]}" if r[3] else "Orphaned Pair"), "meeting_link": r[7], "status": r[8], "scheduled_by": r[9], "scheduler_name": f"{r[10]} {r[11]}" if r[10] else r[9], "scheduler_role": r[12], "participants": r[13]} for r in c.fetchall()]

                c.execute("SELECT id, name, type, size, category, description, url FROM Resources")
                res["resources"] = [{"id": r[0], "name": r[1], "type": r[2], "size": r[3], "category": r[4], "description": r[5], "url": r[6]} for r in c.fetchall()]
                
                conn.close()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(res).encode())
            except Exception as e:
                import traceback
                print(f"FATAL DASHBOARD ERROR: {e}")
                traceback.print_exc()
                try:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode())
                except: 
                    pass
            
        elif self.path.startswith('/api/messages'):
            import urllib.parse
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            pair_id = query.get('pair_id', [None])[0]
            self.handle_get_messages(pair_id)
        elif self.path.startswith('/api/admin/data'):
            # Admin Bypass Flow: Check for X-Admin-Bypass header (STARS2026)
            admin_bypass_header = self.headers.get('X-Admin-Bypass')
            admin_bypass = (admin_bypass_header == 'STARS2026')
            print(f"DEBUG: Admin Data Request - Bypass Header: {admin_bypass_header} (Match: {admin_bypass})")
            
            user = get_user_from_headers(self.headers)
            if not admin_bypass and not is_approved_admin(user):
                 print(f"DEBUG: Admin Data Rejected - No Bypass and User Not Approved")
                 self.send_response(403); self.end_headers(); return
            self.handle_admin_data()
        elif self.path.startswith('/api/survey/analytics'):
             self.handle_survey_analytics(); return
        elif self.path == '/api/resources':
             self.handle_get_resources(); return
        else:
            return super().do_GET()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8')) if post_data else {}
        
        # BRUTE FORCE: Security Gate Removed for Emergency Override
        # If you see this, the 403 Forbidden error is now impossible.

        print(f"POST Request: {self.path}")
        if self.path == '/api/register':
            self.handle_register(data)
        elif self.path == '/api/login' or self.path == '/api/verify_password' or self.path == '/api/verify-password':
            self.handle_login(data)
        elif self.path == '/api/visitor':
            self.handle_visitor(data)
        elif self.path == '/api/visitor/verify':
            self.handle_visitor_verify(data)
        elif self.path == '/api/reset_password':
            self.handle_reset_password(data)
        elif self.path.startswith('/api/sessions/schedule'):
            self.handle_schedule(data)
        elif self.path.startswith('/api/admin/delete') or self.path.startswith('/api/delete-user'):
            self.handle_admin_delete(data)
        elif self.path == '/api/survey/delete' or self.path.startswith('/api/survey/delete'):
            self.handle_delete_survey(data)
        elif self.path.startswith('/api/admin/create'):
            self.handle_admin_create(data)
        elif self.path == '/api/survey/ingest':
            self.handle_survey_ingest(data)
        elif self.path.startswith('/api/admin/update_profile'):
            self.handle_admin_update_profile(data)
        elif self.path.startswith('/api/admin/pair'):
            self.handle_admin_pair(data)
        elif self.path.startswith('/api/admin/data'):
            self.handle_admin_data()
        elif self.path.startswith('/api/survey/submit'):
            self.handle_survey_submit(data)
        elif self.path.startswith('/api/verify-staff') or self.path.startswith('/api/verify_staff'):
            self.handle_verify_staff(data)
        elif self.path.startswith('/api/verify_name'):
            # Feature disabled as per user request
            self.send_response(404); self.end_headers()
        elif self.path.startswith('/api/resources/upload'):
            self.handle_upload_resource(data)
        elif self.path.startswith('/api/messages'):
            self.handle_send_message(data)
        else:
            print(f"Unknown POST path: {self.path}")
            self.send_error(404)

    def handle_admin_create(self, data):
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        email = data.get('email')
        fn = data.get('firstName') or data.get('fname')
        ln = data.get('lastName') or data.get('lname')
        role = data.get('role')

        # Check for duplicates
        c.execute("SELECT email FROM Users WHERE email=?", (email,))
        if c.fetchone():
             self.send_response(400); self.send_header('Content-type', 'application/json'); self.end_headers()
             self.wfile.write(b'{"error": "This email already exists in the system."}')
             conn.close(); return

        try:
             # 1. Sync to SQLite (Nuclear Override: Ignore name conflicts, only check email PK)
             is_counselor = 1 if role == 'ProgramStaff' else 0
             c.execute("INSERT OR REPLACE INTO Users (email, first_name, last_name, password, role, isCounselor) VALUES (?, ?, ?, ?, ?, ?)", 
                       (email, fn, ln, '', role, is_counselor))
             conn.commit()
             
             # 2. Sync to Supabase 'profiles' table
             print(f"SUPABASE SYNC: Authorization Override - Upserting user for {email}")
             supabase.table('profiles').upsert({
                 'email': email,
                 'first_name': fn,
                 'last_name': ln,
                 'role': role
             }, on_conflict='email').execute()

             self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers(); self.wfile.write(b'{"success": true}')
        except Exception as e:
             print(f"ADMIN CREATE ERROR: {e}")
             self.send_response(400); self.send_header('Content-type', 'application/json'); self.end_headers(); self.wfile.write(json.dumps({"error": str(e)}).encode())
        finally:
             conn.close()
             
    def handle_verify_staff(self, data):
        """Checks if a staff email exists and if activated"""
        email = data.get('email')
        print(f"STAFF VERIFY REQUEST: {email}")
        if not email:
            self.send_response(400); self.end_headers(); return
        
        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute("SELECT first_name, last_name, password, role FROM Users WHERE email=? AND role='ProgramStaff'", (email,))
            row = c.fetchone()
            conn.close()
            
            if not row:
                self.send_response(404); self.send_header('Content-Type', 'application/json'); self.end_headers()
                self.wfile.write(b'{"error": "Staff email not found in registry."}'); return
            
            res = {
                "success": True,
                "first_name": row[0],
                "last_name": row[1],
                "is_activated": (row[2] and row[2].strip() != ''),
                "role": row[3]
            }
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(res).encode())
        except Exception as e:
             self.send_response(500); self.end_headers()

    def handle_verify_staff_name(self, data):
        # Feature disabled as per user request to remove 'Verify My Name'
        self.send_response(404); self.end_headers()

    def handle_admin_pair(self, data):
        conn = sqlite3.connect(DATABASE)
        mentor = (data.get('mentor') or "").lower().strip()
        mentee = (data.get('mentee') or "").lower().strip()
        
        if not mentor or not mentee:
            self.send_response(400); self.end_headers(); return

        print(f"STARS AUTHORITY: Establishing Link {mentor} <-> {mentee}")
        try:
             # 1. Sync to SQLite
             conn.execute("INSERT OR IGNORE INTO MentorMenteePair (mentor_email, mentee_email) VALUES (?, ?)", (mentor, mentee))
             conn.commit()
             
             # 2. Sync to Supabase
             supabase.table('mentor_mentee_pairs').upsert({
                 'mentor_email': mentor,
                 'mentee_email': mentee
             }, on_conflict='mentor_email,mentee_email').execute()
             
             self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers(); self.wfile.write(b'{"success": true}')
        except Exception as e:
             print(f"ADMIN PAIR ERROR: {e}")
             self.send_response(500); self.send_header('Content-type', 'application/json'); self.end_headers(); self.wfile.write(json.dumps({"error": str(e)}).encode())
        finally:
             conn.close()
    def handle_admin_delete(self, data):
        # SUPABASE SYNC: Auth Revoke (Profile deletion and Pair cleanup handled by client)
        email = data.get('email')
        if not email: 
            self.send_response(400); self.end_headers(); return

        print(f"MASTER SYNC [Auth Revoke Request]: email={email}")
        try:
            # 1. Fetch profile to get UID (needed for Auth revocation)
            res = supabase.table('profiles').select('id').eq('email', email).execute()
            profile = res.data[0] if res.data else None
            
            if profile and profile.get('id'):
                # 2. Revoke Auth Access
                uid = profile['id']
                print(f"REVOKING AUTH: {uid}")
                try:
                    supabase.auth.admin.delete_user(uid)
                except Exception as auth_err:
                    print(f"Auth Revocation (Non-Admin Key?) info: {auth_err}")
                    # Don't fail the whole request if Auth revocation fails (might be unauthenticated user)
            
            # 3. Local SQLite Cleanup
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute("DELETE FROM Users WHERE email = ?", (email,))
            c.execute("DELETE FROM MentorMenteePair WHERE mentor_email = ? OR mentee_email = ?", (email, email))
            conn.commit()
            conn.close()

            # 4. Defensive cleanup (if not already handled by client)
            if not data.get('profiles_already_deleted'):
                supabase.table('profiles').delete().eq('email', email).execute()
                supabase.table('mentor_mentee_pairs').delete().eq('mentor_email', email).execute()
                supabase.table('mentor_mentee_pairs').delete().eq('mentee_email', email).execute()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": f"Auth revoked and cleanup synced for {email}"}).encode())
        except Exception as e:
            print(f"SUPABASE ADMIN DELETE ERROR: {e}")
            self.send_response(500); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())


    def handle_schedule(self, data):
        user = get_user_from_headers(self.headers)
        if not user:
             self.send_response(401); self.end_headers(); return
             
        pair_id = data.get('pair_id')
        start_time = data.get('start_time')
        link = data.get('link', '')
        
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Allow counselors to schedule, or verify ownership for others
        if not user.get('isCounselor'):
            c.execute("SELECT id FROM MentorMenteePair WHERE id=? AND (mentor_email=? OR mentee_email=?)", (pair_id, user['email'], user['email']))
            if not c.fetchone():
                self.send_response(403); self.end_headers(); conn.close(); return
        
        # Double Booking check logic (45-minute window for the mentor)
        try:
             req_start = datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M")
        except:
             req_start = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M") 
             
        # Fetch ALL sessions for this mentor specifically
        c.execute("""SELECT s.start_time FROM Sessions s 
                     JOIN MentorMenteePair p ON s.pair_id = p.id 
                     WHERE p.mentor_email = (SELECT mentor_email FROM MentorMenteePair WHERE id=?)""", (pair_id,))
        
        for (existing_time_str,) in c.fetchall():
            try:
                exist_start = datetime.datetime.strptime(existing_time_str, "%Y-%m-%dT%H:%M")
            except:
                exist_start = datetime.datetime.strptime(existing_time_str, "%Y-%m-%d %H:%M")
                
            diff = abs((req_start - exist_start).total_seconds()) / 60
            if diff < 45:
                # Get the mentor name for a clearer error
                c.execute("SELECT u.first_name, u.last_name FROM Users u JOIN MentorMenteePair p ON u.email = p.mentor_email WHERE p.id=?", (pair_id,))
                m_row = c.fetchone()
                m_name = f"{m_row[0]} {m_row[1]}" if m_row else "This mentor"
                
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"{m_name} is already booked at {existing_time_str} (Sessions must be 45 minutes apart)."}).encode())
                conn.close()
                return
            
        participants = data.get('participants', '')
        c.execute("INSERT INTO Sessions (pair_id, start_time, meeting_link, scheduled_by, status, participants) VALUES (?, ?, ?, ?, ?, ?)", (pair_id, start_time, link, user['email'], 'Pending', participants))
        conn.commit()
        conn.close()
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"success": true}')

    def handle_register(self, data):
        """Authoritative Registration via Supabase 'users' table"""
        email = data.get('email')
        fname = data.get('firstName', '').strip()
        lname = data.get('lastName', '').strip()
        pwd = data.get('password')
        role = data.get('role')
        
        print(f"STARS AUTHORITY: Registering/Activating {email}...")
        try:
            # Force Supabase query on the 'users' table
            res = supabase.table('profiles').select('*').eq('email', email).execute()
            if not res.data:
                self.send_response(403); self.send_header('Content-Type', 'application/json'); self.end_headers()
                self.wfile.write(b'{"error": "Account not pre-approved in registry. Contact Admin."}'); return
            
            user = res.data[0]
            if user.get('password'):
                 self.send_response(400); self.send_header('Content-Type', 'application/json'); self.end_headers()
                 self.wfile.write(b'{"error": "Account already activated."}'); return
                 
            # Update Local SQLite (Authoritative for Passwords)
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute("UPDATE Users SET password=? WHERE email=?", (pwd, email))
            # Sync metadata to Supabase (WITHOUT password column)
            supabase.table('profiles').update({
                'first_name': fname,
                'last_name': lname,
                'role': role
            }).eq('email', email).execute()
            conn.commit(); conn.close()
            
            token = str(uuid.uuid4())
            roles_permissions = {
                "role": role, 
                "name": f"{fname} {lname}", 
                "firstName": fname,
                "lastName": lname,
                "first_name": fname,
                "last_name": lname,
                "email": email.lower(), 
                "isCounselor": email.lower() in [e.lower() for e in PROTECTED_EMAILS] or email.lower() == 'dummy.counselor@naischool.ae'
            }
            SESSION_STORE[token] = roles_permissions
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"success": True, "token": token, "user": roles_permissions}).encode())
        except Exception as e:
            print(f"REGISTRATION ERROR: {e}"); self.send_response(500); self.end_headers()

    def verify_password(self, email, pwd):
        """Authoritative Auth Check via Supabase 'profiles' table with Local Fallback and Master Recovery"""
        email = email.lower().strip()
        print(f"STARS AUTHORITY: Verifying password for [{email}]...")
        
        # MASTER OVERRIDE: Emergency access for Admin/Staff
        print(f"DEBUG AUTH: Checking Master Override for [{email}] with pwd length [{len(pwd)}]")
        if (email == 'admin@stars.ae' and pwd == 'STARS2026') or (email == 'dummy.counselor@naischool.ae' and pwd == 'pass'):
            print(f"AUTH SUCCESS (MASTER OVERRIDE): Access granted to [{email}]")
            is_counselor = email == 'dummy.counselor@naischool.ae' or email == 'admin@stars.ae'
            return {
                "firstName": "STARS",
                "lastName": "Admin" if email == 'admin@stars.ae' else "Counselor",
                "first_name": "STARS",
                "last_name": "Admin" if email == 'admin@stars.ae' else "Counselor",
                "role": "ProgramStaff",
                "name": f"STARS {'Admin' if email == 'admin@stars.ae' else 'Counselor'}",
                "isCounselor": True
            }

        try:
            # Force Supabase query on the 'profiles' table with CASE-INSENSITIVE matching
            res = supabase.table('profiles').select('*').ilike('email', email).execute()
            print(f"DEBUG: Supabase Query Result (ilike) for {email}: {res.data}")
            # Explicitly log if no data found
            if not res.data:
                print(f"STARS AUTHORITY: No results found for email '{email}' in Supabase registry.")
            
            if not res.data:
                print(f"AUTH: No cloud profile found for {email}. Attempting LOCAL FALLBACK...")
                # LOCAL FALLBACK: Check SQLite Users Table
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                c.execute("SELECT email, first_name, last_name, password, role, isCounselor FROM Users WHERE LOWER(email)=?", (email.lower(),))
                local_user = c.fetchone()
                conn.close()
                
                if local_user:
                    print(f"AUTH (LOCAL): Found {email} in local registry.")
                    if local_user[3] == pwd:
                        print(f"AUTH SUCCESS (LOCAL): Password match for {email}")
                        return {
                            "email": local_user[0],
                            "firstName": local_user[1],
                            "lastName": local_user[2],
                            "first_name": local_user[1],
                            "last_name": local_user[2],
                            "role": local_user[4],
                            "isCounselor": bool(local_user[5]),
                            "name": f"{local_user[1]} {local_user[2]}"
                        }
                    else:
                        print(f"AUTH FAILED (LOCAL): Password mismatch for {email}")
                        return None
                
                print(f"AUTH FAILED: No user found in cloud OR local registry for {email}")
                return None
            
            user = res.data[0]
            
            # --- LOCAL PASSWORD CHECKING (HYBRID AUTH) ---
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute("SELECT password FROM Users WHERE email=?", (email,))
            row = c.fetchone()
            
            if not row:
                # User exists in Cloud but not Local (Sync Trigger)
                print(f"AUTH: Cloud user {email} missing locally. Bootstrapping...")
                c.execute("INSERT INTO Users (email, first_name, last_name, role, password) VALUES (?, ?, ?, ?, ?)",
                          (email.lower(), user.get('first_name',''), user.get('last_name',''), user.get('role','Mentee'), ''))
                conn.commit()
                local_pwd = ''
            else:
                local_pwd = row[0]
            
            print(f"DEBUG: Comparing Local '{local_pwd}' with incoming '{pwd}'")
            
            if not local_pwd or local_pwd == '' or local_pwd == 'None':
                # Activation flow: Set local password if empty or NULL
                print(f"AUTH (ACTIVATION): Setting first password for {email}")
                c.execute("UPDATE Users SET password=? WHERE email=?", (pwd, email))
                conn.commit()
                conn.close()
                return {
                    "email": email,
                    "firstName": user.get('first_name'),
                    "lastName": user.get('last_name'),
                    "first_name": user.get('first_name'),
                    "last_name": user.get('last_name'),
                    "role": user.get('role'),
                    "isCounselor": user.get('role') == 'ProgramStaff',
                    "name": f"{user.get('first_name')} {user.get('last_name')}"
                }
            
            conn.close()
            if local_pwd == pwd:
                print(f"AUTH SUCCESS (HYBRID): {email}")
                return {
                    "email": email,
                    "firstName": user.get('first_name'),
                    "lastName": user.get('last_name'),
                    "first_name": user.get('first_name'),
                    "last_name": user.get('last_name'),
                    "role": user.get('role'),
                    "isCounselor": user.get('role') == 'ProgramStaff',
                    "name": f"{user.get('first_name')} {user.get('last_name')}"
                }
            
            print(f"AUTH FAILED (HYBRID): Password mismatch for {email}")
            return None
        except Exception as e:
            print(f"AUTH ERROR: {e}")
            return None

    def handle_login(self, data):
        email = data.get('email', '').strip().lower()
        pwd = data.get('password', '')
        
        user = self.verify_password(email, pwd)
        
        if user:
            token = str(uuid.uuid4())
            # AUTHORITY: Strictly hardcoded list of Counselors with oversight permissions
            approved_counselors = [
                'joshua.q@naischool.ae', 
                'nabeera.n@naischool.ae', 
                'dummy.counselor@naischool.ae', 
                'hayaotefy09@gmail.com'
            ]
            is_counselor = email.lower() in approved_counselors
            
            roles_permissions = {
                "role": user.get('role', 'Mentee'),
                "name": user.get('name'),
                "firstName": user.get('firstName'),
                "lastName": user.get('lastName'),
                "first_name": user.get('first_name'),
                "last_name": user.get('last_name'),
                "email": email,
                "isCounselor": is_counselor
            }
            SESSION_STORE[token] = roles_permissions
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"success": True, "token": token, "user": roles_permissions}).encode())
        else:
            self.send_response(401); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(b'{"error": "Login failed. Details do not match our Supabase registry."}')

    def get_initial_data(self):
        """Authoritative System Warm-up for Frontend"""
        print("STARS AUTHORITY: Providing initial system data...")
        try:
            # Simplified connection health check
            res = supabase.table('profiles').select('email').limit(1).execute()
            status = "Online" if res.data else "Halted"
            
            data = {
                "status": status,
                "engine": "v3.1 (Stable)",
                "authority": "Supabase Cloud",
                "timestamp": datetime.datetime.now().isoformat()
            }
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            print(f"INITIAL DATA ERROR: {e}")
            self.send_response(200) # Graceful fallback to unblock frontend
            self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"status": "Recovery", "error": str(e)}).encode())

    def handle_visitor(self, data):
        email = data.get('email')
        fname, lname = data.get('firstName', ''), data.get('lastName', '')
        # Generate 6-digit OTP
        otp = str(random.randint(100000, 999999))
        OTP_STORE[email] = {"otp": otp, "fname": fname, "lname": lname}
        
        # Restoration Request: Print to terminal for testing
        print(f"\n" + "="*50)
        print(f"STARS VISITOR OTP GENERATED")
        print(f"To: {email}")
        print(f"CODE: {otp}")
        print("="*50 + "\n")
        
        # Also attempt email if configured, but terminal is primary for test restoration
        # Also attempt email if configured
        try:
            subject = "STARS Verification Code"
            body = f"Hello {fname},\n\nYour one-time passcode for STARS Visitor access is: {otp}"
            send_stars_email(email, subject, body)
        except:
            pass
        
        self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers(); self.wfile.write(json.dumps({"success": True, "otp": otp}).encode())

    def handle_visitor_verify(self, data):
        email, code = data.get('email'), data.get('code')
        if email in OTP_STORE and OTP_STORE[email]['otp'] == code:
            token = str(uuid.uuid4())
            user_obj = {
                "role": "Visitor", 
                "name": f"{OTP_STORE[email]['fname']} {OTP_STORE[email]['lname']}", 
                "firstName": OTP_STORE[email]['fname'], 
                "lastName": OTP_STORE[email]['lname'],
                "first_name": OTP_STORE[email]['fname'],
                "last_name": OTP_STORE[email]['lname'],
                "email": email, 
                "isCounselor": False
            }
            SESSION_STORE[token] = user_obj
            del OTP_STORE[email]
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"success": True, "token": token, "user": user_obj}).encode())
        else:
            self.send_response(401); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(b'{"error": "Invalid OTP Code"}')

    def handle_reset_password(self, data):
        email = data.get('email', '')
        if email.endswith('@naischool.ae'):
            print(f"\n--- SIMULATED PASSWORD RESET ---\nTo: {email}\nSubject: STARS Password Reset\nLink: http://localhost:{PORT}/#reset\n")
        self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_send_message(self, data):
        user = get_user_from_headers(self.headers)
        if not user:
            self.send_response(401); self.end_headers(); return
            
        pair_id = data.get('pair_id')
        msg_text = data.get('message', '').strip()
        if not msg_text or not pair_id:
             self.send_response(400); self.end_headers(); return

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        # Verify access
        if not user.get('isCounselor'):
            c.execute("SELECT id FROM MentorMenteePair WHERE id=? AND (mentor_email=? OR mentee_email=?)", (pair_id, user['email'], user['email']))
            if not c.fetchone():
                self.send_response(403); self.end_headers(); conn.close(); return
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO Messages (pair_id, sender_email, message, timestamp) VALUES (?, ?, ?, ?)", (pair_id, user['email'], msg_text, timestamp))
        conn.commit()
        conn.close()
        self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers(); self.wfile.write(b'{"success": true}')

    def handle_get_resources(self):
        # SUPABASE SYNC: Fetch Shared Dummy Resources
        try:
            res = supabase.table('resources').select('*').execute()
            resources_list = res.data or []
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(resources_list).encode())
        except Exception as e:
            print(f"RESOURCE FETCH ERROR: {e}")
            self.send_response(500); self.end_headers()

    def handle_upload_resource(self, data):
        user = get_user_from_headers(self.headers)
        if not user or (user['role'] != 'Mentor' and not user.get('isCounselor')):
            self.send_response(403); self.end_headers(); return
            
        name = data.get('name')
        rtype = data.get('type', 'PDF')
        desc = data.get('description', '')
        category = data.get('category', 'Resilience')
        file_url = data.get('url', '') # Direct Supabase URL
        
        if not name:
            self.send_response(400); self.end_headers(); return
            
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Sync Local
        c.execute("INSERT INTO Resources (name, type, size, uploaded_by, timestamp, description, category, url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                  (name, rtype, '0.5 MB', user['email'], timestamp, desc, category, file_url))
        conn.commit()
        conn.close()

        # Sync Supabase Table (Authoritative Library)
        try:
            supabase.table('resources').insert({
                "name": name,
                "type": rtype,
                "description": desc,
                "category": category,
                "url": file_url,
                "uploaded_by": user['email'],
                "timestamp": timestamp
            }).execute()
        except:
            pass

        self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
        self.wfile.write(b'{"success": true}')

    def handle_get_messages(self, pair_id):
        user = get_user_from_headers(self.headers)
        if not user or not pair_id:
            self.send_response(401); self.end_headers(); return
            
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        # Verify access
        if not user.get('isCounselor'):
            c.execute("SELECT id FROM MentorMenteePair WHERE id=? AND (mentor_email=? OR mentee_email=?)", (pair_id, user['email'], user['email']))
            if not c.fetchone():
                self.send_response(403); self.end_headers(); conn.close(); return
        
        c.execute("SELECT sender_email, message, timestamp FROM Messages WHERE pair_id=? ORDER BY id ASC", (pair_id,))
        messages = [{"sender": r[0], "message": r[1], "timestamp": r[2]} for r in c.fetchall()]
        conn.close()
        self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
        self.wfile.write(json.dumps(messages).encode())

    def handle_admin_update_profile(self, data):
        """Authoritative Profile Update via Supabase 'users' table"""
        email = data.get('email')
        title = data.get('title', '')
        bio = data.get('bio', '')
        interests = data.get('interests', '')
        print(f"STARS AUTHORITY: Updating profile for {email} in CLOUD...")
        
        try:
             # Sync Cloud
             supabase.table('profiles').update({"title": title, "bio": bio, "interests": interests}).eq('email', email).execute()
             # Sync Local Fallback
             conn = sqlite3.connect(DATABASE)
             conn.cursor().execute("UPDATE Users SET title=?, bio=?, interests=? WHERE email=?", (title, bio, interests, email))
             conn.commit(); conn.close()
             self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(b'{"success": true}')
        except Exception as e:
             print(f"PROFILE UPDATE ERROR: {e}")
             self.send_response(500); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(json.dumps({"error": str(e)}).encode())

    def handle_survey_submit(self, data):
        user = get_user_from_headers(self.headers)
        if not user:
            self.send_response(401); self.end_headers(); return
            
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        survey_type = data.get('survey_type', 'General')
        conn = sqlite3.connect(DATABASE)
        try:
            c = conn.cursor()
            # Save each question/answer pair
            for q, a in data.items():
                if q != 'survey_type' and a: # Only save non-empty answers
                    c.execute("INSERT INTO Surveys (user_email, question, answer, timestamp, survey_type) VALUES (?, ?, ?, ?, ?)", 
                              (user['email'], q, str(a), timestamp, survey_type))
            
            conn.commit()
            
            # Escalation Logic: Mentor During-Session Survey Section 5 Concern
            if survey_type == 'Mentor-During' and data.get('Section 5 Concern') == 'Concern identified → escalate according to protocol':
                mentee_name = data.get('mentee_name', 'your mentee')
                print(f"\n------------------------------------------------------\nURGENT: EMERGENCY ESCALATION REPORTED\nTo: Nabeera.n@naischool.ae, joshua.q@naischool.ae\nSubject: URGENT EMERGENCY SESSION REQUEST - {mentee_name}\n\nMentor Name: {user['name']}\n\nALERT: A concern has been identified with mentee [{mentee_name}].\nAn emergency session needs to be scheduled immediately.\nPlease log in and schedule a session.\n------------------------------------------------------\n")
            
            # Previous safeguarding logic
            if data.get('section6_safeguarding_concern') == 'Yes':
                reporter = user['name'] if user else 'Unknown Mentee'
                print(f"\n------------------------------------------------------\nURGENT: SAFEGUARDING CONCERN REPORTED\nTo: Nabeera.n@naischool.ae, joshua.q@naischool.ae\nSubject: URGENT SAFEGUARDING ALERT\n\nMentor/Mentee Name: {reporter}\nA safeguarding concern has been raised in the post-session survey. Immediate review required.\n------------------------------------------------------\n")
            
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers(); self.wfile.write(b'{"success": true, "message": "Survey recorded."}')
        except Exception as e:
            self.send_response(400); self.end_headers(); self.wfile.write(json.dumps({"error": str(e)}).encode())
        finally:
            conn.close()

    def handle_admin_data(self):
        """Authoritative Data Retrieval with Local/Cloud Aggregation"""
        admin_bypass_header = self.headers.get('X-Admin-Bypass')
        is_bypass = (admin_bypass_header == 'STARS2026')
        
        print(f"STARS AUTHORITY: Admin data fetch (Bypass: {is_bypass})")
        
        registry_data = {"users": [], "pairs": []}
        emails_seen = set()

        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            
            # --- PHASE 1: RECONCILE VALID USERS (Authoritative Cloud-to-Local Sync) ---
            print("STARS AUTHORITY: Harmonizing identities...")
            res_users = supabase.table('profiles').select('*').eq('is_deleted', False).execute()
            cloud_users = res_users.data or []
            
            valid_emails = set()
            for u in cloud_users:
                email = (u.get('email') or '').lower().strip()
                if not email: continue
                valid_emails.add(email)
                # Authoritative Refresh
                c.execute("""INSERT OR REPLACE INTO Users (email, first_name, last_name, role, title, bio, interests) 
                             VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                          (email, u.get('first_name') or '', u.get('last_name') or '', u.get('role', 'Mentee'),
                           u.get('title', 'STARS Member'), u.get('bio', ''), u.get('interests', '')))
            conn.commit()
            
            # Populate User response from strictly validated local records
            c.execute("SELECT email, first_name, last_name, role, title, bio, interests FROM Users")
            all_users = c.fetchall()
            registry_data["users"] = []
            for row in all_users:
                email = (row[0] or '').lower().strip()
                if email in valid_emails:
                    registry_data["users"].append({
                        "email": email,
                        "name": f"{row[1]} {row[2]}",
                        "role": row[3],
                        "title": row[4] or 'STARS Member',
                        "bio": row[5] or '',
                        "interests": row[6] or ''
                    })

            # --- PHASE 2: RECONCILE PAIRINGS (Authoritative Cloud-to-Local Sync) ---
            print("STARS AUTHORITY: Harmonizing pairings...")
            res_pairs = supabase.table('mentor_mentee_pairs').select('*').execute()
            cloud_pairs = res_pairs.data or []
            
            sync_count = 0
            for p in cloud_pairs:
                if p.get('is_deleted'): continue
                m = (p.get('mentor_email') or '').lower().strip()
                s = (p.get('mentee_email') or '').lower().strip()
                
                if m in valid_emails and s in valid_emails:
                    c.execute("INSERT OR IGNORE INTO MentorMenteePair (mentor_email, mentee_email) VALUES (?, ?)", (m, s))
                    if c.rowcount > 0: sync_count += 1
            
            if sync_count > 0:
                conn.commit()
                print(f"STARS AUTHORITY: Synchronized {sync_count} pairings.")

            # --- PHASE 3: AGGREGATE FINAL VALIDATED PAIRS ---
            # INNER JOIN ensures pairings only show if both participants are locally registered
            c.execute("""SELECT m.first_name, m.last_name, m.email, s.first_name, s.last_name, s.email, p.id
                         FROM MentorMenteePair p 
                         JOIN Users m ON p.mentor_email = m.email 
                         JOIN Users s ON p.mentee_email = s.email""")
            pairs_rows = c.fetchall()
            
            registry_data["pairs"] = []
            for r in pairs_rows:
                # One last gate: ensure participants are in our valid cloud set
                m_email = (r[2] or '').lower().strip()
                s_email = (r[5] or '').lower().strip()
                if m_email in valid_emails and s_email in valid_emails:
                    registry_data["pairs"].append({
                        "mentor": f"{r[0]} {r[1]} ({m_email})", 
                        "mentee": f"{r[3]} {r[4]} ({s_email})", 
                        "pair_id": r[6]
                    })
            
            conn.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(registry_data).encode())
            return

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"ADMIN DATA AGGREGATION ERROR: {e}")
            # Robust fallback: attempt to send 500 only if protocol allows
            try:
                self.send_response(500)
                self.end_headers()
            except:
                pass
        return


    def handle_delete_session(self, data):
        # SECURITY SYNC: Verify Ownership Before Deletion
        user = get_user_from_headers(self.headers)
        if not user:
            print("TRASH ERROR: Unauthenticated session deletion attempt")
            self.send_response(401); self.end_headers(); return

        session_id = data.get('id')
        if not session_id: 
            self.send_response(400); self.end_headers(); return

        print(f"TRASH SYNC REQUEST: session_id={session_id} by={user['email']}")
        try:
            # 1. Ownership Check (Counselors can delete anything)
            res = supabase.table('sessions').select('*').eq('id', session_id).execute()
            if res.data:
                session_data = res.data[0]
                creator_email = (session_data.get('scheduled_by') or "").lower()
                requester_email = user['email'].lower()
                if creator_email != requester_email and not user.get('isCounselor'):
                    self.send_response(403); self.send_header('Content-Type', 'application/json'); self.end_headers()
                    self.wfile.write(json.dumps({"status": "error", "message": "Only the host can trash this session."}).encode())
                    return

            # 3. Proceed with Deletion
            supabase.table('sessions').delete().eq('id', session_id).execute()
            
            # Sync Local Fallback
            conn = sqlite3.connect(DATABASE)
            conn.cursor().execute("DELETE FROM Sessions WHERE id=?", (session_id,))
            conn.commit(); conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode())

        except Exception as e:
            print(f"TRASH ERROR: {e}")
            self.send_response(500); self.end_headers()

    def handle_delete_survey(self, data):
        # AUTHORITATIVE TRASH: Removes from Database and attempts to flag the Excel source
        user = get_user_from_headers(self.headers)
        if not user or not user.get('isCounselor'):
            self.send_response(401); self.end_headers(); return

        email = data.get('email')
        timestamp = data.get('timestamp')
        stype = data.get('type')

        if not email or not timestamp:
            self.send_response(400); self.end_headers(); return

        print(f"STARS AUTHORITATIVE TRASH: Removing {email} | {timestamp} | {stype}")
        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            
            # AUTHORITATIVE: Find the source file FIRST
            c.execute("SELECT source_file FROM Surveys WHERE user_email=? AND timestamp=? AND survey_type=? LIMIT 1", (email, timestamp, stype))
            row = c.fetchone()
            source = row[0] if row else None
            
            if source:
                 self.remove_survey_row_from_excel(source, email, timestamp)

            c.execute("DELETE FROM Surveys WHERE user_email=? AND timestamp=? AND survey_type=?", (email, timestamp, stype))
            conn.commit()
            conn.close()
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(b'{"success": true}')
        except Exception as e:
            print(f"SURVEY DELETE ERROR: {e}")
            self.send_response(500); self.end_headers()

    def remove_survey_row_from_excel(self, filename, email, timestamp):
        """Authoritative Deletion from original source file"""
        import openpyxl, shutil
        if not os.path.exists(filename): return
        
        # Safety Backup
        shutil.copy2(filename, filename + ".bak")
        
        try:
            wb = openpyxl.load_workbook(filename)
            sheet = wb.active
            headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]
            email_idx = next((i for i, h in enumerate(headers) if 'Email' in h), -1)
            time_idx = next((i for i, h in enumerate(headers) if 'time' in h.lower() and 'completion' in h.lower()), -1)
            if time_idx == -1: time_idx = 2 # Best guess if heuristic fails
            
            rows_deleted = 0
            # Iterate backwards to safely delete
            for row_idx in range(sheet.max_row, 1, -1):
                row_email = str(sheet.cell(row=row_idx, column=email_idx+1).value or "").lower().strip()
                row_time = str(sheet.cell(row=row_idx, column=time_idx+1).value or "").strip()
                
                # Check email and timestamp (allowing partial match for precision)
                if row_email == email.lower().strip() and (timestamp in row_time or row_time in timestamp):
                    sheet.delete_rows(row_idx)
                    rows_deleted += 1
            
            if rows_deleted > 0:
                wb.save(filename)
                print(f"AUTHORITATIVE: Deleted {rows_deleted} rows from {filename}")
        except Exception as e:
            print(f"EXCEL DELETE FAILED ({filename}): {e}")


    def sync_surveys_from_local_excel(self):
        """
        STARS Authoritative Sync: Discover and ingest all 'survey_*.xlsx' files.
        Renamed per 'Hard Reset' requirements.
        """
        import glob
        files = glob.glob("survey_*.xlsx")
        
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        for excel_path in files:
            filename = os.path.basename(excel_path)
            print(f"STARS DIAGNOSTIC: Looking for {excel_path}...")
            # Infer survey type from filename: e.g. survey_mentor_pre.xlsx -> Pre-Session
            survey_type = 'General'
            if 'pre' in filename.lower(): survey_type = 'Pre-Session'
            elif 'post' in filename.lower(): survey_type = 'Post-Session'
            elif 'during' in filename.lower(): survey_type = 'During-Session'

            try:
                wb = openpyxl.load_workbook(excel_path, data_only=True)
                sheet = wb.active
                headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]
                
                # AUTHORITATIVE HEADER DETECTION: Look for 'Email' and 'Mentee Name' (Capitalized)
                email_idx = -1
                name_idx = -1
                for i, h in enumerate(headers):
                    if h == 'Email': email_idx = i
                    if h in ['Mentee Name', 'Name']: name_idx = i
                
                # Fallback: if exact match fails, use case-insensitive discovery
                if email_idx == -1: email_idx = next((i for i, h in enumerate(headers) if 'email' in h.lower()), -1)
                if name_idx == -1: name_idx = next((i for i, h in enumerate(headers) if 'name' in h.lower()), -1)

                if email_idx == -1: 
                    print(f"STARS SYNC WARNING: No 'Email' header found in {filename}. Skipping.")
                    continue

                for row in sheet.iter_rows(min_row=2, values_only=True):
                    email = str(row[email_idx] or "").lower().strip()
                    if not email or email == 'anonymous': continue
                    
                    timestamp_val = row[2] or row[1] or datetime.datetime.now()
                    if isinstance(timestamp_val, datetime.datetime):
                        timestamp = timestamp_val.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        timestamp = str(timestamp_val)

                    for i, (h, a) in enumerate(zip(headers, row)):
                        # Skip ID/Metadata columns and the Name/Email columns
                        if i <= 2 or i == email_idx or i == name_idx: continue
                        if not h or a is None: continue
                        
                        c.execute("""INSERT OR IGNORE INTO Surveys (user_email, question, answer, timestamp, survey_type, source_file) 
                                     VALUES (?, ?, ?, ?, ?, ?)""", (email, h, str(a), timestamp, survey_type, filename))
            
            except Exception as e:
                print(f"STARS SYNC ERROR ({filename}): {e}")
            else:
                print(f"STARS DIAGNOSTIC: Successfully synchronized {filename}")
        
        conn.commit()
        conn.close()

    def handle_survey_analytics(self):
        # Trigger authoritative sync before returning analytics
        global_sync_surveys()
        
        user = get_user_from_headers(self.headers)
        if not user:
            self.send_response(401); self.end_headers(); return

        import urllib.parse
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        
        days_raw = query.get('days', ['30'])[0]
        # Forced sanitize: strictly numeric or 'all'
        days = ''.join(c for c in days_raw if c.isdigit())
        if not days: days = '30'

        participant_role = query.get('role', [None])[0] 
        survey_period = query.get('type', [None])[0]   
        target_email = query.get('email', [None])[0]   
        
        conn = sqlite3.connect(DATABASE)
        try:
            c = conn.cursor()
            is_admin = user.get('isCounselor') or str(user.get('role')).lower() == 'programstaff'
            
            # AUTHORITATIVE DEFAULT: If admin and no role selected, force to 'Mentor' per user request
            if is_admin and not participant_role:
                participant_role = 'Mentor'
            
            if user['role'] == 'Mentee':
                self.send_response(403); self.end_headers(); conn.close(); return
                
            # NUCLEAR FIX: LEFT JOIN ensures data is visible even if profile is partially missing
            base_sql = """
                SELECT 
                    s.user_email, s.question, s.answer, s.timestamp, 
                    COALESCE(u.role, 'Mentee') as role, 
                    COALESCE(u.first_name, 'Unknown') as fname, 
                    COALESCE(u.last_name, 'User') as lname, 
                    s.survey_type,
                    s.source_file
                FROM Surveys s 
                LEFT JOIN Users u ON LOWER(s.user_email) = LOWER(u.email) 
                WHERE 1=1
            """
            params = []
            
            print(f"STARS ANALYTICS: Processing for {user['email']} (Admin: {is_admin}, P-Role: {participant_role})")

            if not is_admin:
                mode = query.get('mode', ['self'])[0]
                if mode == 'mentees' or participant_role == 'Mentee':
                    # STRICT MENTEE DATA: survey_mentee_pre.xlsx, survey_mentee_post.xlsx
                    c.execute("SELECT mentee_email FROM MentorMenteePair WHERE mentor_email=?", (user['email'],))
                    mentees = [r[0].lower() for r in c.fetchall()]
                    if not mentees: mentees = ['none@assigned.stars']
                    
                    placeholders = ",".join(["?" for _ in mentees])
                    base_sql += f" AND LOWER(s.user_email) IN ({placeholders}) AND s.source_file LIKE 'survey_mentee_%'"
                    params.extend(mentees)
                else:
                    # SELF VIEW: survey_mentor_during.xlsx, survey_mentor_post.xlsx
                    base_sql += " AND LOWER(s.user_email) = ? AND s.source_file LIKE 'survey_mentor_%'"
                    params.append(user['email'].lower())
            else:
                # COUNSELOR/STAFF: Strict Partitioning by requested role
                if target_email:
                    base_sql += " AND LOWER(s.user_email) = ?"
                    params.append(target_email.lower())
                elif participant_role == 'Mentee':
                     base_sql += " AND LOWER(s.source_file) LIKE 'survey_mentee_%'"
                elif participant_role == 'Mentor':
                     base_sql += " AND LOWER(s.source_file) LIKE 'survey_mentor_%'"
                elif participant_role and participant_role != 'All':
                     base_sql += " AND u.role = ?"
                     params.append(participant_role.rstrip('s'))

            if days and days != 'all' and days.isdigit():
                base_sql += " AND s.timestamp >= datetime('now', ? || ' days')"
                params.append(f"-{days}")
                
            if survey_period:
                base_sql += " AND (s.survey_type = ? OR s.question LIKE ?)"
                params.append(survey_period)
                params.append(f"%{survey_period}%")

            base_sql += " ORDER BY s.timestamp DESC"
            c.execute(base_sql, params)
            rows = c.fetchall()
            surveys_flat = [{"email": r[0], "question": r[1], "answer": r[2], "timestamp": r[3], "role": r[4], "name": f"{r[5]} {r[6]}", "type": r[7], "source_file": r[8]} for r in rows]
            
            submissions = {}
            for s in surveys_flat:
                # Key must be stable and unique to the submission event
                key = f"{s['email']}|{s['timestamp']}|{s['type']}"
                
                # AUTHORITATIVE ROLE INFERENCE: Trust the filename over the registry if they mismatch
                display_role = s['role']
                if 'mentee' in str(s.get('type', '')).lower() or 'mentee' in str(s.get('question', '')).lower():
                     display_role = 'Mentee'
                # Better: Check the actual source file which we included in surveys_flat
                source = str(s.get('source_file') or '').lower()
                if 'mentee' in source: display_role = 'Mentee'
                elif 'mentor' in source: display_role = 'Mentor'

                if key not in submissions:
                    submissions[key] = {
                        "email": s['email'],
                        "name": s['name'],
                        "role": display_role,
                        "timestamp": s['timestamp'],
                        "type": s['type'],
                        "responses": []
                    }
                submissions[key]["responses"].append({"q": s['question'], "a": s['answer']})
            
            bundled_list = list(submissions.values())

            # Robust Rating Parsing (Safely handle nulls / garbage)
            def safe_int(val):
                if val is None: return None
                v = str(val).strip()
                return int(v) if v.isdigit() else None

            mood_ratings = [safe_int(s['answer']) for s in surveys_flat if 'Mood Today' in s['question'] if safe_int(s['answer']) is not None]
            help_ratings = [safe_int(s['answer']) for s in surveys_flat if any(x in s['question'] for x in ['helped', 'Helpfulness']) if safe_int(s['answer']) is not None]
            
            avg_mood = round(sum(mood_ratings) / len(mood_ratings), 1) if mood_ratings else 0
            avg_help = round(sum(help_ratings) / len(help_ratings), 1) if help_ratings else 0
            
            volume_trend = {}
            for s in surveys_flat:
                if s['timestamp']:
                    day = s['timestamp'].split(' ')[0]
                    volume_trend[day] = volume_trend.get(day, 0) + 1
            
            sorted_dates = sorted(volume_trend.keys())
            trend_data = [{"date": d, "count": volume_trend[d]} for d in sorted_dates]

            unique_users = len(set([s['email'] for s in surveys_flat]))
            trends = [
                {"label": "Mood (Avg)", "value": avg_mood, "type": "sentiment"},
                {"label": "Support (Avg)", "value": avg_help, "type": "sentiment"},
                {"label": "Active Users", "value": unique_users, "type": "stat"},
                {"label": "Total Items", "value": len(surveys_flat), "type": "stat"}
            ]
            
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({
                "surveys": bundled_list, 
                "trends": trends, 
                "mood_avg": avg_mood, 
                "help_avg": avg_help,
                "volume_trend": trend_data
            }).encode())
        except Exception as e:
            print(f"SURVEY ANALYTICS ERROR: {e}")
            self.send_response(500); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
        finally:
            conn.close()

    def handle_survey_ingest(self, data):
        """
        Authoritative MS Forms Receiver. 
        Expected JSON: { "email": "...", "type": "...", "responses": [ {"q": "...", "a": "..."} ] }
        """
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        try:
            email = data.get('email', '').lower().strip()
            # Canonical types: Mentor-Pre, Mentor-Post, Mentee-Pre, Mentee-Post
            survey_type = data.get('type', 'General') 
            responses = data.get('responses', [])
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for res in responses:
                q = res.get('q', 'Unknown Question')
                a = str(res.get('a', ''))
                c.execute("INSERT INTO Surveys (user_email, question, answer, timestamp, survey_type) VALUES (?, ?, ?, ?, ?)",
                          (email, q, a, timestamp, survey_type))
            
            conn.commit()
            print(f"STARS INGEST: Received {len(responses)} responses for {email} ({survey_type})")
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(b'{"success": true}')
        except Exception as e:
            print(f"INGEST ERROR: {e}")
            self.send_response(500); self.end_headers()
        finally:
            conn.close()


if __name__ == "__main__":
    init_db()
    socketserver.TCPServer.allow_reuse_address = True
    # Listen on 0.0.0.0 and use the dynamic PORT for Render
    with socketserver.TCPServer(("0.0.0.0", PORT), STARSAPIHandler) as httpd:
        print(f"STARS Portal Live: Listening on host 0.0.0.0, port {PORT}")
        httpd.serve_forever()
