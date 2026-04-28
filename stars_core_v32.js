/* --- STARS AUTHORITATIVE MASTER CORE v9.0 --- */
const STARS_DEBUG = true;
const log = (msg) => STARS_DEBUG && console.log(`[STARS]: ${msg}`);

// 1. Session Engine
const StarsSession = {
    save(token, user) {
        const userStr = JSON.stringify(user);
        localStorage.setItem('stars_token', token);
        localStorage.setItem('stars_user', userStr);
        sessionStorage.setItem('stars_token', token);
        sessionStorage.setItem('stars_user', userStr);
        log("Session persisted.");
    },
    clear() {
        localStorage.removeItem('stars_token');
        localStorage.removeItem('stars_user');
        sessionStorage.removeItem('stars_token');
        sessionStorage.removeItem('stars_user');
        log("Session cleared.");
    },
    get() {
        const token = localStorage.getItem('stars_token') || sessionStorage.getItem('stars_token');
        const userJson = localStorage.getItem('stars_user') || sessionStorage.getItem('stars_user');
        if (!token || !userJson) return null;
        try { return { token, user: JSON.parse(userJson) }; } catch (e) { return null; }
    }
};
window.StarsSession = StarsSession;

// 2. Navigation
window.showAuthForm = function (id) {
    const gateway = document.getElementById('auth-gateway');
    const app = document.getElementById('app-container');
    const menu = document.getElementById('auth-menu');
    const forms = ['login', 'register', 'staff-verify', 'staff-activate', 'staff-login', 'visitor'];

    if (id === 'dash') {
        if (gateway) gateway.style.display = 'none';
        if (app) app.style.display = 'flex';
        window.dismissLoader(); // Ensure loader is hidden when entering dash
        initDashboard();
        return;
    }

    if (gateway) gateway.style.display = 'flex';
    if (app) app.style.display = 'none';
    if (id !== 'dash') window.location.hash = (id === 'menu' ? 'menu' : id);
    window.dismissLoader();

    // Safety: Ensure loader is gone after 5s even if something hangs
    setTimeout(() => window.dismissLoader(), 5000);

    if (menu) menu.style.display = (id === 'menu' ? 'grid' : 'none');

    forms.forEach(f => {
        const el = document.getElementById(f + '-form');
        if (el) el.style.display = (f === id ? 'flex' : 'none');
    });
};

window.showPage = function (pageId, el) {
    const user = StarsSession.get()?.user;
    const isCounselor = !!user?.isCounselor || !!user?.is_counselor;
    const isStaff = user?.role === 'ProgramStaff' || isCounselor;

    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const target = document.getElementById(pageId);
    if (target) {
        target.classList.add('active');
        // Final Fix: Force visibility for staff session controls if applicable
        if (pageId === 'sessions') {
            const controls = document.getElementById('counselor-session-controls');
            if (controls) {
                // EXCLUSIVE: Session scheduling is restricted to full Counselors
                controls.style.setProperty('display', isCounselor ? 'block' : 'none', 'important');
            }
        }
    }

    // Sidebar Highlight Sync (Fix for clicks from dashboard buttons)
    document.querySelectorAll('.sidebar-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-page') === pageId);
    });

    const data = window.DASH_DATA || {};
    if (pageId === 'dashboard') renderDashboardUI(data);
    if (pageId === 'mentors') window.renderMentors(data.mentors || [], 'mentors-search-grid');
    if (pageId === 'survey') window.renderSurveyCenter();
    if (pageId === 'sessions') {
        window.renderSessions(data.sessions || []);
        if (isCounselor && window.renderStaffSessionsSelector) window.renderStaffSessionsSelector();

        // Mentee Backup Visibility Logic
        const backup = document.getElementById('mentee-backup-surveys');
        if (backup) backup.style.display = (user?.role === 'Mentee' ? 'block' : 'none');
    }
    if (pageId === 'messages') window.renderMessages(data.messages || []);
    if (pageId === 'resources') window.renderResources(data.resources || []);
    if (pageId === 'whiteboard') window.renderWhiteboard();
    if (pageId === 'profile') window.renderProfile();
    if (pageId === 'settings') window.loadSettings();
};

window.logout = function () { StarsSession.clear(); location.reload(); };

window.renderProfile = function() {
    const user = StarsSession.get()?.user;
    if (!user) return;
    const fname = document.getElementById('prof-fname');
    const lname = document.getElementById('prof-lname');
    const email = document.getElementById('prof-email');
    
    if (fname) fname.innerText = user.first_name || user.name?.split(' ')[0] || 'User';
    if (lname) lname.innerText = user.last_name || user.name?.split(' ')[1] || '';
    if (email) email.innerText = user.email || '';
};

window.toggleSetting = function(el, key) {
    el.classList.toggle('active');
    const isActive = el.classList.contains('active');
    log(`Setting '${key}' toggled: ${isActive}`);
};

window.saveSettings = function() {
    const settings = {
        master: document.getElementById('toggle-master')?.classList.contains('active'),
        resources: document.getElementById('toggle-resources')?.classList.contains('active'),
        sessions: document.getElementById('toggle-sessions')?.classList.contains('active'),
        messages: document.getElementById('toggle-messages')?.classList.contains('active')
    };
    localStorage.setItem('stars_settings', JSON.stringify(settings));
    alert("✓ Settings saved successfully!");
};

window.loadSettings = function() {
    try {
        const stored = localStorage.getItem('stars_settings');
        if (!stored) return;
        const settings = JSON.parse(stored);
        if (settings.master) document.getElementById('toggle-master')?.classList.add('active');
        if (settings.resources) document.getElementById('toggle-resources')?.classList.add('active');
        if (settings.sessions) document.getElementById('toggle-sessions')?.classList.add('active');
        if (settings.messages) document.getElementById('toggle-messages')?.classList.add('active');
    } catch (e) { log("Failed to load settings."); }
};

// 3. NUCLEAR MANAGEMENT HANDLERS (Consolidated Custom Modal Confirmation)
window.starsConfirm = function (msg, onConfirm) {
    let m = document.getElementById('stars-confirm-modal');
    if (!m) {
        m = document.createElement('div');
        m.id = 'stars-confirm-modal';
        m.style = "display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:100000; align-items:center; justify-content:center; backdrop-filter:blur(4px);";
        m.innerHTML = `
            <div style="background:white; padding:2.5rem; border-radius:28px; max-width:450px; width:90%; text-align:center; border:3px solid #fce4ec; box-shadow: 0 20px 40px rgba(0,0,0,0.2);">
                <div style="width:60px; height:60px; background:#fff1f6; color:#e84393; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 1.5rem auto;">
                    <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                </div>
                <h3 style="color:#1e293b; font-family:'Outfit', sans-serif; font-weight:800; font-size:1.4rem; margin-bottom:0.5rem;">Confirm Action</h3>
                <p id="stars-confirm-msg" style="margin-bottom:2rem; color:#64748b; font-weight:500; font-size:0.95rem; line-height:1.5;"></p>
                <div style="display:flex; gap:1rem; justify-content:center;">
                    <button id="stars-confirm-yes" class="btn-magenta" style="flex:1; padding:1rem; border-radius:14px; font-weight:800;">Yes, Proceed</button>
                    <button id="stars-confirm-no" class="btn-white" style="flex:1; padding:1rem; border-radius:14px; font-weight:800; border:1px solid #fce4ec; color:#e84393;">Cancel</button>
                </div>
            </div>
        `;
        document.body.appendChild(m);
    }

    document.getElementById('stars-confirm-msg').textContent = msg;
    m.style.display = 'flex';

    const yes = document.getElementById('stars-confirm-yes');
    const no = document.getElementById('stars-confirm-no');

    // Clean up previous listeners
    const newYes = yes.cloneNode(true);
    const newNo = no.cloneNode(true);
    yes.parentNode.replaceChild(newYes, yes);
    no.parentNode.replaceChild(newNo, no);

    newYes.onclick = () => { m.style.display = 'none'; onConfirm(); };
    newNo.onclick = () => { m.style.display = 'none'; };
};

window.trashSurveySubmission = function (email, timestamp, type, btn) {
    window.starsConfirm("Are you sure you want to permanently delete this survey submission from both the database and the source Excel file?", async () => {
        if (btn) { btn.disabled = true; btn.style.opacity = '0.5'; }
        try {
            const res = await fetch('/api/survey/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${StarsSession.get().token}`
                },
                body: JSON.stringify({ email, timestamp, type })
            });
            const data = await res.json();
            if (data.status === 'success' || data.success) {
                alert("✓ Success: Record permanently removed.");
                await window.initSurveyCenter();
            } else {
                alert("❌ Server Error: " + (data.error || 'Deletion failed.'));
                if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
            }
        } catch (e) {
            alert("❌ Connectivity Error: " + e.message);
            if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
        }
    });
};

window.trashSession = function (sessionId, btn) {
    window.starsConfirm("Are you sure you want to cancel and permanently delete this session?", async () => {
        if (btn) { btn.disabled = true; btn.style.opacity = '0.5'; }
        try {
            const res = await fetch('/api/sessions/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${StarsSession.get().token}`
                },
                body: JSON.stringify({ id: sessionId })
            });
            const data = await res.json();
            if (data.status === 'success' || data.success) {
                alert("✓ Success: Session permanently cancelled.");
                if (window.DASH_DATA && window.DASH_DATA.sessions) {
                    window.DASH_DATA.sessions = window.DASH_DATA.sessions.filter(s => s.id !== sessionId);
                }
                window.showPage('sessions');
            } else {
                alert("❌ Server Error: " + (data.error || 'Deletion failed.'));
                if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
            }
        } catch (e) {
            alert("❌ Connectivity Error: " + e.message);
            if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
        }
    });
};

