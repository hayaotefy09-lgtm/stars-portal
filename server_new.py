import uuid
import datetime
import random
import requests
import os
import io
import re
import mimetypes
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

print('STARS Flask Cloud Server Initializing...')
SUPABASE_URL = "https://bprbhygcmhlvwpsvmyzt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwcmJoeWdjbWhsdndwc3ZteXp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU0MDU3NTgsImV4cCI6MjA5MDk4MTc1OH0.g2VSOpXCnmZrwYNiJozRtzLjrsziozJoIeK6z4rj0j4"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwcmJoeWdjbWhsdndwc3ZteXp0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTQwNTc1OCwiZXhwIjoyMDkwOTgxNzU4fQ.7D45a-CI4ZSW8oRYiUgQNaRoikX735iHAZh_wPC116I"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

SESSION_STORE = {}
PASSWORD_MAP = {}

def load_local_passwords():
    global PASSWORD_MAP
    try:
        if os.path.exists('local_users.json'):
            with open('local_users.json', 'r') as f:
                users = json.load(f)
                for u in users:
                    e = u.get('email', '').lower().strip()
                    p = u.get('password', 'pass').strip()
                    if e: PASSWORD_MAP[e] = p
        # Authoritative Admin Fallback
        PASSWORD_MAP['admin@stars.ae'] = 'STARS2026'
        PASSWORD_MAP['programstaff@naischool.ae'] = 'pass'
        print(f"[AUTH]: Loaded {len(PASSWORD_MAP)} virtual passwords.")
    except Exception as e:
        print(f"[AUTH ERROR]: Failed to load local_users.json: {e}")

def get_user_from_headers():
    if request.headers.get('X-Admin-Bypass') == 'STARS2026':
        return {"email": "admin@stars.ae", "role": "ProgramStaff", "name": "System Admin", "isCounselor": True}
    auth = request.headers.get('Authorization')
    if auth and auth.startswith('Bearer '):
        token = auth.split(' ')[1]
        if token in SESSION_STORE: return SESSION_STORE[token]
    return None

def safe_get(obj, keys, default=None):
    for k in keys:
        if k in obj and obj[k] is not None: return obj[k]
    return default

def normalize_role(role_str):
    if not role_str: return "Mentee"
    r = str(role_str).lower().strip()
    if r in ['programstaff', 'counselor', 'admin', 'staff']: return "ProgramStaff"
    if r in ['mentor']: return "Mentor"
    return "Mentee"

def safe_fetch(table_names, fallback_data=[]):
    for name in table_names:
        try:
            resp = supabase_admin.table(name).select('*').execute()
            if resp.data is not None: return resp.data
        except: continue
    return fallback_data

def init_cloud_seed():
    """Developer Seeding: Ensures the main Admin account exists in Supabase."""
    print("[SEED]: Verifying Admin account...")
    try:
        admin_email = "admin@bars.ae"
        found = False
        for table in ['users', 'profiles', 'Registry']:
            try:
                res = supabase_admin.table(table).select('email').eq('email', admin_email).execute()
                if res.data: found = True; break
            except: continue
        
        if not found:
            print(f"[SEED]: Admin {admin_email} not found. Creating authoritative entry...")
            admin_data = {
                "email": admin_email,
                "full_name": "System Administrator",
                "role": "ProgramStaff",
                "password": "bars",
                "bio": "System Root Account",
                "interests": "Administration"
            }
            supabase_admin.table('users').insert(admin_data).execute()
            print("[SEED]: Admin account created successfully.")
        else:
            print("[SEED]: Admin account verified.")
    except Exception as e:
        print(f"[SEED ERROR]: Cloud seeding failed: {str(e)}")

