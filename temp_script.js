        /* --- STARS MASTER AUTHORITY v3.7 --- */
        const STARS_DEBUG = true;
        const log = (msg) => STARS_DEBUG && console.log(`[STARS]: ${msg}`);

        // 1. Session Engine (Authoritative Cross-Storage)
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

        // 2. Navigation & UI View Switching
        window.showAuthForm = function (id) {
            log(`Switching view to: ${id}`);
            const gateway = document.getElementById('auth-gateway');
            const app = document.getElementById('app-container');
            const menu = document.getElementById('auth-menu');
            const forms = ['login', 'register', 'staff-verify', 'staff-activate', 'staff-login', 'visitor'];

            if (id === 'dash') {
                if (gateway) gateway.style.display = 'none';
                if (app) app.style.display = 'flex';
                initDashboard();
                return;
            }

            if (gateway) gateway.style.display = 'flex';
            if (app) app.style.display = 'none';
            if (menu) menu.style.display = (id === 'menu' ? 'grid' : 'none');

            forms.forEach(f => {
                const el = document.getElementById(f + '-form');
                if (el) el.style.display = (f === id ? 'flex' : 'none');
            });

            // Reset visitor OTP state if entering visitor form
            if (id === 'visitor') {
                const otpBlock = document.getElementById('visitor-otp-block');
                const submitBtn = document.getElementById('visitor-submit-btn');
                if (otpBlock) otpBlock.style.display = 'none';
                if (submitBtn) submitBtn.style.display = 'block';
            }
        };

        window.navigateTo = function (id) { window.MapsTo(id); };
        window.switchPage = function (pageId, el) { window.showPage(pageId, el); };

        // 3. Authentication Handlers
        window.handleAuthSubmit = async function (event, type) {
            if (event) { event.preventDefault(); event.stopPropagation(); }
            log(`Auth Submit: ${type}`);
            const errorEl = document.getElementById(type + '-error') || document.getElementById('staff-error');
            if (errorEl) { errorEl.textContent = ''; errorEl.style.display = 'none'; }

            try {
                let payload = {};
                let endpoint = (type === 'register' ? 'register' : 'login');

                if (type === 'login') {
                    payload = {
                        email: document.getElementById('login-email').value,
                        password: document.getElementById('login-password').value
                    };
                } else if (type === 'register') {
                    payload = {
                        email: document.getElementById('register-email').value,
                        password: document.getElementById('register-password').value,
                        firstName: document.getElementById('register-fname').value,
                        lastName: document.getElementById('register-lname').value,
                        role: document.getElementById('register-role').value
                    };
                } else if (type === 'staff-login' || type === 'staff') {
                    payload = {
                        email: document.getElementById('staff-email').value,
                        password: document.getElementById('staff-password').value
                    };
                    endpoint = 'login';
                } else if (type === 'visitor') {
                    // Step 1: Request OTP
                    const visitorEmail = document.getElementById('visitor-email').value;
                    const res = await fetch('http://localhost:8000/api/visitor', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            email: visitorEmail,
                            firstName: document.getElementById('visitor-fname').value,
                            lastName: document.getElementById('visitor-lname').value
                        })
                    });
                    if (!res.ok) throw new Error("Failed to request code.");

                    document.getElementById('visitor-otp-block').style.display = 'block';
                    document.getElementById('visitor-submit-btn').style.display = 'none';
                    return false;
                }

                const response = await fetch(`http://localhost:8000/api/${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const result = await response.json();
                if (!response.ok) throw new Error(result.error || "Authentication failed");

                StarsSession.save(result.token, result.user);
                showAuthForm('dash');
            } catch (err) {
                if (errorEl) { errorEl.textContent = err.message; errorEl.style.display = 'block'; }
            }
            return false;
        };

        window.verifyVisitorOTP = async function () {
            const email = document.getElementById('visitor-email').value;
            const code = document.getElementById('visitor-otp').value;
            const errorEl = document.getElementById('visitor-code-error');
            if (code.length < 6) { alert("Please enter the full 6-digit code."); return; }

            try {
                const res = await fetch('http://localhost:8000/api/visitor/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, code })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error);

                StarsSession.save(data.token, data.user);
                showAuthForm('dash');
            } catch (e) {
                if (errorEl) { errorEl.textContent = e.message; errorEl.style.display = 'block'; }
            }
        };

        window.handleStaffVerify = async function (event) {
            if (event) event.preventDefault();
            const email = document.getElementById('staff-verify-email').value;
            const errorEl = document.getElementById('staff-verify-error');
            try {
                const res = await fetch('http://localhost:8000/api/verify-staff', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error);
                if (data.is_activated) {
                    if (document.getElementById('staff-email')) document.getElementById('staff-email').value = email;
                    showAuthForm('staff-login');
                } else {
                    window.STAFF_ACTIVATING_EMAIL = email;
                    if (document.getElementById('staff-activate-title')) document.getElementById('staff-activate-title').textContent = `Set Password for ${data.first_name || 'Staff'}`;
                    showAuthForm('staff-activate');
                }
            } catch (e) { if (errorEl) { errorEl.textContent = e.message; errorEl.style.display = 'block'; } }
        };

        window.handleStaffActivate = async function (event) {
            if (event) event.preventDefault();
            const pass = document.getElementById('staff-activate-pass').value;
            const confirm = document.getElementById('staff-activate-confirm').value;
            if (pass !== confirm) { alert("Passwords do not match."); return; }
            try {
                const res = await fetch('http://localhost:8000/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: window.STAFF_ACTIVATING_EMAIL, password: pass })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error);
                StarsSession.save(data.token, data.user);
                showAuthForm('dash');
            } catch (err) { alert(err.message); }
        };

        // 4. Dashboard Features
        async function initDashboard() {
            log("Initializing Dashboard...");
            try {
                // Ensure Supabase is ready and session is restored
                await window.STARS_AUTHORITY;
                const session = StarsSession.get();
                if (!session) {
                    log("No session found, redirecting to menu.");
                    showAuthForm('menu');
                    return;
                }
                const { token, user } = session;

                // State Gate: If we have a hash but it's auth related, reset to dashboard
                const authHashes = ['#menu', '#login', '#staff-verify', '#visitor-otp'];
                if (authHashes.includes(window.location.hash)) {
                    window.location.hash = '#dashboard';
                }
                // Counselor Theme Application (Restoration Parity)
                const isCounselor = !!user.is_counselor || !!user.isCounselor || user.role === 'ProgramStaff';
                log(`Counselor Check: ${isCounselor}`);
                document.body.classList.toggle('counselor-theme', isCounselor);

                // Basic UI Sync
                const fullName = user.firstName && user.lastName ? `${user.firstName} ${user.lastName}` : (user.name || 'User');
                if (document.getElementById('profile-name')) document.getElementById('profile-name').textContent = fullName;
                if (document.getElementById('profile-initial')) document.getElementById('profile-initial').textContent = (user.firstName || user.name || 'U').charAt(0).toUpperCase();

                const res = await fetch('http://localhost:8000/api/dashboard', { headers: { 'Authorization': `Bearer ${token}` } });
                if (!res.ok) throw new Error("Portal synchronization failed.");
                const data = await res.json();
                window.DASH_DATA = data;

                // Authoritative System Health: Hide error banners on sync
                const errorBanner = document.getElementById('system-error');
                if (errorBanner) errorBanner.style.display = 'none';

                // 4. Populate Sidebar based on role (Screenshot 2 Parity)
                const sidebar = document.getElementById('dynamic-sidebar');
                if (sidebar) {
                    const user = StarsSession.get()?.user;
                    const items = [
                        { id: 'dashboard', label: 'Dashboard' },
                        { id: 'mentors', label: 'Find Mentors', hideForMentees: true },
                        { id: 'messages', label: 'Messages', restrictedToCounselorForStaff: true },
                        { id: 'survey', label: 'Survey Responses Center', hideForMentees: true, restrictedToCounselorForStaff: true },
                        { id: 'sessions', label: 'My Sessions', restrictedToCounselorForStaff: true },
                        { id: 'resources', label: 'Library' },
                        { id: 'settings', label: 'Settings' }
                    ];

                    let navItems = '';
                    items.forEach(item => {
                        if (item.hideForMentees && user.role === 'Mentee') return;
                        if (item.restrictedToCounselorForStaff && user.role === 'ProgramStaff' && !isCounselor) return;
                        navItems += `<li class="sidebar-btn ${item.id === 'dashboard' ? 'active' : ''}" data-page="${item.id}">${item.label}</li>`;
                    });

                    // Add Management Console for Counselors (Screenshot Parity)
                    if (isCounselor) {
                        navItems += `<li class="sidebar-btn" onclick="window.location.href='admin.html'" style="color: var(--magenta); font-weight: 800; border-left: 4px solid var(--magenta); background: #fff1f6;">Management Console</li>`;
                    }

                    navItems += `<div style="height: 1px; background: #f1f5f9; margin: 1.5rem 2rem;"></div>`;
                    navItems += `<li class="sidebar-btn" data-page="profile">My Profile</li>`;
                    navItems += `<li class="sidebar-btn" data-page="settings">Settings</li>`;
                    navItems += `<li class="sidebar-btn" data-page="contact">Contact Us</li>`;

                    sidebar.innerHTML = navItems;
                }

                renderDashboard(data);
                renderMentors(data.mentors || []);
                
                // Authoritative Tab Initialization
                window.SESSION_TAB = 'Pending';
                renderSessions(data.sessions || []);
                
                renderMessages(data.messages || []);
                renderResources(data.resources || []);

                showPage('dashboard');
                const loader = document.getElementById('system-loader');
                if (loader) loader.classList.add('hidden');
            } catch (e) {
                log(`Dashboard init fail: ${e.message}`);
                const loader = document.getElementById('system-loader');
                if (loader) loader.classList.add('hidden');
            }
        }

        function renderDashboard(data) {
            const welcome = document.getElementById('dash-welcome-title');
            if (welcome) welcome.textContent = `Welcome to STARS Institute, ${StarsSession.get()?.user?.firstName || 'User'}! 👋`;
        }

        window.renderSessions = function (sessions) {
            const container = document.getElementById('sessions-list-container');
            if (!container) return;
            
            const currentUser = StarsSession.get()?.user;
            const now = new Date();
            const tab = window.SESSION_TAB || 'Pending';

            // 1. Unified Filtering Logic
            const categorized = sessions.reduce((acc, s) => {
                const sDate = new Date(s.start_time);
                if (sDate < now) {
                    acc.Past.push(s);
                } else if (s.status === 'Pending') {
                    acc.Pending.push(s);
                } else {
                    acc.Upcoming.push(s);
                }
                return acc;
            }, { Pending: [], Upcoming: [], Past: [] });

            // 2. Update Tab Counts (Screenshot 1 parity)
            document.querySelectorAll('.status-tab').forEach(btn => {
                const label = btn.textContent.split(' (')[0];
                btn.innerHTML = `${label} (${categorized[label]?.length || 0})`;
                btn.classList.toggle('active', label === tab);
            });

            const filtered = categorized[tab];

            if (!filtered || !filtered.length) {
                container.innerHTML = `
                    <div style="grid-column: 1/-1; background: #fff1f6; border: 2px dashed #fbcfe8; border-radius: 24px; padding: 5rem; text-align: center;">
                        <p style="color: #94a3b8; margin-bottom: 2rem; font-size: 1.1rem;">No ${tab.toLowerCase()} sessions</p>
                        <button class="btn-magenta" onclick="window.openScheduleModal()" style="padding: 1rem 2rem; border-radius: 12px; font-weight: 800;">
                            + Schedule A Session
                        </button>
                    </div>
                `;
                return;
            }

            container.innerHTML = `
                <div style="background: #fff1f6; border: 2px dashed #fbcfe8; border-radius: 24px; padding: 2.5rem; display: flex; flex-direction: column; gap: 1.5rem;">
                    ${filtered.map(s => {
                        const isReceiver = s.scheduled_by.toLowerCase() !== currentUser?.email.toLowerCase();
                        const showAccept = tab === 'Pending' && (isReceiver || currentUser?.isCounselor);
                        
                        return `
                            <div style="background: white; border-radius: 16px; padding: 1.5rem 2rem; border: 1px solid #fce4ec; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 15px rgba(232, 67, 147, 0.05);">
                                <div>
                                    <h3 style="margin: 0; color: #e84393; font-size: 1.4rem; font-weight: 800; font-family: 'Outfit';">
                                        ${new Date(s.start_time).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                    </h3>
                                    <p style="margin: 0.25rem 0 0 0; color: #64748b; font-size: 0.95rem; font-weight: 500;">
                                        ${tab === 'Pending' ? (isReceiver ? 'Accept this session request' : `Waiting for ${s.partner_name} to accept`) : 'Virtual Session Room'}
                                    </p>
                                </div>
                                <div style="display: flex; align-items: center; gap: 1rem;">
                                    ${showAccept ? `
                                        <button onclick="window.acceptSession('${s.id}')" class="btn-magenta" style="padding: 0.8rem 2rem; border-radius: 12px; font-weight: 800; font-size: 0.9rem; background: #16a34a; border-color: #16a34a;">Accept Request</button>
                                    ` : `
                                        <a href="${s.link || '#'}" target="_blank" class="btn-magenta" style="padding: 0.8rem 2rem; border-radius: 12px; text-decoration: none; font-weight: 800; font-size: 0.9rem; ${tab === 'Pending' ? 'opacity: 0.5; pointer-events: none;' : ''}">Join Call</a>
                                    `}
                                    
                                    ${(s.scheduled_by.toLowerCase() === currentUser?.email.toLowerCase() || currentUser?.isCounselor) ? `
                                        <button onclick="window.trashSession('${s.id}')" style="background: none; border: none; color: #ef4444; cursor: pointer; padding: 0.5rem; transition: all 0.2s;" onmouseover="this.style.transform='scale(1.2)'" onmouseout="this.style.transform='scale(1)'">
                                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                                        </button>
                                    ` : ''}
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            `;
        };

        window.switchSessionsTab = function (tab, btn) {
            window.SESSION_TAB = tab;
            renderSessions(window.DASH_DATA?.sessions || []);
        };

        window.acceptSession = async function (id) {
            const { token } = StarsSession.get();
            try {
                const res = await fetch('http://localhost:8000/api/sessions/accept', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                    body: JSON.stringify({ id })
                });
                if (!res.ok) throw new Error("Acceptance failed.");
                initDashboard();
            } catch (e) { alert(e.message); }
        };

        window.trashSession = function (id) {
            window.showStarsConfirm("Cancel Session?", "Are you sure you want to cancel this mentorship session? This cannot be undone.", async () => {
                const { token } = StarsSession.get();
                try {
                    const res = await fetch(`http://localhost:8000/api/sessions/${id}`, {
                        method: 'DELETE',
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.error);
                    initDashboard(); // Refresh
                } catch (e) { alert(e.message); }
        };

        window.renderMentors = function (mentors) {
            const grids = [
                document.getElementById('mentors-grid'),
                document.getElementById('mentors-search-grid'),
                document.getElementById('dash-mentors-list-container')
            ].filter(g => g !== null);
            
            if (!grids.length) return;
            const session = StarsSession.get();
            const user = session?.user;
            const pairs = window.DASH_DATA?.pairs || [];

            // Update badge count
            const badge = document.getElementById('mentor-count-badge');
            if (badge) badge.textContent = mentors.length;

            let menteeCardsHtml = '';
            // 1. If user is a Mentor, show their specific Mentee(s) at the top (Yellow Cards)
            if (user.role === 'Mentor') {
                const myMentees = pairs.filter(p => p.type === 'Mentee');
                const menteeGrid = document.getElementById('mentors-pair-top-grid');
                const menteeSection = document.getElementById('mentors-assigned-top');
                
                if (myMentees.length > 0) {
                    if (menteeSection) menteeSection.style.display = 'block';
                    menteeCardsHtml = myMentees.map(m => `
                        <div class="mentee-card-yellow" style="grid-column: 1/-1; display: flex; align-items: center; justify-content: space-between; padding: 1.5rem 2.5rem; border-radius: 28px; margin-bottom: 2rem;">
                            <div style="display: flex; align-items: center; gap: 2rem;">
                                <div class="avatar" style="width: 60px; height: 60px; background: #fbbf24; color: white; font-weight: 800; font-size: 1.5rem;">${m.name.charAt(0)}</div>
                                <div>
                                    <div style="font-size: 0.75rem; color: #d97706; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;">YOUR MENTEE</div>
                                    <h3 style="margin: 0; font-size: 1.8rem; color: #1e293b; font-weight: 800;">${m.name}</h3>
                                </div>
                            </div>
                            <div style="display: flex; gap: 1rem;">
                                <button class="btn" style="background: white; color: var(--stars-magenta); border: 1.5px solid #fce4ec; border-radius: 14px; padding: 0.8rem 1.5rem; font-weight: 800; display: flex; align-items: center; gap: 0.5rem;" onclick="showPage('messaging'); window.loadChat('${m.pair_id}', '${m.name}')">
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 1 1-7.6-11.7 8.38 8.38 0 0 1 3.8.9L21 3.5l-1.5 5.5Z"/></svg>
                                    Chat
                                </button>
                                <button class="btn-magenta" style="border-radius: 14px; padding: 0.8rem 1.5rem; font-weight: 800; display: flex; align-items: center; gap: 0.5rem;" onclick="window.openScheduleModal('${m.name}', '${m.pair_id}')">
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                                    Schedule
                                </button>
                            </div>
                        </div>
                    `).join('');
                    if (menteeGrid) menteeGrid.innerHTML = menteeCardsHtml;
                } else {
                    if (menteeSection) menteeSection.style.display = 'none';
                }
            }

            // 2. Show the rest of the mentors
            let mentorsHtml = mentors.map(m => {
                const initials = m.name.split(' ').map(n => n.charAt(0)).join('').toUpperCase();
                const isPaired = m.is_paired;
                return `
                    <div class="mentor-card-ivory" onclick="window.viewMentorProfile('${m.email}')">
                        <div class="mentor-initials-pink">${initials}</div>
                        <div>
                            <h3 class="mentor-name-pink">${m.name}</h3>
                            <a href="#" class="profile-link" onclick="event.stopPropagation(); window.viewMentorProfile('${m.email}')">View Profile</a>
                        </div>
                        <div class="status-indicator ${isPaired ? 'paired' : 'available'}">
                            ${isPaired ? 'Paired' : 'Available'}
                        </div>
                    </div>
                `;
            }).join('');

            grids.forEach(g => {
                if (g.id === 'dash-mentors-list-container' || g.id === 'mentors-grid' || g.id === 'mentors-search-grid') {
                     // Prepended for Dashboard, and also for search grid if we want them inside the grid itself
                     // Note: mentors-assigned-top handles it for the specific FIND MENTORS page layout
                     if (g.id === 'mentors-search-grid') {
                         g.innerHTML = mentorsHtml;
                     } else {
                         g.innerHTML = menteeCardsHtml + mentorsHtml;
                     }
                } else {
                     g.innerHTML = mentorsHtml;
                }
            });
        };

        window.viewMentorProfile = function(email) {
            const m = (window.DASH_DATA?.mentors || []).find(x => x.email === email);
            if (!m) return;
            
            document.getElementById('modal-mentor-name').textContent = m.name;
            document.getElementById('modal-mentor-avatar').textContent = m.name.charAt(0);
            document.getElementById('modal-mentor-bio').textContent = m.bio || "No biography provided yet.";
            
            const interestsBox = document.getElementById('modal-mentor-interests');
            if (interestsBox) {
                const tags = (m.interests || "Mentorship, Leadership").split(',');
                interestsBox.innerHTML = tags.map(t => `<span style="background: var(--pink-light); color: var(--magenta); padding: 0.3rem 0.8rem; border-radius: 8px; font-size: 0.75rem; font-weight: 700;">${t.trim()}</span>`).join('');
            }
            
            document.getElementById('mentor-profile-modal').style.display = 'flex';
        };

        window.renderMessages = function (msgs) {
            const section = document.getElementById('messages');
            if (!section) return;
            const user = StarsSession.get()?.user;
            const pairs = window.DASH_DATA?.pairs || [];

            // 1. High-Fidelity Header Restoration (Screenshot 3)
            let html = `
                <div class="message-header-light">
                    <div>
                        <h1 style="color: var(--stars-magenta); margin: 0 0 0.25rem 0; font-size: 2.2rem; font-weight: 800;">Messages</h1>
                        <p style="color: #64748b; margin: 0; font-size: 1rem; font-weight: 500;">Connect with your mentors and mentees</p>
                    </div>
                    <img src="assets/logo.png" style="width: 60px; height: 60px; object-fit: contain;">
                </div>

                <div class="message-banner-solid">
                    <div style="background: rgba(255,255,255,0.2); width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center;">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="white" stroke="white" stroke-width="0.5"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                    </div>
                    <div>
                        <h2 style="margin: 0; font-size: 1.15rem; font-weight: 700;">Messages</h2>
                        <p style="margin: 0.1rem 0 0 0; font-size: 0.85rem; opacity: 0.9;">Select a mentor-mentee conversation to view</p>
                    </div>
                </div>

                <div id="message-selector-container" style="max-height: 500px; overflow-y: auto; padding-right: 0.5rem;">
            `;

            if (user.role === 'ProgramStaff' || user.isCounselor) {
                // Group by Mentor
                const mentorGroups = {};
                pairs.forEach(p => {
                    const nameParts = (p.name || '').split(' <-> ');
                    const mentorName = p.mentor_name || (nameParts.length > 0 ? nameParts[0] : 'Unknown Mentor');
                    if (!mentorGroups[mentorName]) mentorGroups[mentorName] = [];
                    mentorGroups[mentorName].push(p);
                });

                Object.keys(mentorGroups).sort().forEach(mentor => {
                    html += `<div class="pair-label" style="margin: 2rem 0 1rem 0; color: #94a3b8; font-size: 0.8rem; letter-spacing: 0.1em;">MENTOR: ${mentor.toUpperCase()}</div>`;
                    mentorGroups[mentor].forEach(p => {
                        const nameParts = (p.name || '').split(' <-> ');
                        const menteeName = p.mentee_name || (nameParts.length > 1 ? nameParts[1] : 'Unknown Mentee');
                        html += `
                            <div class="message-card-premium">
                                <div class="avatar" style="width: 80px; height: 80px; background: var(--stars-magenta); color: white; font-size: 2rem; font-weight: 800; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">${menteeName.charAt(0)}</div>
                                <div>
                                    <div class="card-label-grey">YOUR MENTEE</div>
                                    <h3 class="card-name-magenta">${menteeName}</h3>
                                </div>
                                <div class="card-actions-vertical">
                                    <button class="btn-card-action primary" onclick="window.loadChat('${p.pair_id}', '${menteeName}')">
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                                        Chat
                                    </button>
                                    <button class="btn-card-action secondary" onclick="window.showPage('sessions'); setTimeout(() => { if(window.selectMentee) window.selectMentee('${menteeName}'); }, 100);">
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                                        Sessions
                                    </button>
                                </div>
                            </div>
                        `;
                    });
                });
            } else {
                // Mentors/Mentees see their relative partners - CLICKABLE CARD, NO BUTTONS
                pairs.forEach(p => {
                    const label = (user.role === 'Mentor' ? 'YOUR MENTEE' : 'YOUR MENTOR');
                    html += `
                        <div class="message-card-premium" onclick="window.loadChat('${p.pair_id}', '${p.name}')" style="cursor: pointer;">
                            <div class="avatar" style="width: 80px; height: 80px; background: var(--stars-magenta); color: white; font-size: 2rem; font-weight: 800; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">${p.name.charAt(0)}</div>
                            <div>
                                <div class="card-label-grey">${label}</div>
                                <h3 class="card-name-magenta">${p.name}</h3>
                            </div>
                        </div>
                    `;
                });
            }

            html += `</div>`; // End selector

            // 2. Chat Area (Hidden until selected)
            html += `
                <div id="active-chat-container" style="display: none; height: 600px; flex-direction: column; background: white; border-radius: 24px; overflow: hidden; border: 1.5px solid #f1f5f9; margin-top: 2rem;">
                    <div id="general-chat-header" style="background: var(--stars-magenta); padding: 1.25rem 2rem; color: white; display: flex; align-items: center; gap: 1rem;">
                        <button onclick="document.getElementById('active-chat-container').style.display='none'; document.getElementById('message-selector-container').style.display='block';" style="background: none; border: none; color: white; cursor: pointer; display: flex; align-items: center;"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"></polyline></svg></button>
                        <div id="chat-header-avatar" class="avatar" style="width: 40px; height: 40px; background: rgba(255,255,255,0.2); font-size: 1rem; border: none;">?</div>
                        <div>
                            <h2 id="chat-header-name" style="margin: 0; font-size: 1rem; font-weight: 700;">Chat</h2>
                            <p id="chat-header-subtitle" style="margin: 0; font-size: 0.7rem; opacity: 0.8;">Active Session</p>
                        </div>
                    </div>
                    <div class="chat-body" id="chat-body-content" style="flex: 1; padding: 2rem; overflow-y: auto; background: #fafafa; display: flex; flex-direction: column; gap: 1rem;"></div>
                    <div class="chat-input-area" style="padding: 1.25rem 2rem; background: white; border-top: 1px solid #f1f5f9; display: flex; gap: 1rem; align-items: center;">
                        <input type="text" id="chat-input" placeholder="Type your message here..." style="flex: 1; border: 1.5px solid #f1f5f9; border-radius: 12px; padding: 0.9rem 1.25rem; outline: none; font-family: inherit;">
                        <button class="btn-magenta" onclick="window.submitMessage(event)" style="padding: 0.8rem 1.5rem; border-radius: 12px;">Send</button>
                    </div>
                </div>
            `;

            section.innerHTML = `
                <div class="page-inner" style="max-width: 800px; margin: 0 auto; padding-bottom: 5rem;">
                    ${html}
                </div>
            `;
            // AUTO-OPEN CHAT for Mentees and Mentors with 1 partner
            if (pairs.length === 1 && (user.role === 'Mentee' || user.role === 'Mentor')) {
                setTimeout(() => {
                    const p = pairs[0];
                    const partnerName = p.name || (user.role === 'Mentor' ? p.mentee_name : p.mentor_name);
                    window.loadChat(p.pair_id, partnerName);
                }, 50);
            }
        };

        window.loadChat = function (pairId, name) {
            window.CURRENT_CHAT_PAIR = pairId;
            document.getElementById('message-selector-container').style.display = 'none';
            document.getElementById('active-chat-container').style.display = 'flex';
            document.getElementById('chat-header-name').textContent = name;
            document.getElementById('chat-header-avatar').textContent = name.charAt(0);
            window.syncChat();
        };

        window.syncChat = async function () {
            if (!window.CURRENT_CHAT_PAIR) return;
            const res = await fetch(`http://localhost:8000/api/messages?pair_id=${window.CURRENT_CHAT_PAIR}`, {
                headers: { 'Authorization': `Bearer ${StarsSession.get().token}` }
            });
            const msgs = await res.json();
            const body = document.getElementById('chat-body-content');
            if (body) {
                const user = StarsSession.get().user;
                body.innerHTML = msgs.map(m => `
                    <div style="align-self: ${m.sender === user.email ? 'flex-end' : 'flex-start'}; max-width: 80%; background: ${m.sender === user.email ? 'var(--stars-magenta)' : 'white'}; color: ${m.sender === user.email ? 'white' : '#1e293b'}; padding: 0.8rem 1.2rem; border-radius: 18px; border: ${m.sender === user.email ? 'none' : '1.5px solid #f1f5f9'}; box-shadow: 0 2px 5px rgba(0,0,0,0.02);">
                        <div style="font-size: 0.85rem; line-height: 1.4;">${m.message}</div>
                        <div style="font-size: 0.6rem; margin-top: 0.3rem; opacity: 0.6; text-align: right;">${m.timestamp.split(' ')[1]}</div>
                    </div>
                `).join('');
                body.scrollTop = body.scrollHeight;
            }
        };

        window.submitMessage = async function (event) {
            const input = document.getElementById('chat-input');
            const text = input.value;
            if (!text || !window.CURRENT_CHAT_PAIR) return;
            const res = await fetch('http://localhost:8000/api/messages', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${StarsSession.get().token}` },
                body: JSON.stringify({ pair_id: window.CURRENT_CHAT_PAIR, message: text })
            });
            if (res.ok) {
                input.value = '';
                window.syncChat();
            }
        };

        window.renderResources = function (resources) {
            const container = document.getElementById('resources-grid');
            if (!container) return;
            if (!resources || !resources.length) {
                container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: #94a3b8;">No resources shared yet.</div>';
                return;
            }
            container.innerHTML = resources.map(r => `
                <div class="resource-card" style="background: white; border-radius: 20px; padding: 1.5rem; border: 1.5px solid #f1f5f9; position: relative; transition: 0.2s;">
                    <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;">
                        <div style="width: 40px; height: 40px; border-radius: 10px; background: #fff5f8; color: #e84393; display: flex; align-items: center; justify-content: center;">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                        </div>
                        <div>
                            <span style="font-size: 0.65rem; font-weight: 800; color: #e84393; text-transform: uppercase; letter-spacing: 0.05em;">${r.category || 'General'}</span>
                            <h4 style="margin: 0; font-size: 0.95rem; color: #1e293b; font-weight: 700;">${r.name}</h4>
                        </div>
                    </div>
                    <p style="margin: 0 0 1.5rem 0; color: #64748b; font-size: 0.8rem; line-height: 1.5; height: 2.4rem; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;">${r.description || 'No description provided.'}</p>
                    <a href="${r.url || '#'}" target="_blank" class="btn-magenta" style="display: block; text-align: center; text-decoration: none; padding: 0.6rem; border-radius: 10px; font-weight: 700; font-size: 0.8rem;">View Resource</a>
                </div>
            `).join('');
        };

        // Scheduling Logic
        window.openScheduleModal = function (name, pairId) {
            const pairs = window.DASH_DATA?.pairs || [];
            if (!name) {
                // If called without arguments (e.g. from banner), try to auto-select if user has 1 pair
                if (pairs.length === 1) {
                    name = pairs[0].name;
                    pairId = pairs[0].pair_id;
                } else if (pairs.length > 1) {
                    alert("Please select a mentee/mentor from your list first or use the 'My Sessions' page to select a partner.");
                    return;
                } else if (pairs.length === 0) {
                    alert("You don't have any assigned pairings yet.");
                    return;
                }
            }

            document.getElementById('schedule-partner-name').textContent = name;
            document.getElementById('final-schedule-btn').onclick = () => window.submitSchedule(pairId);
            document.getElementById('schedule-modal').style.display = 'flex';
            window.switchScheduleStep(1);
            window.updateCalendar();
        };

        window.openResourceUpload = function () {
            const overlay = document.getElementById('resource-upload-modal-overlay');
            if (overlay) overlay.style.display = 'flex';
        };

        window.closeScheduleModal = function () {
            document.getElementById('schedule-modal-overlay').style.display = 'none';
        };

        window.updateCalendar = function () {
            const calendarDays = document.getElementById('calendar-days');
            if (!calendarDays) return;
            calendarDays.innerHTML = '';
            const now = new Date();
            const year = now.getFullYear();
            const month = now.getMonth();
            const daysInMonth = new Date(year, month + 1, 0).getDate();
            for (let d = 1; d <= daysInMonth; d++) {
                const dayEl = document.createElement('div');
                dayEl.className = 'calendar-day' + (d === now.getDate() ? ' today' : '');
                dayEl.textContent = d;
                dayEl.onclick = () => {
                    document.querySelectorAll('.calendar-day').forEach(el => el.classList.remove('active'));
                    dayEl.classList.add('active');
                    window.SELECTED_DATE = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
                    window.switchScheduleStep(2);
                };
                calendarDays.appendChild(dayEl);
            }
        };

        // Settings & Preference Handlers
        window.toggleSetting = function (el, type) {
            el.classList.toggle('active');
            log(`Setting toggled: ${type}`);
        };

        window.saveSettings = async function () {
            try {
                const btn = event.target;
                const originalText = btn.textContent;
                btn.textContent = 'Saving...';

                // Ensure session exists before saving
                const session = StarsSession.get();
                if (!session || !window.stars_sb) throw new Error("Session lost. Please re-login.");

                // Example: Sync to Supabase profile if needed
                // await window.stars_sb.from('profiles').update({ ... }).eq('id', session.user.id);

                setTimeout(() => {
                    btn.textContent = 'Settings Saved!';
                    setTimeout(() => btn.textContent = originalText, 2000);
                }, 1000);
            } catch (err) {
                alert(err.message);
            }
        };

        window.switchScheduleStep = function (step) {
            document.getElementById('schedule-step-1').style.display = (step === 1 ? 'block' : 'none');
            document.getElementById('schedule-step-2').style.display = (step === 2 ? 'block' : 'none');
            if (step === 2) {
                document.getElementById('selected-date-display').textContent = window.SELECTED_DATE;
            }
        };

        window.submitSchedule = async function () {
            const time = document.getElementById('schedule-time-input').value;
            const link = document.getElementById('schedule-link-input').value;
            if (!time) { alert("Please select a time"); return; }
            const { token } = StarsSession.get();
            try {
                const res = await fetch('http://localhost:8000/api/sessions/schedule', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                    body: JSON.stringify({
                        pair_id: window.SELECTED_PAIR_ID, // Use pair_id as required by handle_schedule
                        start_time: `${window.SELECTED_DATE}T${time}`,
                        link: link
                    })
                });
                const result = await res.json();
                if (!res.ok) throw new Error(result.error || "Failed to schedule session");
                alert("Session scheduled successfully!");
                window.closeScheduleModal();
                initDashboard();
            } catch (err) { alert(err.message); }
        };

        window.handleFileSelect = function (input) {
            const file = input.files[0];
            if (file) {
                document.getElementById('selected-filename').textContent = `Selected: ${file.name}`;
                window.CURRENT_UPLOAD_FILE = file;
            }
        };

        window.submitResourceUpload = async function () {
            const name = document.getElementById('res-upload-name').value;
            const description = document.getElementById('res-upload-desc').value;
            const category = document.getElementById('res-upload-category').value;
            const type = document.getElementById('res-upload-type').value;
            const file = window.CURRENT_UPLOAD_FILE;

            if (!name || !file) { alert("Please enter name and select a file."); return; }

            const btn = document.getElementById('res-confirm-btn');
            btn.textContent = "Uploading...";
            btn.disabled = true;

            const session = StarsSession.get();
            if (!session) return;

            try {
                // 1. Upload to Supabase Storage
                const fileName = `${Date.now()}_${file.name}`;
                // Usage of stars_sb assumes it is the Supabase client initialized in stars_core
                const { data: storageData, error: storageError } = await window.stars_sb.storage
                    .from('shared-resources')
                    .upload(fileName, file);

                if (storageError) throw storageError;

                const { data: publicUrlData } = window.stars_sb.storage
                    .from('shared-resources')
                    .getPublicUrl(fileName);

                const url = publicUrlData.publicUrl;

                // 2. Save metadata to local backend
                const res = await fetch('http://localhost:8000/api/resources/upload', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${session.token}` },
                    body: JSON.stringify({ name, description, category, type, url })
                });

                if (!res.ok) throw new Error("Metadata sync failed.");

                alert("Resource posted successfully!");
                window.closeResourceUpload();
                initDashboard(); // Refresh library
            } catch (e) {
                alert(`Upload error: ${e.message}`);
            } finally {
                btn.textContent = "Post to Library";
                btn.disabled = false;
            }
        };

        // Modal Engine
        window.showStarsConfirm = function (title, body, onConfirm) {
            const overlay = document.getElementById('stars-modal-overlay');
            const modal = document.getElementById('stars-modal');
            document.getElementById('stars-modal-title').textContent = title;
            document.getElementById('stars-modal-body').textContent = body;
            const confirmBtn = document.getElementById('stars-modal-confirm-btn');

            // Re-bind click handler
            const newConfirmBtn = confirmBtn.cloneNode(true);
            confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

            newConfirmBtn.onclick = () => {
                onConfirm();
                window.closeStarsModal();
            };

            overlay.style.display = 'flex';
            setTimeout(() => modal.classList.add('active'), 10);
        };

        window.closeStarsModal = function () {
            const overlay = document.getElementById('stars-modal-overlay');
            const modal = document.getElementById('stars-modal');
            modal.classList.remove('active');
            setTimeout(() => overlay.style.display = 'none', 300);
        };

        window.logout = function () { StarsSession.clear(); location.reload(); };

        window.viewMentorProfile = function (id) {
            const m = (window.DASH_DATA?.mentors || []).find(x => x.id === id);
            if (!m) return;
            document.getElementById('modal-mentor-name').textContent = `${m.firstName || 'Mentor'} ${m.lastName || ''}`;
            document.getElementById('modal-mentor-avatar').textContent = (m.firstName || 'M').charAt(0);
            document.getElementById('modal-mentor-bio').textContent = m.bio || "No bio available.";

            const interests = document.getElementById('modal-mentor-interests');
            if (interests) {
                interests.innerHTML = (m.interests || "").split(',').map(i => i.trim()).filter(i => i).map(i => `<span class="pill mentor" style="margin: 0.2rem;">${i}</span>`).join('');
            }

            document.getElementById('mentor-profile-modal').style.display = 'flex';
        };

        window.handleOTP = function (input, index) {
            if (input.value && index < 6) {
                const next = input.nextElementSibling;
                if (next) next.focus();
            }
            // Sync to hidden input
            const boxes = document.querySelectorAll('.otp-box');
            let fullCode = '';
            boxes.forEach(b => fullCode += b.value);
            document.getElementById('visitor-otp').value = fullCode;
        };


        window.closeResourceUpload = () => document.getElementById('resource-upload-modal-overlay').style.display = 'none';

        // 5. App Lifecycle
        window.addEventListener('DOMContentLoaded', () => {
            log("ENGINE ONLINE.");
            const session = StarsSession.get();
            const loader = document.getElementById('system-loader');

            // Function to hide loader with safety timeout
            const hideInitialLoader = () => {
                if (loader) {
                    loader.classList.add('hidden');
                    setTimeout(() => { loader.style.display = 'none'; }, 500);
                }
            };

            if (session) {
                showAuthForm('dash');
            } else {
                // Check for entry hash from portal.html
                const hash = window.location.hash.replace('#', '');
                const validForms = ['login', 'register', 'staff-verify', 'visitor'];
                if (validForms.includes(hash)) {
                    showAuthForm(hash);
                } else {
                    showAuthForm('menu');
                }
                hideInitialLoader();
            }

            // Authoritative fallback
            setTimeout(hideInitialLoader, 2000);
        });