window.trashResource = async (resId, btn) => {
    window.starsConfirm("Are you sure you want to permanently delete this resource? This action cannot be undone.", async () => {
        logAPI('DELETE', '/api/resources/delete', 0, 'PENDING');
        if (btn) { btn.disabled = true; btn.style.opacity = '0.5'; }
        
        try {
            const res = await fetch('/api/resources/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${StarsSession.get().token}`
                },
                body: JSON.stringify({ id: resId })
            });

            // HARDENED HEARTBEAT: Log Status BEFORE parsing
            const text = await res.text();
            let data;
            try { data = JSON.parse(text); } catch (e) { data = { success: false, error: 'Malformed Server Response: ' + text.substring(0, 30) }; }
            
            logAPI('DELETE', '/api/resources/delete', res.status, data.success ? 'Success' : (data.error || 'Server error'));

            if (res.ok && data.success) {
                // OPTIMISTIC UI: Remove from list immediately
                const card = btn ? btn.closest('.resource-card') : null;
                if (card) {
                    card.style.opacity = '0';
                    card.style.transform = 'scale(0.9)';
                    setTimeout(() => card.remove(), 300);
                }
                
                // NO PAGE RELOAD: Stay in Library view as requested
                // console.log("✓ Resource deleted successfully (Local View Preserved)");
            } else {
                alert("❌ Deletion failed: " + (data.error || 'Server error.'));
                if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
            }
        } catch (e) {
            logAPI('ERR', '/api/resources/delete', 'Fail', e.message);
            alert("❌ Connectivity Error: " + e.message);
            if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
        }
    });
};