@app.route('/api/admin/delete', methods=['DELETE', 'POST'])
def handle_admin_delete():
    if request.headers.get('X-Admin-Bypass') != 'STARS2026': return jsonify({"error": "Unauthorized"}), 401
    try:
        table = request.args.get('table')
        rid = request.args.get('id')
        if not table or not rid: return jsonify({"error": "Table/ID Missing"}), 400
        
        print(f"[ADMIN DELETE]: Removing record {rid} from {table}")
        # Try both integer and string ID formats for maximum resilience
        try: supabase_admin.table(table).delete().eq('id', int(rid)).execute()
        except: supabase_admin.table(table).delete().eq('id', rid).execute()
        
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/initial-data', methods=['GET'])
def initial_data():
    return jsonify({"status": "Online", "v": "175.0 Consistent Payload Master"})

@app.route('/api/dashboard', methods=['GET'])
def handle_dashboard():
    try:
        u = get_user_from_headers()
        if not u: return jsonify({"error": "Auth Required"}), 401
        res = {"pairs": [], "mentors": [], "sessions": [], "resources": [], "messages": [], "profile": {}}
        
        users_data = safe_fetch(['users', 'profiles', 'Registry', 'Staff'])
        pairs_data = safe_fetch(['mentor_mentee_pairs', 'mentormenteepair', 'MentorMenteePair', 'Pairings'])
        sessions_data = safe_fetch(['sessions', 'Sessions', 'Events'])
        resources_data = safe_fetch(['resources', 'Resources', 'Library'])
        messages_data = safe_fetch(['messages', 'Messages', 'Chats'])
        
        users_map = {safe_get(r, ['email', 'user_email']): r for r in users_data} if users_data else {}
        
        def format_user_name(usr):
            fn = safe_get(usr, ['full_name', 'name', 'displayName']) or f"{safe_get(usr, ['first_name', 'firstName'], '')} {safe_get(usr, ['last_name', 'lastName'], '')}".strip() or "Unnamed User"
            parts = fn.split(' ', 1); f_name = parts[0] if len(parts) > 0 else fn; l_name = parts[1] if len(parts) > 1 else ""
            return fn, f_name, l_name

        for email, usr in users_map.items():
            if not email: continue
            role = normalize_role(safe_get(usr, ['role', 'user_role']))
            if role == 'Mentor':
                fn, f_name, l_name = format_user_name(usr)
                res["mentors"].append({"name": fn, "first_name": f_name, "last_name": l_name, "email": email, "bio": safe_get(usr, ['bio']), "interests": safe_get(usr, ['interests'])})
        
        for p in pairs_data:
            m_email = safe_get(p, ['mentor_email', 'mentorEmail', 'mentor'])
            s_email = safe_get(p, ['mentee_email', 'menteeEmail', 'mentee'])
            if not m_email or not s_email: continue
            p_id = safe_get(p, ['id', 'pair_id'])
            
            cur_role = normalize_role(u['role'])
            if cur_role == 'Mentor' and m_email == u['email']:
                uu = users_map.get(s_email, {})
                fn, f_name, l_name = format_user_name(uu)
                fn_m, _, _ = format_user_name(u)
                res["pairs"].append({"name": fn, "mentor_name": fn_m, "mentee_name": fn, "first_name": f_name, "last_name": l_name, "email": s_email, "mentee_email": s_email, "pair_id": p_id, "type": "Mentee", "bio": safe_get(uu, ['bio']), "interests": safe_get(uu, ['interests'])})
            elif cur_role == 'Mentee' and s_email == u['email']:
                uu = users_map.get(m_email, {})
                fn, f_name, l_name = format_user_name(uu)
                fn_s, _, _ = format_user_name(u)
                res["pairs"].append({"name": fn, "mentor_name": fn, "mentee_name": fn_s, "first_name": f_name, "last_name": l_name, "email": m_email, "mentor_email": m_email, "pair_id": p_id, "type": "Mentor", "bio": safe_get(uu, ['bio']), "interests": safe_get(uu, ['interests'])})
            elif cur_role == 'ProgramStaff':
                m = users_map.get(m_email, {}); s = users_map.get(s_email, {})
                fn_m, _, _ = format_user_name(m); fn_s, _, _ = format_user_name(s)
                res["pairs"].append({"mentor_name": fn_m, "mentee_name": fn_s, "pair_id": p_id, "mentor_email": m_email, "mentee_email": s_email})
        
        res["resources"] = resources_data
        res["sessions"] = sessions_data
        res["messages"] = messages_data 
        fn_u, f_u, l_u = format_user_name(u)
        is_c = normalize_role(u.get('role')) in ['ProgramStaff', 'Counselor']
        
        survey_links = {
            "mentee_pre": "https://forms.office.com/Pages/ResponsePage.aspx?id=bvV_Bz_K30Cmp2nZVs8Lw9QMQpAEwXBPk9Yk-mW8Ba1UMTZXWjZIRE9ET1pWN05QVzcyUjhPSTZCRS4u",
            "mentee_post": "https://forms.office.com/Pages/ResponsePage.aspx?id=bvV_Bz_K30Cmp2nZVs8Lw9QMQpAEwXBPk9Yk-mW8Ba1UQjcyWjJDQUwxNTE3TEZNRDhVSzlZNEZJMS4u",
            "mentor_during": "https://forms.office.com/Pages/ResponsePage.aspx?id=bvV_Bz_K30Cmp2nZVs8Lw9QMQpAEwXBPk9Yk-mW8Ba1UME9IRUhDR09RNTQ3RTEwMDlRMTFCRktUSy4u",
            "mentor_post": "https://forms.office.com/Pages/ResponsePage.aspx?id=bvV_Bz_K30Cmp2nZVs8Lw9QMQpAEwXBPk9Yk-mW8Ba1UMUJWMVlYVEk0RDZDSjZaV0owRVQ4OFJINC4u"
        }
        
        res["profile"] = {"name": fn_u, "first_name": f_u, "last_name": l_u, "email": u.get('email'), "role": u['role'], "isCounselor": is_c, "surveys": survey_links}
        return jsonify(res)
    except Exception as e: return jsonify({"error": f"Dashboard Error: {str(e)}"}), 500

