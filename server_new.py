import uuid
import datetime
import random
import requests
import os
import io
import re
import mimetypes
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

print('BARS Flask Cloud Server Initializing...')
SUPABASE_URL = os.environ.get('SUPABASE_URL', "https://cojvbregrwqgnzscmmub.supabase.co")
SUPABASE_KEY = os.environ.get('SUPABASE_ANON_KEY', "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNvanZicmVncndxZ256c2NtbXViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MjYxNDIsImV4cCI6MjA5MjUwMjE0Mn0.QCnDJtL7oYuvL8spFWaMWAxA6DG6u7lMid1a79yqYQI")
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNvanZicmVncndxZ256c2NtbXViIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjkyNjE0MiwiZXhwIjoyMDkyNTAyMTQyfQ.eRgflZH9Qy2EXIVkIAN0xd5tFf9mO2pM-Iqr8IFnv7s")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

SESSION_STORE = {}

def get_user_from_headers():
    if request.headers.get('X-Admin-Bypass') == 'BARS2026':
        return {"email": "admin@bars.ae", "role": "ProgramStaff", "name": "System Admin", "isCounselor": True}
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

@app.route('/api/initial-data', methods=['GET'])
def initial_data():
    return jsonify({"status": "Online", "v": "143.0 Registry Restoration"})

@app.route('/api/dashboard', methods=['GET'])
def handle_dashboard():
    try:
        u = get_user_from_headers()
        if not u: return jsonify({"error": "Auth Required"}), 401
        res = {"pairs": [], "mentors": [], "sessions": [], "resources": [], "messages": [], "profile": {}}
        
        def safe_fetch(table_names, fallback_data=[]):
            for name in table_names:
                try:
                    resp = supabase_admin.table(name).select('*').execute()
                    if resp.data is not None: return resp.data
                except: continue
            return fallback_data

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
                res["pairs"].append({"name": fn, "first_name": f_name, "last_name": l_name, "email": s_email, "pair_id": p_id, "type": "Mentee", "bio": safe_get(uu, ['bio']), "interests": safe_get(uu, ['interests'])})
            elif cur_role == 'Mentee' and s_email == u['email']:
                uu = users_map.get(m_email, {})
                fn, f_name, l_name = format_user_name(uu)
                res["pairs"].append({"name": fn, "first_name": f_name, "last_name": l_name, "email": m_email, "pair_id": p_id, "type": "Mentor", "bio": safe_get(uu, ['bio']), "interests": safe_get(uu, ['interests'])})
            elif cur_role == 'ProgramStaff':
                m = users_map.get(m_email, {}); s = users_map.get(s_email, {})
                fn_m, _, _ = format_user_name(m); fn_s, _, _ = format_user_name(s)
                res["pairs"].append({"mentor_name": fn_m, "mentee_name": fn_s, "pair_id": p_id, "mentor_email": m_email, "mentee_email": s_email})
        
        res["resources"] = resources_data
        res["sessions"] = sessions_data
        res["messages"] = messages_data 
        fn_u, f_u, l_u = format_user_name(u)
        is_c = normalize_role(u.get('role')) == 'ProgramStaff'
        res["profile"] = {"name": fn_u, "first_name": f_u, "last_name": l_u, "email": u.get('email'), "role": u['role'], "isCounselor": is_c}
        return jsonify(res)
    except Exception as e: return jsonify({"error": f"Dashboard Error: {str(e)}"}), 500

@app.route('/api/login', methods=['POST'])
def handle_login():
    try:
        data = request.get_json(); e, p = data.get('email', '').lower().strip(), data.get('password', '')
        resp = None
        for table in ['users', 'profiles', 'Registry', 'Staff']:
            try:
                r = supabase_admin.table(table).select('*').eq('email', e).eq('password', p).execute()
                if r.data: resp = r; break
            except: continue
        if resp and resp.data:
            r = resp.data[0]
            fn = safe_get(r, ['full_name', 'name']) or f"{safe_get(r, ['first_name', 'firstName'], '')} {safe_get(r, ['last_name', 'lastName'], '')}".strip() or "User"
            parts = fn.split(' ', 1); f_name = parts[0] if len(parts) > 0 else fn; l_name = parts[1] if len(parts) > 1 else ""
            user = {"email": e, "role": safe_get(r, ['role', 'user_role']), "name": fn, "first_name": f_name, "last_name": l_name, "isCounselor": (normalize_role(safe_get(r, ['role'])) == 'ProgramStaff')}
            token = str(uuid.uuid4()); SESSION_STORE[token] = user
            return jsonify({"success": True, "token": token, "user": user})
        return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e: return jsonify({"error": f"Login Error: {str(e)}"}), 500