// 4. Auth Handlers
window.handleAuthSubmit = async function (event, type) {
    if (event) event.preventDefault();
    const errorEl = document.getElementById(type + '-error') || document.getElementById('staff-error');
    try {
        let payload = {};
        let endpoint = (type === 'register' ? 'register' : 'login');
        if (type === 'login') {
            payload = { email: document.getElementById('login-email').value, password: document.getElementById('login-password').value };
        } else if (type === 'register') {
            payload = {
                email: document.getElementById('register-email').value,
                password: document.getElementById('register-password').value,
                firstName: document.getElementById('register-fname').value,
                lastName: document.getElementById('register-lname').value,
                role: document.getElementById('register-role').value
            };
        } else if (type === 'staff-login' || type === 'staff') {
            payload = { email: document.getElementById('staff-email').value, password: document.getElementById('staff-password').value };
            endpoint = 'login';
        } else if (type === 'visitor') {
            const visitorEmail = document.getElementById('visitor-email').value;
            const res = await fetch('/api/visitor', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: visitorEmail, firstName: document.getElementById('visitor-fname').value, lastName: document.getElementById('visitor-lname').value })
            });
            if (!res.ok) throw new Error("Failed to request code.");

            const visitorData = await res.json();
            const msgEl = document.getElementById('visitor-sent-msg');
            if (visitorData.otp) {
                // Presentation Mode: Show prominently in the box AND alert
                msgEl.innerHTML = `✓ Code Generated! Access Code: <span style="font-size: 1.2rem; color: #e84393; text-decoration: underline;">${visitorData.otp}</span>`;
                window.alert(`[DEVELOPER MODE]: Since this is a student project, your access code is: ${visitorData.otp}`);
            }

            // Show feedback
            msgEl.style.display = 'block';
            document.getElementById('visitor-otp-block').style.display = 'block';
            document.getElementById('visitor-submit-btn').style.display = 'none';
            return false;
        }

        const response = await fetch(`/api/${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Authentication failed");

        StarsSession.save(result.token, result.user);
        window.showAuthForm('dash');
    } catch (err) {
        if (errorEl) { errorEl.textContent = err.message; errorEl.style.display = 'block'; }
    }
};

window.handleStaffVerify = async function (event) {
    if (event) event.preventDefault();
    const email = document.getElementById('staff-verify-email').value;
    const errorEl = document.getElementById('staff-verify-error');
    const titleEl = document.getElementById('staff-login-title');
    try {
        const res = await fetch('/api/verify-staff', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);
        if (data.is_activated) {
            if (titleEl) titleEl.textContent = "Welcome back!";
            if (document.getElementById('staff-email')) document.getElementById('staff-email').value = email;
            window.showAuthForm('staff-login');
        } else {
            // New user Flow: Screenshot/Request parity
            if (titleEl) titleEl.textContent = "Welcome! Create your password";
            window.STAFF_ACTIVATING_EMAIL = email;
            window.showAuthForm('staff-activate');
        }
    } catch (e) { if (errorEl) { errorEl.textContent = e.message; errorEl.style.display = 'block'; } }
};

window.handleStaffActivate = async function (event) {
    if (event) event.preventDefault();
    const pass = document.getElementById('staff-activate-pass').value;
    const confirm = document.getElementById('staff-activate-confirm').value;
    const errorEl = document.getElementById('staff-activate-error');
    if (pass !== confirm) return alert("Passwords do not match.");
    if (pass.length < 4) return alert("Password must be at least 4 characters.");

    const email = window.STAFF_ACTIVATING_EMAIL;
    log(`Activating account for ${email}...`);

    try {
        // STEP 1: Activate account in DB
        const actRes = await fetch('/api/activate-staff', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password: pass })
        });
        if (!actRes.ok) throw new Error("Activation failed.");

        // STEP 2: Login with the new password
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password: pass })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Login failed after activation.");

        StarsSession.save(data.token, data.user);
        window.showAuthForm('dash');
    } catch (err) { 
        if (errorEl) { errorEl.textContent = err.message; errorEl.style.display = 'block'; }
        else alert(err.message); 
    }
};

window.verifyVisitorOTP = async function () {
    const email = document.getElementById('visitor-email').value;
    const code = document.getElementById('visitor-otp').value;
    try {
        const res = await fetch('/api/visitor/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, code })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);
        StarsSession.save(data.token, data.user);
        window.showAuthForm('dash');
    } catch (e) { alert(e.message); }
};

window.handleOTP = function (el, idx) {
    if (el.value.length === 1 && idx < 6) {
        // Find next box
        const next = el.nextElementSibling;
        if (next) next.focus();
    }

    // Aggregate digits
    const boxes = document.querySelectorAll('.otp-field');
    let code = "";
    boxes.forEach(b => code += b.value);
    document.getElementById('visitor-otp').value = code;
};

// 4. Dash Init
async function initDashboard() {
    log("Initializing Dashboard Logic...");
    try {
        const session = StarsSession.get();
        if (!session) {
            showAuthForm('menu');
            return;
        }
        const { token, user } = session;

        // Correct Sidebar Selector (#dynamic-sidebar)
        const sidebar = document.getElementById('dynamic-sidebar');
        if (!sidebar) {
            console.error("Dashboard sidebar container not found.");
            dismissLoader();
            return;
        }

        // Apply Counselor Theme
        const isCounselor = !!user.is_counselor || !!user.isCounselor || user.role === 'ProgramStaff';
        document.body.classList.toggle('counselor-theme', isCounselor);

        // Fetch Live Dashboard Data
        const res = await fetch('/api/dashboard', { 
            headers: { 'Authorization': `Bearer ${token}` } 
        });
        if (!res.ok) throw new Error("Database synchronization failed.");
        
        const data = await res.json();
        window.DASH_DATA = data; // Authoritative state
        log("Portal Data Synced.");

        // Populate Sidebar
        const items = [
            { id: 'dashboard', label: 'Dashboard' },
            { id: 'messages', label: 'Messages', hideForStaffOnly: true, hideForMentors: true },
            { id: 'survey', label: 'Survey Center', hideForMentees: true, hideForMentors: true },
            { id: 'sessions', label: 'My Sessions', hideForStaffOnly: true, hideForVisitors: true },
            { id: 'resources', label: 'Library' },
            { id: 'whiteboard', label: 'Whiteboard', hideForMentees: true },
            { id: 'profile', label: 'My Profile' },
            { id: 'contact', label: 'Contact Us' },
            { id: 'settings', label: 'Settings' }
        ];

        sidebar.innerHTML = items.map(item => {
            if (item.hideForMentees && user.role === 'Mentee') return '';
            if (item.hideForStaffOnly && user.role === 'ProgramStaff' && !isCounselor) return '';
            if (item.hideForVisitors && user.role === 'Visitor') return '';
            return `<li class="sidebar-btn" onclick="window.showPage('${item.id}', this)" data-page="${item.id}">${item.label}</li>`;
        }).join('');

        if (user.role === 'Program Manager' || user.role === 'Counselor' || isCounselor) {
            sidebar.innerHTML += `<li class="sidebar-btn" onclick="window.location.href='/admin.html'" style="color:#e84393; font-weight:800; background:#fff1f6;">Management Console</li>`;
        }

        // Trigger UI Renders
        window.showPage('dashboard');

        // Profile Sync
        const profName = document.getElementById('profile-name');
        if (profName) profName.textContent = user.full_name || user.name || 'User';
        
        const profInitial = document.getElementById('profile-initial');
        if (profInitial) profInitial.textContent = (user.full_name || user.name || 'U').charAt(0).toUpperCase();

        dismissLoader();
    } catch (e) {
        log(`Dash error: ${e.message}`);
        dismissLoader();
    }
}
function dismissLoader() {
    const l = document.getElementById('system-loader');
    if (l) {
        l.style.setProperty('display', 'none', 'important');
        log("Initial loader dismissed.");
    }
}
window.dismissLoader = dismissLoader;

function renderDashboardUI(data) {
    const user = StarsSession.get()?.user;
    if (!user) return;

    const isCounselor = !!user?.isCounselor || !!user?.is_counselor;
    const isStaff = user?.role === 'ProgramStaff' || isCounselor;

    if (STARS_DEBUG) console.log("[DASH]: Rendering for", user.role, "Staff?", isStaff);

    // 1. Discovery/Find Mentors Gating
    const discSec = document.getElementById('dash-all-mentors-section');
    if (discSec) {
        if (user.role === 'Mentee' || isStaff) {
            discSec.style.display = 'none';
        } else {
            discSec.style.display = 'block';
            if (window.renderMentors) window.renderMentors(data.mentors || [], 'dash-mentors-list-container');
        }
    }

    // 2. Authoritative Quick Actions Rendering (MUST RENDER REGARDLESS OF PAIRS)
    const qa = document.getElementById('dash-quick-actions');
    if (qa) {
        let actions = '';
        if (isStaff) {
            const btnOne = isCounselor ? 'Messages' : 'Library';
            const pageOne = isCounselor ? 'messages' : 'resources';
            const btnTwo = isCounselor ? 'Survey Center' : 'My Sessions';
            const pageTwo = isCounselor ? 'survey' : 'sessions';

            actions = `
                <button class="btn-magenta" onclick="window.location.href='admin.html'">Management Console</button>
                <button class="btn-white" onclick="window.showPage('${pageOne}')">${btnOne}</button>
                <button class="btn-white" onclick="window.showPage('${pageTwo}')">${btnTwo}</button>
            `;
        } else if (user.role === 'Visitor') {
            actions = `
                <button class="btn-magenta" onclick="window.showPage('resources')">Browse Library</button>
                <button class="btn-white" onclick="window.showPage('profile')">My Profile</button>
            `;
        } else if (user.role === 'Mentor') {
            actions = `
                <button class="btn-magenta" onclick="window.showPage('messages')">Messages</button>
                <button class="btn-white" onclick="window.showPage('mentors')">Find Mentors</button>
                <button class="btn-white" onclick="window.showPage('sessions')">My Sessions</button>
            `;
        } else {
            // Mentee flow
            actions = `
                <button class="btn-magenta" onclick="window.showPage('messages')">Messages</button>
                <button class="btn-white" onclick="window.showPage('sessions')">My Sessions</button>
            `;
        }
        qa.innerHTML = `<div class="section-title">QUICK ACTIONS</div><div style="display:flex; gap:1rem; margin-top:1rem;">${actions}</div>`;
    }

    // 3. Robust Pairings Rendering
    const pairCont = document.getElementById('dash-pair-section');
    if (pairCont) {
        const pairs = data.pairs || [];
        if (pairs.length === 0) {
            pairCont.innerHTML = `<div style="text-align:center; padding:3rem; color:#94a3b8; font-weight:600;">No active pairings found. Please contact an administrator.</div>`;
            // DO NOT RETURN. Continue rendering.
        } else if (isStaff) {
            // Staff View: 2-Column Grid
            pairCont.innerHTML = `<div class="section-title" style="margin-top:2rem;">MENTOR-MENTEE PAIRINGS</div>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1.5rem; margin-top: 1rem;">` +
                pairs.map(p => `
                <div class="glass-card" style="padding: 1.5rem; border-radius: 20px; background: white; border: 1.5px solid #f1f5f9;">
                    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1.25rem;">
                        <div style="background: #e91e63; color: white; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.9rem;">${p.mentor_name?.charAt(0) || 'M'}</div>
                        <div>
                            <div style="font-size: 0.65rem; color: #94a3b8; font-weight: 800; text-transform: uppercase;">MENTOR</div>
                            <div style="font-weight: 800; color: #1e293b; font-size: 1.1rem;">${p.mentor_name || 'Unassigned'}</div>
                            <div style="font-size: 0.8rem; color: #e84393; font-weight: 700; margin-top: 0.1rem;">${p.mentor_email || ''}</div>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <div style="background: #f78fb3; color: white; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.9rem;">${p.mentee_name?.charAt(0) || 'S'}</div>
                        <div>
                            <div style="font-size: 0.65rem; color: #94a3b8; font-weight: 800; text-transform: uppercase;">MENTEE</div>
                            <div style="font-weight: 800; color: #1e293b; font-size: 1.1rem;">${p.mentee_name || 'Unassigned'}</div>
                            <div style="font-size: 0.8rem; color: #e84393; font-weight: 700; margin-top: 0.1rem; display: block !important;">${p.mentee_email || ''}</div>
                        </div>
                    </div>
                </div>
            `).join('') + `</div>`;
        } else {
            // Student View (Mentor or Mentee)
            const typeLabel = (pairs[0].type || "").toUpperCase().includes('MENTEE') ? 'MENTEES' : 'MENTORS';
            pairCont.innerHTML = `<div class="section-title" style="margin-top:2rem;">YOUR ${typeLabel}</div>` + pairs.map(p => {
                const initial = (p.name || "U").charAt(0);
                return `
                    <div class="mentee-card-yellow" style="margin-bottom: 2rem; border-radius: 28px; padding: 2.5rem; border: 2px solid #fef3c7; background: #fffcf0;">
                        <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                            <div style="display: flex; align-items: center; gap: 2.5rem;">
                                <div style="background: #e84393; color: white; width: 85px; height: 85px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.8rem; box-shadow: 0 5px 15px rgba(232, 67, 147, 0.2);">${initial}</div>
                                <div style="text-align: left;">
                                    <div style="font-size: 0.85rem; color: #94a3b8; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0.4rem;">YOUR ${p.type || "PARTNER"}</div>
                                    <h3 style="margin: 0; color: #e84393; font-size: 1.85rem; font-weight: 800; letter-spacing: -0.5px;">${p.name || "User"}</h3>
                                    <div style="font-size: 0.9rem; color: #94a3b8; font-weight: 700; margin-top: 0.2rem;">${p.email || ''}</div>
                                </div>
                            </div>
                            <div class="dash-card-btn-stack">
                               <button class="btn-magenta" onclick="window.switchChat('${p.pair_id}', '${p.name}')" style="font-weight:700;">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right:2px;"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                                    Chat
                               </button>
                               <button class="btn-white" onclick="window.showPage('${p.type === 'Mentor' ? 'sessions' : 'dashboard'}')" style="font-weight:700; background:white; color:#e84393; border: 1.5px solid #fce4ec;">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right:2px;"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                                    Sessions
                               </button>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }
    }
}

// 5. Survey Center
window.SURVEY_FILTERS = { role: 'Mentor', type: 'All', mentee: 'All', mode: 'self', days: 30 };
window.CURRENT_ANALYTICS_DAYS = parseInt(30);

window.switchSurveyView = function (view) {
    const user = StarsSession.get()?.user;
    if (user?.role === 'Mentor' && view === 'trends') return;
    document.getElementById('survey-list-view').style.display = (view === 'list' ? 'block' : 'none');
    document.getElementById('survey-analytics-view').style.display = (view === 'trends' ? 'block' : 'none');
    document.getElementById('toggle-list')?.classList.toggle('active', view === 'list');
    document.getElementById('toggle-trends')?.classList.toggle('active', view === 'trends');
    if (view === 'trends') window.renderSurveyTrends();
};

window.renderSurveyCenter = async function () {
    const user = StarsSession.get()?.user;
    if (!user) return;
    const isStaff = user.role === 'ProgramStaff' || !!user.isCounselor || !!user.is_counselor;
    const isMentor = user.role === 'Mentor';

    const hub = document.getElementById('mentor-safeguarding-hub');
    const backup = document.getElementById('mentor-backup-surveys-footer');
    const toggle = document.getElementById('counselor-survey-toggle');
    const surveySection = document.getElementById('survey');

    if (hub) hub.style.display = isMentor ? 'block' : 'none';
    if (backup) backup.style.display = isMentor ? 'block' : 'none';
    if (toggle) toggle.style.display = isStaff ? 'flex' : 'none';

    if (isMentor && hub && surveySection && backup) {
        // PROMOTED REORDER: Banner (Header) -> Hub (Safeguarding) -> Backup (Links) -> Rest
        const banner = surveySection.querySelector('.banner-block');
        if (banner) {
            surveySection.prepend(banner);
            banner.insertAdjacentElement('afterend', hub);
            hub.insertAdjacentElement('afterend', backup);
        }
        hub.style.marginTop = '1.5rem';
        backup.style.marginTop = '1.5rem';
        // Populating safeguarding selector
        const selCont = document.getElementById('emergency-contact-selector');
        if (selCont) {
            const pairs = window.DASH_DATA?.pairs || [];
            selCont.innerHTML = `<select id="emergency-mentee-select" style="padding:1rem; border-radius:12px; border:1.5px solid #ffdde1; background:white; font-weight:700; color:#b91c1c;">
                ${pairs.map(p => `<option value="${p.mentee_name || p.name}">${p.mentee_name || p.name}</option>`).join('')}
            </select>`;
        }
    }

    try {
        const fetchDays = parseInt(window.CURRENT_ANALYTICS_DAYS) || 30;
        const fil = window.SURVEY_FILTERS;
        const res = await fetch(`/api/survey/analytics?days=${fetchDays}&mode=${fil.mode || 'self'}&role=${fil.role || 'All'}`, {
            headers: { 'Authorization': `Bearer ${StarsSession.get().token}` }
        });
        if (!res.ok) throw new Error("Backend server error");
        window.SURVEY_DATA = await res.json();
    } catch (e) {
        console.error("Survey fetch fail:", e);
        window.SURVEY_DATA = { surveys: [], trends: [] };
        const cont = document.getElementById('survey-responses-container');
        if (cont) cont.innerHTML = `<div style="text-align:center; padding:3rem; color:#e84393; font-weight:700;">Unable to connect to Survey Analytics. Please ensure the backend is running.</div>`;
    } finally {
        window.renderSurveyFilters();
        window.applySurveyFilters();
    }
};

window.setSurveyFilter = function (k, v) {
    window.SURVEY_FILTERS[k] = v;
    // If we switch modes or audiences, we need a fresh authoritative fetch from partitioned backend
    if (k === 'mode' || k === 'role') {
        window.renderSurveyCenter();
    } else {
        window.renderSurveyFilters();
        window.applySurveyFilters();
    }
};

window.initSurveyCenter = window.renderSurveyCenter;

window.renderSurveyFilters = function () {
    const filterCont = document.getElementById('survey-filters');
    if (!filterCont) return;
    console.log("SURVEY SYSTEM: INITIALIZING FILTERS v5.0");
    const session = StarsSession.get();
    const currentUser = session?.user;
    const isProgramStaff = currentUser?.role === 'ProgramStaff' || !!currentUser?.isCounselor || !!currentUser?.is_counselor;
    const isSurveyMentor = currentUser?.role === 'Mentor';
    const fil = window.SURVEY_FILTERS;

    let filterHtml = '';

    if (isProgramStaff) {
        // 1. Counselor: Multi-Survey Toggle (Mentor vs Mentee responses)
        filterHtml += `
        <div style="display: flex; flex-direction: column; gap: 1rem; width: 100%; margin-bottom: 2rem;">
            <div style="font-size: 0.85rem; color: #94a3b8; font-weight: 800; text-transform: uppercase;">Toggle Audience</div>
            <div style="display: flex; gap: 0.5rem; justify-content: flex-start;">
                <button onclick="window.setSurveyFilter('role', 'Mentor')" 
                    class="pairing-pill ${fil.role === 'Mentor' ? 'active' : ''}" 
                    style="border:none; margin:0; border-radius:15px; padding: 0.8rem 1.5rem; font-weight:700; flex: 1; max-width: 200px;">
                    Mentor Responses
                </button>
                <button onclick="window.setSurveyFilter('role', 'Mentee')" 
                    class="pairing-pill ${fil.role === 'Mentee' ? 'active' : ''}" 
                    style="border:none; margin:0; border-radius:15px; padding: 0.8rem 1.5rem; font-weight:700; flex: 1; max-width: 200px;">
                    Mentee Responses
                </button>
            </div>
            
            <div style="display: flex; align-items: center; gap: 1rem; margin-top: 0.5rem;">
                <span style="font-size: 0.8rem; color: #e84393; font-weight: 800;">SUB-FILTER:</span>
                <select onchange="window.setSurveyFilter('type', this.value)" 
                    style="padding: 0.8rem 1.2rem; border-radius: 15px; border: 2.5px solid #fce4ec; background: white; color: #e84393; font-weight: 700; outline: none; cursor: pointer; font-family: 'Outfit', sans-serif;">
                    <option value="All" ${fil.type === 'All' ? 'selected' : ''}>All Survey Types</option>
                    <option value="Pre-Session" ${fil.type === 'Pre-Session' ? 'selected' : ''}>Pre-Session</option>
                    <option value="Post-Session" ${fil.type === 'Post-Session' ? 'selected' : ''}>Post-Session</option>
                    <option value="During-Session" ${fil.type === 'During-Session' ? 'selected' : ''}>During/Periodic</option>
                </select>
            </div>
        </div>`;
    }

    if (isSurveyMentor) {
        // 2. Mentor: My Data vs. Mentee Data
        filterHtml += `
        <div style="display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; width: 100%;">
             <div style="display: flex; background: #fff1f6; padding: 0.4rem; border-radius: 16px; border: 1.5px solid #fce4ec;">
                <button onclick="window.setSurveyFilter('mode', 'self')" 
                    class="pairing-pill ${fil.mode === 'self' ? 'active' : ''}" 
                    style="border:none; margin:0; border-radius:12px; font-weight:700;">My Responses</button>
                <button onclick="window.setSurveyFilter('mode', 'mentees')" 
                    class="pairing-pill ${fil.mode === 'mentees' ? 'active' : ''}" 
                    style="border:none; margin:0; border-radius:12px; font-weight:700;">Mentee Data</button>
            </div>`;

        // Dynamic Mentee List if mode is 'mentees'
        if (fil.mode === 'mentees') {
            const myPairs = window.DASH_DATA?.pairs || [];
            if (myPairs.length > 0) {
                filterHtml += `
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <span style="font-size: 0.8rem; color: #e84393; font-weight: 800;">VIEW MENTEE:</span>
                    <select onchange="window.setSurveyFilter('mentee', this.value)" 
                        style="padding: 0.6rem 1rem; border-radius: 12px; border: 1.5px solid #fce4ec; background: white; color: #e84393; font-weight: 700; outline: none; cursor: pointer;">
                        <option value="All" ${fil.mentee === 'All' ? 'selected' : ''}>All My Mentees</option>
                        ${myPairs.map(p => `
                            <option value="${p.mentee_name || p.name}" ${fil.mentee === (p.mentee_name || p.name) ? 'selected' : ''}>${p.mentee_name || p.name}</option>
                        `).join('')}
                    </select>
                </div>`;
            }
        }
        filterHtml += `</div>`;
    }

    filterCont.innerHTML = filterHtml;
};

window.applySurveyFilters = function () {
    const rawData = window.SURVEY_DATA?.surveys || [];
    const fil = window.SURVEY_FILTERS;
    const activeUser = StarsSession.get()?.user;
    const isStaffRole = activeUser?.role === 'ProgramStaff' || !!activeUser?.isCounselor || !!activeUser?.is_counselor;
    const isMentorRole = activeUser?.role === 'Mentor';

    const filteredResponses = rawData.filter(s => {
        // Staff Filtering
        if (isStaffRole) {
            const auditRole = String(s.role || '').trim().toLowerCase();
            const filterRole = String(fil.role || '').trim().toLowerCase();
            const roleMatch = (fil.role === 'All' || auditRole === filterRole);
            const typeMatch = (fil.type === 'All' || s.type === fil.type);
            return roleMatch && typeMatch;
        }

        // Mentor Filtering
        if (isMentorRole) {
            const isSelf = (s.email || s.user_email) === activeUser.email;
            if (fil.mode === 'self') {
                return isSelf;
            } else {
                // Mentee Data view
                if (isSelf) return false;
                const menteeMatch = (fil.mentee === 'All' || s.name === fil.mentee);
                return menteeMatch;
            }
        }

        return true;
    });

    const surveyResponseContainer = document.getElementById('survey-responses-container');
    if (surveyResponseContainer) {
        surveyResponseContainer.innerHTML = filteredResponses.map(s => {
            const emergencyKeywords = ['emergency', 'urgent', 'safety', 'danger', 'harm', 'help', 'immediate', 'safeguarding'];

            // AUTHORITATIVE SCAN: Check all responses in the bundle for emergency keywords
            const bundleText = s.responses.map(r => (r.q || '') + ' ' + (r.a || '')).join(' ').toLowerCase();
            const containsEmergency = emergencyKeywords.some(k => bundleText.includes(k));

            const cardBg = containsEmergency ? '#fff8f8' : 'white';
            const cardBorder = containsEmergency ? '#ef4444' : '#fce4ec';

            const responseHtml = s.responses.map(r => `
                <div style="margin-bottom: 1rem; border-bottom: 1px solid #f1f5f9; padding-bottom: 0.5rem;">
                    <div style="font-weight:700; margin-bottom:0.2rem; font-size: 0.9rem;">${r.q}</div>
                    <div style="color:#475569; font-size: 0.95rem;">${r.a}</div>
                </div>
            `).join('');

            return `
            <div style="background:${cardBg}; border-radius:24px; padding:2rem; border:2px solid ${cardBorder}; margin-bottom:1.5rem; position: relative;">
                ${containsEmergency ? '<div style="position:absolute; top:1.5rem; right:2rem; background:#ef4444; color:white; padding:0.4rem 0.8rem; border-radius:8px; font-size:0.65rem; font-weight:800; text-transform:uppercase; letter-spacing:0.5px;">Safeguarding Alert</div>' : ''}
                
                <div style="display:flex; justify-content:space-between; margin-bottom:1.5rem; align-items: flex-start;">
                    <div>
                        <div style="font-weight: 800; color:#e84393; font-size: 1.1rem;">${s.name}</div>
                        <div style="font-size: 0.75rem; color: #94a3b8; font-weight: 700; text-transform: uppercase;">${s.role} • ${s.type}</div>
                    </div>
                    <div style="text-align: right;">
                        <span style="color:#94a3b8; font-size:0.85rem; font-weight: 600;">${new Date(s.timestamp).toLocaleDateString()}</span>
                        ${isStaffRole ? `
                            <div style="margin-top: 0.5rem;">
                                <button 
                                    data-action="trash-survey" 
                                    data-email="${s.email}" 
                                    data-ts="${s.timestamp}" 
                                    data-type="${s.type}"
                                    onclick="window.trashSurveySubmission('${s.email}', '${s.timestamp}', '${s.type}', this)"
                                    style="background:none; border:none; color:#ef4444; padding:0.5rem; cursor:pointer;" title="Delete Submission">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                                </button>
                            </div>
                        ` : ''}
                    </div>
                </div>

                <div style="background:${containsEmergency ? 'rgba(239, 68, 68, 0.05)' : '#fff8f8'}; padding:1.5rem; border-radius:20px;">
                    ${responseHtml}
                </div>
            </div>`;
        }).join('') || '<div style="text-align:center; padding:3rem; color:#94a3b8;">No matching responses found for current criteria.</div>';
    }
};

// Surgical Cleanup Complete - Redundant definitions removed.

window.updateAnalyticsTimeframe = function (days) {
    window.CURRENT_ANALYTICS_DAYS = parseInt(days) || 30;
    document.querySelectorAll('#analytics-timeline-filters .pairing-pill').forEach(btn => {
        const t = btn.textContent;
        const m = (days === 7 && t.includes('1 Week')) || (days === 14 && t.includes('2 Weeks')) || (days === 21 && t.includes('3 Weeks')) || (days === 30 && t.includes('30 Days')) || (days === 90 && t.includes('90 Days'));
        btn.classList.toggle('active', !!m);
    });
    window.renderSurveyCenter();
};

// 6. Safeguarding
window.triggerEmergencyOutlook = function () {
    const sel = document.getElementById('emergency-mentee-select');
    const name = sel ? sel.value : (window.DASH_DATA?.pairs[0]?.mentee_name || 'My Mentee');
    const subject = encodeURIComponent(`STARS Emergency Safeguarding Request - ${name}`);
    const body = encodeURIComponent(`Hello Counselors,\n\nI am requesting an immediate safeguarding check for ${name}.\n\nPlease review the recent survey responses and reach out.\n\nBest regards,\nSTARS Mentor`);
    window.location.href = `mailto:counselors@naischool.ae?subject=${subject}&body=${body}`;
};

window.copySafetyPrompt = function (e) {
    const sel = document.getElementById('emergency-mentee-select');
    const name = sel ? sel.value : (window.DASH_DATA?.pairs[0]?.mentee_name || "[mentee's name]");
    const text = `Hello Counselors, I am requesting an immediate safeguarding check for ${name}. Please review the recent survey responses.`;
    navigator.clipboard.writeText(text).then(() => {
        const btn = e.target;
        const old = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = old, 2000);
    });
};

// 7. Messaging
window.renderMessages = function (messages) {
    const target = document.getElementById('message-target-pills');
    if (!target) return;
    const user = StarsSession.get()?.user;
    if (!user) return;
    const isCounselor = !!user.isCounselor || !!user.is_counselor;
    const isStaff = user.role === 'ProgramStaff' || isCounselor;
    const pairs = window.DASH_DATA?.pairs || [];

    // Remove legacy placeholder elements
    const placeholder = document.getElementById('message-placeholder-text');
    if (placeholder) placeholder.style.display = 'none';

    if (isStaff) {
        // Counselor messenger list (Screenshot 1 parity: grouped headers + yellow cards)
        const grouped = {};
        pairs.forEach(p => {
            const mName = p.mentor_name || 'Unassigned Mentor';
            if (!grouped[mName]) grouped[mName] = [];
            grouped[mName].push(p);
        });

        target.innerHTML = Object.keys(grouped).map(mentor => `
            <div class="pair-label" style="color: #64748b; font-size: 0.75rem; font-weight: 800; margin-top: 1.5rem; margin-bottom: 0.5rem; text-transform: uppercase;">MENTOR: ${mentor}</div>
            ${grouped[mentor].map(p => `
                <div class="mentee-card-yellow" onclick="window.switchChat('${p.pair_id}', '${p.mentee_name}')" style="margin-bottom: 0.75rem; padding: 1rem 1.25rem;">
                    <div style="background: #f7b731; color: white; width: 45px; height: 45px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.1rem; flex-shrink: 0;">${p.mentee_name.charAt(0)}</div>
                    <div>
                        <div style="font-weight: 800; color: #1e293b; font-size: 1.05rem;">${p.mentee_name}</div>
                        <div style="font-size: 0.8rem; color: #1e293b; font-weight: 600;">${p.mentee_email || p.email || ''}</div>
                        <div style="font-size: 0.75rem; color: #94a3b8; font-weight: 600; margin-top:0.1rem;">Tap to open chat</div>
                    </div>
                </div>
            `).join('')}
        `).join('');
    } else if (user.role === 'Mentee') {
        // Mentee: Auto-open active chat, hide selector (Final Polish)
        document.getElementById('message-selector-container').style.display = 'none';
        if (pairs.length > 0) {
            const p = pairs[0];
            const partnerName = p.mentor_name || p.name;
            window.switchChat(p.pair_id, partnerName);
        }
        target.innerHTML = '';
    } else {
        // Mentor view
        target.innerHTML = pairs.map(p => {
            const name = (user.role === 'Mentor' ? p.mentee_name : p.mentor_name) || p.name;
            const subtext = user.role === 'Mentor' ? (p.mentee_email || '') : (p.mentor_email || '');
            return `<div class="message-contact-card" onclick="window.switchChat('${p.pair_id}', '${name}')" style="background:#fffde7; padding:1.2rem; border-radius:20px; border:2px solid #fef08a; cursor:pointer; margin-bottom:0.8rem; display:flex; align-items:center; gap:1rem;">
                <div style="background:#e84393; color:white; width:40px; height:40px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:800;">${name.charAt(0)}</div>
                <div>
                   <div style="font-weight:800; color:#e84393;">${name}</div>
                   <div style="font-size: 0.8rem; color: #e84393; opacity: 0.8; font-weight: 600;">${subtext}</div>
                </div>
            </div>`;
        }).join('');
    }
};

window.switchChat = function (id, name) {
    window.CURRENT_CHAT_PAIR = id;
    document.getElementById('message-selector-container').style.display = 'none';
    const active = document.getElementById('active-chat-container');
    active.style.display = 'flex';
    document.getElementById('chat-header-name').textContent = name;

    // Final Screenshot Parity: Remove generic headers & instruction text
    const headerTitle = active.querySelector('h2');
    if (headerTitle) headerTitle.style.display = 'none';
    const subtitle = document.getElementById('chat-header-subtitle');
    if (subtitle) subtitle.style.display = 'none'; // Clean up selector text

    // Gating for Counselors: Remove send interface (Screenshot 4 request)
    const user = StarsSession.get()?.user;
    const isStaff = user?.role === 'ProgramStaff' || !!user?.isCounselor || !!user?.is_counselor;
    const sendBox = document.getElementById('chat-input-container');
    if (sendBox) sendBox.style.display = isStaff ? 'none' : 'flex';

    const header = document.getElementById('general-chat-header');
    if (!document.getElementById('chat-exit-btn')) {
        const btn = document.createElement('button');
        btn.id = 'chat-exit-btn';
        const user = StarsSession.get()?.user;
        const isMentee = user?.role === 'Mentee';
        btn.textContent = '← Exit Chat';
        btn.style.display = isMentee ? 'none' : 'block'; // ONLY hide for mentees (Final Fix)
        btn.className = 'btn-magenta';
        btn.style.padding = '0.5rem 1rem';
        btn.style.marginRight = '1rem';
        btn.onclick = window.exitChat;
        header.prepend(btn);
    }
    window.syncChat();
};

window.exitChat = function () {
    window.CURRENT_CHAT_PAIR = null;
    document.getElementById('message-selector-container').style.display = 'block';
    document.getElementById('active-chat-container').style.display = 'none';
};

window.syncChat = async function () {
    if (!window.CURRENT_CHAT_PAIR) return;
    const res = await fetch(`/api/messages?pair_id=${window.CURRENT_CHAT_PAIR}`, { headers: { 'Authorization': `Bearer ${StarsSession.get().token}` } });
    const msgs = await res.json();
    const body = document.getElementById('chat-body-content');
    if (body) {
        const u = StarsSession.get().user;
        const isCounselor = !!u.isCounselor || !!u.is_counselor || u.role === 'ProgramStaff';

        // Find the current pair to identify mentor/mentee roles for counselor view
        const currentPair = window.DASH_DATA?.pairs?.find(p => String(p.pair_id) === String(window.CURRENT_CHAT_PAIR));

        body.innerHTML = msgs.map(m => {
            const isMe = m.sender === u.email;
            let bubbleClass = isMe ? 'sent' : 'received';
            let label = '';

            if (isCounselor && currentPair) {
                const isMentor = m.sender === currentPair.mentor_email;
                const isMentee = m.sender === currentPair.mentee_email;

                // USER REQUEST: Mentor on right (sent style), Mentee on left (received style)
                bubbleClass = isMentor ? 'sent' : 'received';

                // Add explicit labels for counselor clarity
                const roleLabel = isMentor ? 'Mentor' : 'Mentee';
                const senderName = isMentor ? currentPair.mentor_name : currentPair.mentee_name;
                label = `<div style="font-size: 0.65rem; font-weight: 800; color: #94a3b8; margin-bottom: 0.2rem; text-transform: uppercase; align-self: ${isMentor ? 'flex-end' : 'flex-start'}">${roleLabel}: ${senderName || 'User'}</div>`;
            }

            return `
                <div style="display: flex; flex-direction: column; width: 100%; align-items: ${bubbleClass === 'sent' ? 'flex-end' : 'flex-start'}">
                    ${label}
                    <div class="chat-bubble ${bubbleClass}">
                        ${m.message}
                    </div>
                </div>`;
        }).join('');
        body.scrollTop = body.scrollHeight;
    }
};

window.sendMessage = async function (e) {
    if (e) e.preventDefault();
    const input = document.getElementById('chat-input');
    if (!input.value || !window.CURRENT_CHAT_PAIR) return;
    const res = await fetch('/api/messages', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${StarsSession.get().token}` }, body: JSON.stringify({ pair_id: window.CURRENT_CHAT_PAIR, message: input.value }) });
    if (res.ok) { input.value = ''; window.syncChat(); }
};