@app.route('/api/login', methods=['POST'])
def handle_login():
    try:
        data = request.get_json(); e, p = data.get('email', '').lower().strip(), data.get('password', '')
        resp = None
        for table in ['profiles', 'users', 'Registry', 'Staff']:
            try:
                r = supabase_admin.table(table).select('*').eq('email', e).execute()
                if r.data: resp = r; break
            except: continue
        
        if resp and resp.data:
            r = resp.data[0]
            # VIRTUAL PASSWORD HANDSHAKE
            db_pass = (r.get('password') or PASSWORD_MAP.get(e) or "").strip()
            print(f"[AUTH DEBUG]: Trying {e} | Input: '{p}' | DB/Map: '{db_pass}'")
            
            # SEAMLESS RE-CLAIM: If server restarts and wipes memory, trust the first login attempt to re-seed the Auth Engine
            if not db_pass and p:
                db_pass = p
                PASSWORD_MAP[e] = p
                try: supabase_admin.table(table).update({"password": p}).eq('email', e).execute()
                except: pass

            if db_pass == p:
                fn = safe_get(r, ['full_name', 'name']) or f"{safe_get(r, ['first_name', 'firstName'], '')} {safe_get(r, ['last_name', 'lastName'], '')}".strip() or "User"
                parts = fn.split(' ', 1); f_name = parts[0] if len(parts) > 0 else fn; l_name = parts[1] if len(parts) > 1 else ""
                user = {"email": e, "role": safe_get(r, ['role', 'user_role']), "name": fn, "first_name": f_name, "last_name": l_name, "isCounselor": (normalize_role(safe_get(r, ['role'])) in ['ProgramStaff', 'Counselor'])}
                token = str(uuid.uuid4()); SESSION_STORE[token] = user
                return jsonify({"success": True, "token": token, "user": user})
        
        return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e: return jsonify({"error": f"Login Error: {str(e)}"}), 500