@app.route('/api/admin/data', methods=['GET'])
def admin_data():
    if request.headers.get('X-Admin-Bypass') != 'BARS2026': return jsonify({"error": "Unauthorized"}), 401
    try:
        users = supabase_admin.table('users').select('*').execute().data or []
        pairs = supabase_admin.table('mentor_mentee_pairs').select('*').execute().data or []
        # Support fallback tables if main is empty
        if not users: users = supabase_admin.table('Registry').select('*').execute().data or []
        if not pairs: pairs = supabase_admin.table('Pairings').select('*').execute().data or []
        return jsonify({"users": users, "pairs": pairs, "profiles": users})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/admin/create', methods=['POST'])
def admin_create():
    if request.headers.get('X-Admin-Bypass') != 'BARS2026': return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json()
        email, fn, ln, role = data.get('email', '').lower().strip(), data.get('firstName', ''), data.get('lastName', ''), data.get('role', 'Mentee')
        full_name = f"{fn} {ln}".strip()
        supabase_admin.table('users').insert({"email": email, "full_name": full_name, "role": role, "password": "bars"}).execute()
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        email, fn, ln, pw, role = data.get('email', '').lower().strip(), data.get('firstName', ''), data.get('lastName', ''), data.get('password', ''), data.get('role', 'Mentee')
        full_name = f"{fn} {ln}".strip()
        supabase_admin.table('users').insert({"email": email, "full_name": full_name, "password": pw, "role": role, "bio": "", "interests": ""}).execute()
        return jsonify({"status": "success", "message": "Account created! You can now log in."}), 200
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/verify-staff', methods=['POST'])
def handle_verify_staff():
    data = request.get_json(); e = data.get('email', '').lower().strip()
    resp = None
    for table in ['users', 'profiles', 'Registry', 'Staff']:
        try:
            r = supabase_admin.table(table).select('*').eq('email', e).execute()
            if r.data: resp = r; break
        except: continue
    if resp and resp.data:
        r = resp.data[0]
        is_active = r.get('password') is not None and r['password'].strip() not in ['PENDING_ACTIVATION', '', 'pass']
        return jsonify({"success": True, "full_name": safe_get(r, ['full_name', 'name']), "is_activated": is_active})
    return jsonify({"error": "Staff not found"}), 404

@app.route('/api/activate-staff', methods=['POST'])
def handle_activate_staff():
    data = request.get_json(); e, p = data.get('email', '').lower().strip(), data.get('password', '')
    supabase_admin.table('users').update({"password": p}).eq('email', e).execute()
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
        if request.method == 'GET':
            for table in ['whiteboard', 'Whiteboard', 'Notes']:
                try:
                    resp = supabase_admin.table(table).select('*').order('created_at', desc=True).execute()
                    if resp.data is not None: return jsonify(resp.data)
                except: continue
            return jsonify([])
        else:
            data = request.get_json(); note = data.get('note')
            if normalize_role(u['role']) != 'ProgramStaff': return jsonify({"error": "Unauthorized"}), 403
            supabase_admin.table('whiteboard').insert({
                "mentor_name": u['name'],
                "mentor_email": u['email'],
                "note": note,
                "created_at": datetime.datetime.now().isoformat()
            }).execute()
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
        file_item = form['file']; fn = f"{uuid.uuid4()}_{file_item['filename']}"
        mime, _ = mimetypes.guess_type(file_item['filename'])
        supabase_admin.storage.from_('resource-files').upload(path=fn, file=file_item['content'], file_options={"content-type": mime or 'application/octet-stream'})
        url = supabase_admin.storage.from_('resource-files').get_public_url(fn)
        supabase_admin.table('resources').insert({"id": str(uuid.uuid4())[:8], "name": form.get('name', file_item['filename']), "type": form.get('type', 'Document'), "uploaded_by": u['email'], "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "description": form.get('description', ''), "category": form.get('category', 'General'), "url": url}).execute()
        return jsonify({"success": True, "url": url})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/resources/delete', methods=['POST'])
def handle_resource_delete():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        data = request.get_json(); rid = data.get('resource_id')
        supabase_admin.table('resources').delete().eq('id', rid).execute()
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/sessions/delete', methods=['POST'])
def handle_session_delete():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        data = request.get_json(); sid = data.get('id')
        supabase_admin.table('sessions').delete().eq('id', sid).execute()
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/delete-user', methods=['POST'])
def handle_delete_user():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        data = request.get_json(); email = data.get('email')
        supabase_admin.table('users').delete().eq('email', email).execute()
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/')
def serve_index(): return send_from_directory('.', 'index.html')
@app.route('/admin.html')
def serve_admin(): return send_from_directory('.', 'admin.html')
@app.route('/<path:path>')
def serve_static(path): return send_from_directory('.', path)

if __name__ == "__main__":
    init_cloud_seed()
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