// 8. Analytics
window.renderSurveyTrends = function () {
    const ctx1 = document.getElementById('sentimentBarChart')?.getContext('2d');
    const ctx2 = document.getElementById('volumeTrendChart')?.getContext('2d');
    const data = window.SURVEY_DATA;
    if (!ctx1 || !ctx2 || !data) return;

    if (window._chart1) window._chart1.destroy();
    if (window._chart2) window._chart2.destroy();

    // Chart 1: Real Sentiment (Mood vs Impact)
    window._chart1 = new Chart(ctx1, {
        type: 'bar',
        data: {
            labels: ['Mood Today', 'Support Level', 'Overall Impact'],
            datasets: [{
                data: [data.mood_avg || 0, data.help_avg || 0, ((data.mood_avg + data.help_avg) / 2) || 0],
                backgroundColor: '#e84393'
            }]
        },
        options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, max: 5 } } }
    });

    // Chart 2: Real Volume Trends
    const labels = (data.volume_trend || []).map(t => t.date);
    const counts = (data.volume_trend || []).map(t => t.count);
    window._chart2 = new Chart(ctx2, {
        type: 'line',
        data: {
            labels: labels.length ? labels : ['No Data'],
            datasets: [{
                label: 'Submissions',
                data: counts.length ? counts : [0],
                borderColor: '#e84393',
                backgroundColor: 'rgba(232, 67, 147, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: { scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
    });
};

// 9. Lifecycle
window.addEventListener('load', () => {
    log("STARS Authority ONLINE.");
    if (StarsSession.get()) window.showAuthForm('dash');
    else window.showAuthForm('menu');
});

// Bindings
window.openScheduleModal = (n, p) => {
    document.getElementById('schedule-modal-overlay').style.display = 'flex';
    document.getElementById('selected-partner-name').textContent = n;
    window.SELECTED_PAIR_ID = p;
    
    const actualName = (n && n !== 'undefined') ? n : 'User';
    const initials = actualName.trim().split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase() || '?';
    const avatar = document.getElementById('selected-partner-avatar');
    if (avatar) avatar.textContent = initials;
    
    window.updateCalendar();

    // Privacy: Default to Mentee Only for Counselor sessions
    const user = StarsSession.get()?.user;
    const isCounselor = !!user?.isCounselor || user?.role === 'ProgramStaff';
    const participantsWrap = document.getElementById('counselor-participants-wrap');
    if (participantsWrap) {
        participantsWrap.style.display = isCounselor ? 'block' : 'none';
        document.getElementById('meeting-participants-select').value = 'Mentee Only';
    }

    window.switchScheduleStep(1);
};
window.closeScheduleModal = () => document.getElementById('schedule-modal-overlay').style.display = 'none';
window.switchScheduleStep = (s) => { document.getElementById('schedule-step-1').style.display = (s === 1 ? 'block' : 'none'); document.getElementById('schedule-step-2').style.display = (s === 2 ? 'block' : 'none'); };
window.updateCalendar = () => {
    const cont = document.getElementById('calendar-days');
    if (!cont) return;
    cont.innerHTML = '';
    const today = new Date().getDate();
    for (let d = 1; d <= 30; d++) {
        const div = document.createElement('div');
        div.className = 'calendar-day';
        div.textContent = d;
        if (d < today) {
            div.style.opacity = '0.3';
            div.style.pointerEvents = 'none';
        } else {
            div.onclick = () => { window.SELECTED_DATE = `2026-04-${d.toString().padStart(2, '0')}`; window.switchScheduleStep(2); };
        }
        cont.appendChild(div);
    }
};
window.submitSchedule = async () => {
    const time = document.getElementById('schedule-time-input').value;
    const link = document.getElementById('schedule-link-input').value;
    const user = StarsSession.get()?.user;
    const isCounselor = !!user?.isCounselor || user?.role === 'ProgramStaff';

    let participants = '';
    if (isCounselor) {
        const mode = document.getElementById('meeting-participants-select').value;
        const myPairs = window.DASH_DATA?.pairs || [];
        const pair = myPairs.find(p => p.pair_id === window.SELECTED_PAIR_ID);
        if (pair) {
            participants = user.email; // Host is always in
            if (mode === 'Mentee Only') participants += `,${pair.mentee_email || pair.email}`;
            else participants += `,${pair.mentee_email || pair.email},${pair.mentor_email}`;
        }
    }

    const res = await fetch('/api/sessions/schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${StarsSession.get().token}` },
        body: JSON.stringify({ pair_id: window.SELECTED_PAIR_ID, start_time: `${window.SELECTED_DATE}T${time}`, link: link || '', participants: participants })
    });
    if (res.ok) { window.closeScheduleModal(); initDashboard(); }
};
window.setSessionFilter = function (f) {
    window.CURRENT_SESSION_FILTER = f;
    const btns = document.querySelectorAll('.session-tabs-wrap .pairing-pill');
    btns.forEach(btn => {
        if (btn.innerText.toLowerCase().includes(f.toLowerCase())) btn.classList.add('active');
        else btn.classList.remove('active');
    });
    // AUTHORITATIVE FIX: Only re-render the list, DO NOT initDashboard (to avoid redirect)
    window.renderSessions(window.DASH_DATA?.sessions || []);
};

window.renderSessions = function (sessions) {
    const list = document.getElementById('sessions-list-container');
    if (!list) return;
    const user = StarsSession.get()?.user;
    const isMentee = user?.role === 'Mentee';
    const filter = window.CURRENT_SESSION_FILTER || 'Upcoming';

    const now = new Date().getTime();
    const filtered = sessions.filter(s => {
        const sTime = new Date(s.start_time).getTime();
        if (filter === 'Past') return sTime < now;
        if (filter === 'Upcoming') return sTime >= now;
        return true;
    });

    list.innerHTML = filtered.map(s => {
        const isScheduler = s.scheduled_by === user.email;
        const isCounselor = !!user.isCounselor || !!user.is_counselor;
        const isMentorForStaffSession = (s.scheduler_role === 'ProgramStaff' || s.scheduler_role === 'Counselor') && user.role === 'Mentor';

        // Final Parity Visibility for Trash Icon
        const canTrash = isScheduler || isCounselor || isMentorForStaffSession;

        // JOIN LOCK LOGIC (Mentees only)
        // Link remains inactive until they click the Pre-Session survey link
        const isJoinLocked = isMentee && !(window.SURVEY_CLICKS && window.SURVEY_CLICKS[s.id]);
        const joinBtnStyle = isJoinLocked ? 'opacity:0.5; pointer-events:none; filter:grayscale(1);' : '';
        const lockNote = isJoinLocked ? `<div style="font-size:0.65rem; color:#ef4444; font-weight:800; margin-top:0.3rem;">LOCKED: Complete Pre-Survey first</div>` : '';

        // MENTEE PRE-SURVEY LINK (Required for unlock)
        const PRE_SURVEY_URL = "https://forms.office.com/Pages/ResponsePage.aspx?id=bvV_Bz_K30Cmp2nZVs8Lw9QMQpAEwXBPk9Yk-mW8Ba1UMTZXWjZIRE9ET1pWN05QVzcyUjhPSTZCRS4u";
        const preSurveyBtn = isMentee && isJoinLocked
            ? `<a href="${PRE_SURVEY_URL}" target="_blank" onclick="window.unlockSessionJoin('${s.id}')" class="btn-white" style="text-decoration:none; padding:0.6rem 1rem; border-radius:12px; font-size:0.75rem; border:1px solid #fce4ec; color:#e84393; font-weight:800;">1. Open Pre-Survey</a>`
            : '';

        const attribution = (s.scheduler_role === 'ProgramStaff' || s.scheduler_role === 'Counselor')
            ? `<div style="font-size: 0.7rem; color: #e84393; font-weight: 800; text-transform: uppercase; margin-top: 0.2rem;">Scheduled by Counselor ${s.scheduler_name || 'Staff'}</div>`
            : '';

        // Meeting Link Visualization
        let linkActionHtml = `<a href="${s.meeting_link}" target="_blank" class="btn-magenta" 
                               style="text-decoration:none; padding:0.6rem 1.2rem; border-radius:12px; ${joinBtnStyle}">Join Call</a>`;

        if (!isJoinLocked && s.meeting_link) {
            linkActionHtml = `
                <div style="display:flex; flex-direction:column; gap:0.5rem; align-items:center;">
                    <a href="${s.meeting_link}" target="_blank" class="btn-magenta" style="text-decoration:none; padding:0.8rem 1.5rem; border-radius:12px; font-weight:800; width:100%; text-align:center;">ENTER MEETING LINK</a>
                    <div style="font-size:0.65rem; color:#22c55e; font-weight:800;">✓ ACCESS UNLOCKED</div>
                </div>
            `;
        }

        return `<div style="background:white; border-radius:20px; padding:1.5rem; border:1.5px solid #fce4ec; margin-bottom:1rem; display:flex; justify-content:space-between; align-items:center;">
            <div style="flex: 1;">
                <div style="font-weight:800; color:#e84393;">${new Date(s.start_time).toLocaleString()}</div>
                <div style="font-size:0.8rem; color:#64748b; font-weight: 600;">${s.partner_name || 'Partner'}</div>
                ${attribution}
                ${lockNote}
            </div>
            <div style="display:flex; align-items:center; gap:0.5rem;">
                ${canTrash ? `
                <button onclick="window.trashSession('${s.id}', this)" data-action="trash-session" data-id="${s.id}" title="Cancel Session" style="background: #fff1f6; border: none; padding: 0.6rem; border-radius: 12px; cursor: pointer; color: #e84393; display: flex; align-items: center; justify-content: center;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                </button>` : ''}
                ${preSurveyBtn}
                ${linkActionHtml}
            </div>
        </div>`;
    }).join('') || `<div style="text-align:center; padding:3rem; color:#94a3b8;">No ${filter} sessions found.</div>`;
};

window.SURVEY_CLICKS = {};
window.unlockSessionJoin = function (sessionId) {
    window.SURVEY_CLICKS[sessionId] = true;
    window.renderSessions(window.DASH_DATA.sessions); // Re-render to unlock
};

window.renderStaffSessionsSelector = function () {
    const target = document.getElementById('counselor-session-controls');
    if (!target) return;
    const user = StarsSession.get()?.user;
    if (!user || (user.role !== 'ProgramStaff' && !user.isCounselor && !user.is_counselor)) return;

    const pairs = window.DASH_DATA?.pairs || [];

    // Grouping by Mentor (Screenshot Parity)
    const grouped = {};
    pairs.forEach(p => {
        const mName = p.mentor_name || 'Unassigned Mentor';
        if (!grouped[mName]) grouped[mName] = [];
        grouped[mName].push(p);
    });

    target.innerHTML = `<div class="section-title" style="margin-top: 3rem;">SCHEDULE A SESSION</div>` +
        Object.keys(grouped).map(mentor => {
            const pairsList = grouped[mentor].map(p => {
                const displayName = p.mentee_name || p.name || 'Mentee';
                const initials = displayName.trim().split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase() || 'M';
                return `
                <div class="mentee-card-yellow" onclick="window.openScheduleModal('${displayName}', '${p.pair_id}')" style="margin-bottom: 0.75rem; padding: 1.2rem 1.5rem; cursor: pointer; transition: 0.2s; border-radius: 20px;">
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <div style="background: #f7b731; color: white; width: 45px; height: 45px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.1rem; flex-shrink: 0;">${initials}</div>
                        <div>
                            <div style="font-weight: 800; color: #1e293b; font-size: 1.1rem;">${p.mentee_name}</div>
                            <div style="font-size: 0.8rem; color: #1e293b; font-weight: 600;">${p.mentee_email || p.email || ''}</div>
                            <div style="font-size: 0.75rem; color: #94a3b8; font-weight: 600; margin-top:0.1rem;">Mentee • Tap to schedule session</div>
                        </div>
                    </div>
                </div>`;
            }).join('');
            
            return `
                <div class="pair-label" style="color: #64748b; font-size: 0.75rem; font-weight: 800; margin-top: 1.5rem; margin-bottom: 0.5rem; text-transform: uppercase;">MENTOR: ${mentor}</div>
                ${pairsList}
            `;
        }).join('');
};
window.renderMentors = (mentors, targetId) => {
    const tid = targetId || 'mentors-grid';
    const g = document.getElementById(tid);
    if (!g) return;

    g.innerHTML = `<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1.5rem; width: 100%;">` +
        // Mentors: Horizontal layout with pink bubble avatar and status text
        mentors.map(m => `
        <div class="mentor-horizontal-card" onclick="window.viewMentorProfile('${m.email}')" 
             style="background: white; border: 1.5px solid #f1f5f9; border-radius: 20px; padding: 1.25rem 1.5rem; display: flex; align-items: center; justify-content: space-between; cursor: pointer; transition: 0.2s;">
            <div style="display: flex; align-items: center; gap: 1.25rem;">
                <div style="background: #e84393; color: white; width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.1rem; flex-shrink: 0;">${m.name.charAt(0)}${m.name.split(' ').length > 1 ? m.name.split(' ')[1].charAt(0) : ''}</div>
                <div>
                    <div style="font-weight: 800; color: #1e293b; font-size: 1.05rem; line-height: 1.2;">${m.name}</div>
                    <div style="font-size: 0.75rem; color: #94a3b8; font-weight: 700; margin-top: 0.15rem;">${m.email}</div>
                    <div style="font-size: 0.8rem; color: #e84393; font-weight: 700; margin-top: 0.15rem; text-decoration: none;">View Profile</div>
                </div>
            </div>
            <div style="color: #16a34a; font-weight: 800; font-size: 0.8rem; letter-spacing: 0.3px;">Available</div>
        </div>
    `).join('') + `</div>`;
};

window.filterMentors = () => {
    const q = document.getElementById('mentor-search-input')?.value.toLowerCase();
    const mentors = window.DASH_DATA?.mentors || [];
    const filtered = mentors.filter(m => m.name.toLowerCase().includes(q) || m.email.toLowerCase().includes(q));
    window.renderMentors(filtered, 'mentors-search-grid');
};
window.viewMentorProfile = (e) => {
    const m = (window.DASH_DATA?.mentors || []).find(x => x.email === e);
    if (!m) return;
    document.getElementById('modal-mentor-name').textContent = m.name;
    document.getElementById('modal-mentor-avatar').textContent = m.name.charAt(0);
    document.getElementById('modal-mentor-bio').textContent = m.bio || 'STARS Mentor';

    // Screenshot 2 Parity: Interests population
    const intCont = document.getElementById('modal-mentor-interests');
    if (intCont) {
        const ints = m.interests ? m.interests.split(',') : [];
        intCont.innerHTML = ints.map(i => `<span style="background:#fff1f6; color:#e84393; padding:0.4rem 0.8rem; border-radius:10px; font-size:0.75rem; font-weight:800; border:1px solid #fce4ec;">${i.trim()}</span>`).join('') || '<span style="color:#94a3b8; font-size:0.8rem;">General Interests</span>';
    }

    document.getElementById('mentor-profile-modal').style.display = 'flex';
};
window.renderResources = (r) => {
    const g = document.getElementById('resource-list-grid');
    if (!g) return;
    const user = StarsSession.get()?.user;

    // Hide upload for Mentees and Visitors (Restricted access)
    const uploadBtn = document.getElementById('btn-upload-resource');
    if (uploadBtn) uploadBtn.style.display = (user?.role === 'Mentee' || user?.role === 'Visitor' ? 'none' : 'flex');

    if (!r || r.length === 0) {
        g.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: #94a3b8; font-weight: 600;">No resources available.</div>`;
        return;
    }

    g.innerHTML = r.map(x => {
        const url = x.url && x.url !== 'null' ? x.url : '#';
        const description = x.description && x.description !== 'null' ? x.description : 'No description provided.';
        const hasUrl = url !== '#';
        const isOwner = (user?.email === x.uploaded_by) || (user?.role === 'ProgramStaff');

        return `<div class="resource-card" style="background:white; border-radius:24px; padding:1.75rem; border:1px solid #f1f5f9; display: flex; flex-direction: column; height: 100%; position: relative; transition: all 0.3s ease;">
            
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
                <div style="font-weight:800; color:#e84393; font-size: 1.15rem; flex: 1; padding-right: 2rem;">${x.name || 'Untitled Resource'}</div>
                
                ${isOwner ? `
                    <button onclick="window.trashResource('${x.id}', this)" title="Delete Resource" 
                        style="background: #fff1f6; border: none; padding: 0.5rem; border-radius: 10px; cursor: pointer; color: #e84393; display: flex; align-items: center; justify-content: center; position: absolute; right: 1.5rem; top: 1.5rem;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        </svg>
                    </button>
                ` : ''}
            </div>

            <p style="font-size:0.9rem; color: #64748b; line-height: 1.6; flex: 1;">${description}</p>
            
            <div style="display:flex; gap:0.5rem; margin-top:1.5rem;">
                ${hasUrl ? `
                    <button onclick="window.openResourcePreview('${url}', '${x.name}')" class="btn-magenta" style="flex:1; padding:0.75rem; border-radius:12px; font-weight:800; border:none; cursor:pointer; font-size: 0.9rem;">Preview</button>
                    <a href="${url}" target="_blank" class="btn-white" style="flex:1; text-align:center; text-decoration:none; padding:0.75rem; border-radius:12px; font-weight:800; border:1px solid #fce4ec; color:#e84393; font-size: 0.9rem;">Open Link</a>
                ` : `
                    <div style="flex: 1; text-align: center; color: #94a3b8; font-size: 0.85rem; font-style: italic; padding: 0.75rem; background: #f8fafc; border-radius: 12px; border: 1px dashed #e2e8f0;">Link Unavailable</div>
                `}
            </div>
        </div>`;
    }).join('');
};

window.openResourcePreview = (url, name) => {
    const modal = document.getElementById('resource-preview-modal');
    const iframe = document.getElementById('resource-preview-iframe');
    const title = document.getElementById('preview-filename');
    if (modal && iframe) {
        title.textContent = name || "Resource Preview";
        iframe.src = url;
        modal.style.display = 'flex';
    }
};
window.closeResourcePreview = () => {
    const modal = document.getElementById('resource-preview-modal');
    const iframe = document.getElementById('resource-preview-iframe');
    if (modal && iframe) {
        modal.style.display = 'none';
        iframe.src = '';
    }
};

// 8. RESOURCE MANAGEMENT (Functional Logic)
window.openResourceUpload = () => {
    const modal = document.getElementById('resource-upload-modal-overlay');
    if (modal) modal.style.display = 'flex';
};

window.closeResourceUpload = () => {
    const modal = document.getElementById('resource-upload-modal-overlay');
    if (modal) modal.style.display = 'none';
};

window.submitResource = async () => {
    const name = document.getElementById('res-upload-name')?.value;
    const url = document.getElementById('res-upload-url')?.value;
    const description = document.getElementById('res-upload-desc')?.value;

    if (!name || !url) {
        alert("Name and URL are required.");
        return;
    }

    try {
        const res = await fetch('/api/resources/upload', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${StarsSession.get().token}`
            },
            body: JSON.stringify({ name, url, description, category: 'General' })
        });

        if (res.ok) {
            window.closeResourceUpload();
            if (window.initDashboard) window.initDashboard(); // Refresh
        } else {
            alert("Upload failed. Please try again.");
        }
    } catch (e) {
        console.error("Resource upload error:", e);
        alert("A connectivity error occurred.");
    }
};



window.SURVEY_ALERTS_SHOWN = {};
window.checkSessionTimers = function () {
    const sessions = window.DASH_DATA?.sessions || [];
    const user = StarsSession.get()?.user;
    if (!sessions.length || !user) return;

    const now = new Date();
    const MENTEE_POST_LINK = "https://forms.office.com/Pages/ResponsePage.aspx?id=bvV_Bz_K30Cmp2nZVs8Lw9QMQpAEwXBPk9Yk-mW8Ba1UQjcyWjJDQUwxNTE3TEZNRDhVSzlZNEZJMS4u";
    const MENTOR_DURING_LINK = "https://forms.office.com/Pages/ResponsePage.aspx?id=bvV_Bz_K30Cmp2nZVs8Lw9QMQpAEwXBPk9Yk-mW8Ba1UMTZXWjZIRE9ET1pWN05QVzcyUjhPSTZCRS4u";
    const MENTOR_POST_LINK = "https://forms.office.com/Pages/ResponsePage.aspx?id=bvV_Bz_K30Cmp2nZVs8Lw9QMQpAEwXBPk9Yk-mW8Ba1UQjcyWjJDQUwxNTE3TEZNRDhVSzlZNEZJMS4u"; // Placeholder mentor post

    sessions.forEach(s => {
        const sTime = new Date(s.start_time);
        const diffMs = now - sTime;
        const diffMins = Math.floor(diffMs / 60000);

        // 1. Mentor During-Session (As soon as it starts)
        if (user.role === 'Mentor' && diffMins >= 0 && diffMins < 45) {
            if (!window.SURVEY_ALERTS_SHOWN[`during_${s.id}`]) {
                window.SURVEY_ALERTS_SHOWN[`during_${s.id}`] = true;
                window.triggerSurveyAlert("Session Started", "Please complete your 'During-Session' mentor survey now.", MENTOR_DURING_LINK);
            }
        }

        // 2. Mentee Post-Session (5 mins before it ends - session is 45 mins)
        if (user.role === 'Mentee' && diffMins >= 40 && diffMins < 45) {
            if (!window.SURVEY_ALERTS_SHOWN[`post_5min_${s.id}`]) {
                window.SURVEY_ALERTS_SHOWN[`post_5min_${s.id}`] = true;
                window.triggerSurveyAlert("Session Ending Soon", "Please complete your post-session mentee survey.", MENTEE_POST_LINK);
            }
        }

        // 3. Mentor Post-Session (As soon as it ends)
        if (user.role === 'Mentor' && diffMins >= 45 && diffMins < 50) {
            if (!window.SURVEY_ALERTS_SHOWN[`post_${s.id}`]) {
                window.SURVEY_ALERTS_SHOWN[`post_${s.id}`] = true;
                window.triggerSurveyAlert("Session Finished", "Please complete your final post-session evaluation.", MENTOR_POST_LINK);
            }
        }
    });
};

window.triggerSurveyAlert = function (title, msg, link) {
    // Inject a centered, stars-themed alert box
    const modal = document.createElement('div');
    modal.style = "position:fixed; top:0; left:0; width:100vw; height:100vh; background:rgba(0,0,0,0.6); z-index:99999; display:flex; align-items:center; justify-content:center; backdrop-filter:blur(5px);";
    modal.innerHTML = `
        <div style="background:white; padding:2.5rem; border-radius:24px; text-align:center; width:450px; box-shadow:0 25px 50px rgba(0,0,0,0.25); border:3px solid #fce4ec;">
            <div style="width:70px; height:70px; background:#fff1f6; color:#e84393; border-radius:20px; display:flex; align-items:center; justify-content:center; margin:0 auto 1.5rem auto;">
                <svg width="35" height="35" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
            </div>
            <h2 style="font-family:'Outfit', sans-serif; font-weight:800; color:#1e293b; margin-bottom:0.5rem;">${title}</h2>
            <p style="color:#64748b; margin-bottom:2rem; font-weight:500;">${msg}</p>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
                <button onclick="this.closest('div.parent').remove();" class="btn-white" style="padding:1rem; border-radius:12px; font-weight:800; border:1px solid #fce4ec; color:#e84393; cursor:pointer;">Dismiss</button>
                <a href="${link}" target="_blank" onclick="this.closest('div.parent').remove();" class="btn-magenta" style="padding:1rem; border-radius:12px; font-weight:800; text-decoration:none; text-align:center; display:block;">Open Survey</a>
            </div>
        </div>
    `;
    modal.className = 'parent';
    document.body.appendChild(modal);
};

// 9. DIAGNOSTIC INFRASTRUCTURE (API Heartbeat Monitor)
window.logAPI = (method, endpoint, status, message) => {
    const logs = document.getElementById('hb-logs');
    if (!logs) return;
    
    const entry = document.createElement('div');
    const color = status === 200 || status === 'success' ? '#10b981' : '#ef4444';
    entry.style = `padding: 0.5rem; margin-top: 0.5rem; border-left: 3px solid ${color}; background: #f8fafc; border-radius: 6px; font-family: monospace; font-size: 10px; color: #1e293b;`;
    entry.innerHTML = `
        <div style="font-weight: 800; display: flex; justify-content: space-between;">
            <span>${method} ${endpoint}</span>
            <span style="color: ${color}">${status}</span>
        </div>
        <div style="opacity: 0.7;">${message || ''}</div>
    `;
    logs.prepend(entry);
    if (logs.children.length > 5) logs.lastChild.remove();
};

window.initDiagnosticOverlay = () => {
    if (document.getElementById('stars-api-diagnostic')) return;
    const diag = document.createElement('div');
    diag.id = 'stars-api-diagnostic';
    
    const isMin = localStorage.getItem('stars_heartbeat_min') === 'true';
    
    diag.style = `position:fixed; bottom:20px; right:20px; ${isMin ? 'width:120px; height:32px;' : 'width:220px; max-height:300px;'} background:rgba(255,255,255,0.95); backdrop-filter:blur(10px); border:1px solid #e2e8f0; border-radius:12px; z-index:999999; padding:0.75rem; box-shadow:0 10px 15px -3px rgba(0,0,0,0.1); display:flex; flex-direction:column; overflow:hidden; transition: all 0.3s ease; cursor: pointer;`;
    
    diag.onclick = () => window.toggleDiagnostic();
    
    diag.innerHTML = `<div style="font-size:10px; font-weight:800; color:#94a3b8; text-transform:uppercase; letter-spacing:0.05em; display:flex; justify-content:space-between; align-items:center;">
        <span id="hb-text">${isMin ? 'API ONLINE' : 'API Heartbeat'}</span>
        <span id="hb-status" style="width:8px; height:8px; background:#10b981; border-radius:50%; display:inline-block;"></span>
    </div>
    <div id="hb-logs" style="display: ${isMin ? 'none' : 'block'};"></div>`;
    
    document.body.appendChild(diag);
    
    window.toggleDiagnostic = () => {
        const el = document.getElementById('stars-api-diagnostic');
        const logs = document.getElementById('hb-logs');
        const text = document.getElementById('hb-text');
        const min = el.style.width === '120px';
        
        if (min) {
            el.style.width = '220px'; el.style.height = 'auto'; el.style.maxHeight = '300px';
            logs.style.display = 'block'; text.innerText = 'API Heartbeat';
            localStorage.setItem('stars_heartbeat_min', 'false');
        } else {
            el.style.width = '120px'; el.style.height = '32px'; el.style.maxHeight = '32px';
            logs.style.display = 'none'; text.innerText = 'API ONLINE';
            localStorage.setItem('stars_heartbeat_min', 'true');
        }
    };

    if (window.starsPersistenceTimer) clearInterval(window.starsPersistenceTimer);
    window.starsPersistenceTimer = setInterval(() => {
        if (!document.getElementById('stars-api-diagnostic')) {
            window.initDiagnosticOverlay();
        }
    }, 2000);

    logAPI('BOOT', 'System Online', 200, 'v160.0 Full Master');
};

// Initialize Diagnostics and restore handlers
document.addEventListener('DOMContentLoaded', () => {
    // Heartbeat Monitor: Always initialize if session exists or on portal/staff page
    const checkDiag = () => {
        if (!document.getElementById('stars-api-diagnostic')) {
            const hasSession = !!StarsSession.get()?.token;
            const isPortal = window.location.hash.includes('staff') || window.location.hash.includes('dashboard') || window.location.hash.includes('portal') || window.location.pathname.includes('admin.html');
            if (hasSession || isPortal) {
                window.initDiagnosticOverlay();
            }
        }
    };
    
    setTimeout(checkDiag, 500);
    setInterval(checkDiag, 5000);
    
    // Global Privilege Guard for Whiteboard
    const observer = new MutationObserver(() => {
        const postBox = document.getElementById('whiteboard-input-card');
        if (postBox) {
            const user = StarsSession.get()?.user;
            if (user) {
                const role = (user.role || '').toLowerCase();
                const isStaff = role.includes('staff') || role.includes('counselor') || !!user.isCounselor || !!user.is_counselor;
                if (isStaff) {
                    postBox.style.setProperty('display', 'none', 'important');
                    console.log("WHITEBOARD_GUARD: Authoritatively hiding post box for staff role.");
                }
            }
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
});

window.handleFileSelect = (input) => {
    const file = input.files[0];
    const display = document.getElementById('selected-filename');
    if (file && display) {
        display.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
        display.style.color = '#e84393';
    }
};

window.submitResourceUpload = async () => {
    const name = document.getElementById('res-upload-name')?.value;
    const desc = document.getElementById('res-upload-desc')?.value;
    const category = document.getElementById('res-upload-category')?.value || 'General';
    const type = document.getElementById('res-upload-type')?.value || 'PDF';
    const fileInput = document.getElementById('res-file-input');
    const btn = document.getElementById('res-confirm-btn');

    if (!name || (!fileInput.files[0] && !document.getElementById('res-upload-url')?.value)) {
        alert("Please provide a name and select a document.");
        return;
    }

    if (btn) { btn.disabled = true; btn.textContent = 'Posting...'; }
    logAPI('UPLOAD', '/api/resources/upload', 0, 'PENDING');

    try {
        const formData = new FormData();
        formData.append('name', name);
        formData.append('description', desc || "");
        formData.append('category', category);
        formData.append('type', type);

        if (fileInput.files[0]) {
            formData.append('file', fileInput.files[0]);
        } else {
            const urlVal = document.getElementById('res-upload-url')?.value;
            if (urlVal) formData.append('url', urlVal);
        }

        const response = await fetch('/api/resources/upload', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${StarsSession.get().token}`
            },
            body: formData
        });

        // HARDENED HEARTBEAT: Log BEFORE parsing to capture HTML errors
        const text = await response.text();
        let data;
        try { data = JSON.parse(text); } catch (e) { data = { success: false, error: 'Malformed Server Response: ' + text.substring(0, 30) }; }
        
        logAPI('UPLOAD', '/api/resources/upload', response.status, data.success ? 'Success' : (data.error || 'Server error'));

        if (data.success) {
            alert("✓ Resource posted successfully!");
            if (window.closeResourceUpload) window.closeResourceUpload();
            if (window.renderResources) window.renderResources();
            else window.location.reload();
        } else {
            alert("❌ Upload failed: " + (data.error || "Server error"));
            if (btn) { btn.disabled = false; btn.textContent = "Confirm Upload"; }
        }
    } catch (error) {
        logAPI('UPLOAD', 'Connectivity Error', 500, 'FAILED');
        alert("❌ Upload failed. Check console.");
        if (btn) { btn.disabled = false; btn.textContent = "Confirm Upload"; }
    }
};

window.renderWhiteboard = async function() {
    const container = document.getElementById('whiteboard-notes-container');
    if (!container) return;
    
    container.innerHTML = '<div style="padding:2rem; text-align:center; color:#94a3b8;">Syncing with cloud whiteboard...</div>';
    
    try {
        const res = await fetch('/api/whiteboard', {
            headers: { 'Authorization': `Bearer ${StarsSession.get().token}` }
        });
        const notes = await res.json();
        
        if (notes.error || !Array.isArray(notes)) {
            container.innerHTML = `
                <div style="padding:4rem 2rem; text-align:center; background:#fff; border-radius:24px; border:2px dashed #f1f5f9;">
                    <p style="color:#e84393; font-weight:600; margin:0;">${notes.error || 'Unable to load notes.'}</p>
                </div>`;
            return;
        }

        if (notes.length === 0) {
            container.innerHTML = `
                <div style="padding:4rem 2rem; text-align:center; background:#fff; border-radius:24px; border:2px dashed #f1f5f9;">
                    <p style="color:#94a3b8; font-weight:600; margin:0;">No notes found. Create your first persistent note above!</p>
                </div>`;
            return;
        }

        const user = StarsSession.get().user;
        const role = user.role?.toLowerCase() || '';
        const isStaff = role.includes('staff') || role.includes('counselor') || !!user.isCounselor || !!user.is_counselor;

        // HIDE POST BOX FOR NON-MENTORS (Staff/Counselors see all, but don't post)
        const postBox = document.getElementById('whiteboard-input-card');
        if (postBox) {
            postBox.style.setProperty('display', isStaff ? 'none' : 'block', 'important');
        }

        container.innerHTML = notes.map(n => {
           const dateStr = n.timestamp ? new Date(n.timestamp).toLocaleDateString() : 'N/A';
           const timeStr = n.timestamp ? new Date(n.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '';
           return `
            <div class="resource-card" style="margin-bottom:1.5rem; background:white; padding:1.5rem; border-radius:20px; border:1.5px solid #f1f5f9; position:relative;">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:1rem;">
                    <span style="font-size:0.65rem; font-weight:800; color:var(--stars-magenta); text-transform:uppercase; background:#fff1f6; padding:0.4rem 0.8rem; border-radius:8px;">
                        ${n.category || 'Session Note'}
                    </span>
                    <span style="font-size:0.7rem; color:#94a3b8; font-weight:600;">
                        ${dateStr} ${timeStr}
                    </span>
                </div>
                <p style="font-size:1rem; color:#1e293b; line-height:1.6; font-weight:500; margin-bottom:1rem;">${n.content}</p>
                <div style="border-top:1px solid #f8fafc; padding-top:1rem; display:flex; justify-content:space-between; align-items:center;">
                    <div style="font-size:0.75rem; color:#64748b; font-weight:700;">
                        Author: <span style="color:var(--stars-magenta)">${isStaff ? (n.mentor_name ? `${n.mentor_name} (${n.created_by})` : n.created_by) : 'Stored Privately'}</span>
                    </div>
                </div>
            </div>
        `}).join('');
    } catch (e) {
        container.innerHTML = `<p style="color:#e84393; text-align:center;">Connectivity Error: ${e.message}</p>`;
    }
};

window.saveWhiteboardNote = async function() {
    const content = document.getElementById('whiteboard-input')?.value;
    const btn = document.getElementById('save-whiteboard-btn');
    if (!content) { alert("Please enter some content for your note."); return; }
    
    if (btn) { btn.disabled = true; btn.textContent = 'Saving...'; }
    
    try {
        const res = await fetch('/api/whiteboard', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${StarsSession.get().token}`
            },
            body: JSON.stringify({ content, category: 'General' })
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('whiteboard-input').value = '';
            window.renderWhiteboard();
        } else {
            alert("❌ Save failed: " + (data.error || "Server error"));
        }
    } catch (e) {
        alert("❌ Connectivity Error: " + e.message);
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Post Note'; }
    }
};