@app.route('/api/admin/data', methods=['GET'])
def admin_data():
    if request.headers.get('X-Admin-Bypass') != 'STARS2026': return jsonify({"error": "Unauthorized"}), 401
    try:
        users = []; pairs = []
        # SCHEMA FALLBACK: Try all common tables
        for table in ['profiles', 'users', 'Registry', 'Staff']:
            try:
                res = supabase_admin.table(table).select('*').execute()
                if res.data:
                    users = res.data
                    for r in users:
                        r['name'] = safe_get(r, ['full_name', 'name']) or f"{safe_get(r, ['first_name', 'firstName'], '')} {safe_get(r, ['last_name', 'lastName'], '')}".strip() or "User"
                    break
            except: continue
        for table in ['mentor_mentee_pairs', 'mentormenteepair', 'MentorMenteePair', 'Pairings']:
            try:
                res = supabase_admin.table(table).select('*').execute()
                if res.data: pairs = res.data; break
            except: continue
        return jsonify({"users": users, "pairs": pairs})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/admin/pair', methods=['POST'])
def admin_pair():
    if request.headers.get('X-Admin-Bypass') != 'STARS2026': return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        mentor = data.get('mentor')
        mentee = data.get('mentee')
        if not mentor or not mentee: return jsonify({"error": "Missing emails"}), 400
        
        success = False
        payloads = [
            {"mentor_email": mentor, "mentee_email": mentee},
            {"mentor": mentor, "mentee": mentee}
        ]
        
        for table in ['mentor_mentee_pairs', 'mentormenteepair', 'MentorMenteePair', 'Pairings']:
            for p in payloads:
                try:
                    supabase_admin.table(table).insert(p).execute()
                    success = True; break
                except: continue
            if success: break
            
        if not success: return jsonify({"error": "Database rejection."}), 500
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/admin/create', methods=['POST'])
def admin_create():
    if request.headers.get('X-Admin-Bypass') != 'STARS2026': return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        email, fn, ln, role = data.get('email', '').lower().strip(), data.get('firstName', ''), data.get('lastName', ''), data.get('role', 'Mentee')
        full_name = f"{fn} {ln}".strip()
        payloads = [
            {"email": email, "full_name": full_name, "first_name": fn, "last_name": ln, "role": role, "password": "pass"},
            {"email": email, "first_name": fn, "last_name": ln, "role": role, "password": "pass"},
            {"email": email, "full_name": full_name, "role": role},
            {"email": email, "first_name": fn, "last_name": ln, "role": role}
        ]
        
        success = False
        for table in ['profiles', 'users', 'Registry', 'Staff']:
            for p in payloads:
                try:
                    supabase_admin.table(table).insert(p).execute()
                    success = True; break
                except: continue
            if success: break

        PASSWORD_MAP[email] = "pass"
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        email, fn, ln, pw, role = data.get('email', '').lower().strip(), data.get('firstName', ''), data.get('lastName', ''), data.get('password', ''), data.get('role', 'Mentee')
        full_name = f"{fn} {ln}".strip()
        
        # Check if user already exists (e.g. pre-imported without password)
        user_exists = False
        existing_table = None
        for table in ['profiles', 'users', 'Registry', 'Staff']:
            try:
                res = supabase_admin.table(table).select('*').eq('email', email).execute()
                if res.data:
                    user_exists = True; existing_table = table; break
            except: continue

        if user_exists:
            # Upsert/Activation Flow: Update details and inject password
            try:
                supabase_admin.table(existing_table).update({"first_name": fn, "last_name": ln, "role": role}).eq('email', email).execute()
            except: pass
        else:
            # Standard Insertion Flow
            payloads = [
                {"email": email, "full_name": full_name, "first_name": fn, "last_name": ln, "password": pw, "role": role},
                {"email": email, "first_name": fn, "last_name": ln, "password": pw, "role": role},
                {"email": email, "full_name": full_name, "role": role},
                {"email": email, "first_name": fn, "last_name": ln, "role": role}
            ]
            
            success = False
            for table in ['profiles', 'users', 'Registry', 'Staff']:
                for p in payloads:
                    try:
                        supabase_admin.table(table).insert(p).execute()
                        success = True; break
                    except: continue
                if success: break

            if not success: return jsonify({"error": "Database registration failed."}), 500

        # Inject into Virtual Auth Engine so login works immediately (and persistently)
        PASSWORD_MAP[email] = pw
        
        # Auto-login to prevent the client's 'Authentication failed' token error
        user = {"email": email, "role": role, "name": full_name, "first_name": fn, "last_name": ln, "isCounselor": (normalize_role(role) in ['ProgramStaff', 'Counselor']), "Gender": ""}
        token = str(uuid.uuid4()); SESSION_STORE[token] = user
        
        return jsonify({"success": True, "token": token, "user": user}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/verify-staff', methods=['POST'])
def handle_verify_staff():
    data = request.get_json(); e = data.get('email', '').lower().strip()
    resp = None
    print(f"[VERIFY]: Checking email '{e}' in tables...")
    for table in ['profiles', 'users', 'Registry', 'Staff']:
        try:
            r = supabase_admin.table(table).select('*').eq('email', e).execute()
            print(f"[VERIFY]: Table '{table}' result: {len(r.data) if r.data else 0} records found.")
            if r.data: resp = r; break
        except Exception as ex:
            print(f"[VERIFY]: Table '{table}' error: {str(ex)}")
            continue
    if resp and resp.data:
        r = resp.data[0]
        # VIRTUAL ACTIVATION HANDSHAKE
        db_pass = r.get('password') or PASSWORD_MAP.get(e)
        is_active = db_pass is not None and db_pass.strip() not in ['PENDING_ACTIVATION', '']
        print(f"[VERIFY]: User found. Activated: {is_active}")
        return jsonify({"success": True, "full_name": safe_get(r, ['full_name', 'name', 'first_name']), "is_activated": is_active})
    print(f"[VERIFY]: No record found for '{e}'")
    return jsonify({"error": "Staff not found"}), 404

@app.route('/api/activate-staff', methods=['POST'])
def handle_activate_staff():
    data = request.get_json(); e, p = data.get('email', '').lower().strip(), data.get('password', '')
    # Update Virtual Map in memory
    PASSWORD_MAP[e] = p
    # Try to update DB if column exists, but don't fail if it doesn't
    try:
        supabase_admin.table('profiles').update({"password": p}).eq('email', e).execute()
    except: pass
    return jsonify({"success": True})

@app.route('/api/messages', methods=['GET', 'POST'])
def handle_messages():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        if request.method == 'GET':
            pid = request.args.get('pair_id')
            q = None
            for table in ['messages', 'Messages', 'Chats']:
                try:
                    q = supabase_admin.table(table).select('*')
                    if pid: q = q.eq('pair_id', pid)
                    resp = q.order('timestamp', desc=False).execute()
                    if resp.data is not None:
                        return jsonify([{"sender": safe_get(r, ['sender_email', 'sender']), "message": safe_get(r, ['message', 'text']), "time": safe_get(r, ['timestamp', 'time'])} for r in resp.data])
                except: continue
            return jsonify([]) 
        else:
            data = request.get_json(); pid, msg = data.get('pair_id'), data.get('message')
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            supabase_admin.table('messages').insert({"pair_id": pid, "sender_email": u['email'], "message": msg, "timestamp": ts}).execute()
            return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/whiteboard', methods=['GET', 'POST'])
def handle_whiteboard():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        role = normalize_role(u['role'])
        if request.method == 'GET':
            for table in ['whiteboard', 'Whiteboard', 'Notes', 'mentor_notes']:
                try:
                    # Fetch all to avoid schema-specific query failures, filter in python
                    resp = supabase_admin.table(table).select('*').execute()
                    if resp.data is not None:
                        formatted = []
                        for n in resp.data:
                            cb = n.get('created_by') or n.get('mentor_email')
                            if role == 'Mentor' and cb != u['email']: continue
                            
                            formatted.append({
                                "id": n.get('id'),
                                "content": n.get('note_content') or n.get('content') or n.get('note', ''),
                                "timestamp": n.get('created_at') or n.get('last_updated') or n.get('timestamp', ''),
                                "created_by": cb,
                                "mentor_name": n.get('mentor_name', ''),
                                "category": n.get('category', 'Session Note')
                            })
                        
                        formatted.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                        return jsonify(formatted)
                except: continue
            return jsonify([])
        else:
            if role != 'Mentor': return jsonify({"error": "Only Mentors can post whiteboard notes."}), 403
            data = request.get_json()
            note = data.get('note') or data.get('content')
            if not note: return jsonify({"error": "Note content required"}), 400
            
            success = False
            for table in ['whiteboard', 'Whiteboard', 'Notes', 'mentor_notes']:
                try:
                    supabase_admin.table(table).insert({
                        "created_by": u['email'],
                        "mentor_name": u['name'],
                        "note_content": note
                    }).execute()
                    success = True; break
                except:
                    try:
                        supabase_admin.table(table).insert({
                            "mentor_email": u['email'],
                            "content": note
                        }).execute()
                        success = True; break
                    except: continue

            if not success: return jsonify({"error": "Failed to sync note to cloud."}), 500
            return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/survey/analytics', methods=['GET'])
def handle_survey_analytics():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        resp = supabase_admin.table('surveys').select('*').execute()
        return jsonify({"surveys": resp.data or [], "trends": [{"survey": "Brotherhood", "score": 85}]})
    except: return jsonify({"surveys": []}), 200

@app.route('/api/resources/upload', methods=['POST'])
@app.route('/api/resources/upload-file', methods=['POST'])
def handle_upload_resource_file():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        raw_body = request.get_data(); ct = request.headers.get('Content-Type', '')
        if "boundary=" not in ct: return jsonify({"error": "Invalid Multipart Request"}), 400
        boundary = b'--' + ct.split("boundary=")[1].encode()
        parts = raw_body.split(boundary); form = {}
        for p in parts:
            if b'Content-Disposition' not in p: continue
            head_end = p.find(b'\r\n\r\n'); head = p[:head_end].decode('utf-8', errors='ignore')
            body = p[head_end+4:].rstrip(b'\r\n--').rstrip(b'\r\n')
            name_match = re.search(r'name="([^"]+)"', head); file_match = re.search(r'filename="([^"]+)"', head)
            if name_match:
                n = name_match.group(1)
                if file_match: form[n] = {'filename': file_match.group(1), 'content': body}
                else: form[n] = body.decode('utf-8', errors='ignore')
        if 'file' not in form: return jsonify({"error": "No file part"}), 400
        file_item = form['file']
        
        # KEY SANITIZATION (v160.0): Replace non-alphanumeric chars with underscores
        raw_fn = file_item['filename']
        ext = os.path.splitext(raw_fn)[1]
        base = os.path.splitext(raw_fn)[0]
        sanitized_base = re.sub(r'[^a-zA-Z0-9]', '_', base)
        fn = f"{uuid.uuid4()}_{sanitized_base}{ext}"
        
        mime, _ = mimetypes.guess_type(fn)
        
        # Bucket Sync: shared-resources is the authoritative bucket for STARS
        supabase_admin.storage.from_('shared-resources').upload(path=fn, file=file_item['content'], file_options={"content-type": mime or 'application/octet-stream'})
        url = supabase_admin.storage.from_('shared-resources').get_public_url(fn)
        
        # INSERT WITHOUT MANUAL ID (Let DB handle bigint)
        res_data = {
            "name": form.get('name', file_item['filename']),
            "type": form.get('type', 'Document'),
            "uploaded_by": u['email'],
            "timestamp": datetime.datetime.now().isoformat(),
            "description": form.get('description', ''),
            "category": form.get('category', 'General'),
            "url": url
        }
        supabase_admin.table('resources').insert(res_data).execute()
        return jsonify({"success": True, "url": url})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/resources/delete', methods=['POST'])
def handle_resource_delete():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        data = request.get_json(); 
        rid = data.get('id') or data.get('resource_id')
        if not rid: return jsonify({"error": "Resource ID required"}), 400
        
        # SCHEMA FALLBACK: Try multiple table names and ID types
        errs = []
        for table in ['resources', 'Resources', 'Library']:
            try:
                # Try as integer first (STARS default)
                try:
                    supabase_admin.table(table).delete().eq('id', int(rid)).execute()
                    return jsonify({"success": True})
                except:
                    # Fallback to string ID
                    supabase_admin.table(table).delete().eq('id', str(rid)).execute()
                    return jsonify({"success": True})
            except Exception as e:
                errs.append(str(e))
                continue
        return jsonify({"error": f"Delete failed: {'; '.join(errs)}"}), 500
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/sessions/schedule', methods=['POST'])
def handle_session_schedule():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        data = request.get_json()
        pid = data.get('pair_id')
        start = data.get('start_time')
        link = data.get('link')
        parts = data.get('participants', '')
        
        if not pid or not start:
            return jsonify({"error": "Pair ID and Start Time required"}), 400
            
        role = normalize_role(u.get('role', 'User'))
        fn_u, _, _ = format_user_name(u)
        
        session_data = {
            "pair_id": pid,
            "start_time": start,
            "meeting_link": link or "",
            "scheduled_by": u.get('email'),
            "scheduler_name": fn_u,
            "scheduler_role": role,
            "participants": parts,
            "status": "Scheduled"
        }
        
        # SCHEMA FALLBACK: Try multiple table names
        errs = []
        for table in ['sessions', 'Sessions', 'Events']:
            try:
                supabase_admin.table(table).insert(session_data).execute()
                return jsonify({"success": True})
            except Exception as e:
                errs.append(str(e))
                continue
        return jsonify({"error": f"Schedule failed: {'; '.join(errs)}"}), 500
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/sessions/delete', methods=['POST'])
def handle_session_delete():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        data = request.get_json(); sid = data.get('id')
        if not sid: return jsonify({"error": "Session ID required"}), 400
        
        # SCHEMA FALLBACK
        for table in ['sessions', 'Sessions', 'Events', 'Pairings']:
            try:
                supabase_admin.table(table).delete().eq('id', sid).execute()
                return jsonify({"success": True})
            except: continue
        return jsonify({"error": "Could not find session to delete"}), 404
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/delete-user', methods=['POST'])
def handle_delete_user():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        data = request.get_json(); email = data.get('email')
        if not email: return jsonify({"error": "Email required"}), 400
        
        # SCHEMA FALLBACK: STARS uses 'profiles' primarily
        for table in ['profiles', 'users', 'Registry', 'Staff']:
            try:
                supabase_admin.table(table).delete().eq('email', email).execute()
                return jsonify({"success": True})
            except: continue
        return jsonify({"error": "Could not find user to delete"}), 404
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/')
def serve_index(): return send_from_directory('.', 'index.html')
@app.route('/admin.html')
def serve_admin(): return send_from_directory('.', 'admin.html')
@app.route('/<path:path>')
def serve_static(path): return send_from_directory('.', path)

if __name__ == "__main__":
    load_local_passwords()
    # init_cloud_seed() # Disabled for STARS as table schema differs
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
