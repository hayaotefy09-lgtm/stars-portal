import sqlite3

DATABASE = 'stars.db'

# 1. ADD YOUR NEW ACCOUNTS HERE
# Formats: 
# ('email@naischool.ae', 'First', 'Last', 'Password123', 'Role')
# Allowed Roles: 'Mentor', 'Mentee', 'ProgramStaff'
ACCOUNTS_TO_CREATE = [
    # Counselors
    ('nabeera.n@naischool.ae', 'Nabeera', 'Noman', 'counselor123', 'ProgramStaff'),
    ('joshua.q@naischool.ae', 'Joshua', 'Quinn', 'counselor123', 'ProgramStaff'),
    
    # Real Mentors
    ('tala.j@naischool.ae', 'Tala', 'Jubair', 'mentor123', 'Mentor'),
    ('maria.a@naischool.ae', 'Maria', 'Ahli', 'mentor123', 'Mentor'),
    
    # Real Mentees
    ('amira.i@naischool.ae', 'Amira', 'Ali Ismael', 'mentee123', 'Mentee')
]

# 2. ADD YOUR PAIRINGS HERE
# Only pair emails that exist in your database!
PAIRS_TO_CREATE = [
    # ('mentor_email', 'mentee_email')
    ('tala.j@naischool.ae', 'amira.i@naischool.ae')
]

def run():
    print("Connecting to STARS Backend Database...\n")
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    print("--- 1. Registering Accounts ---")
    for acc in ACCOUNTS_TO_CREATE:
        try:
            c.execute("INSERT INTO Users (email, first_name, last_name, password, role) VALUES (?, ?, ?, ?, ?)", acc)
            print(f"✅ Created {acc[4]}: {acc[1]} {acc[2]} ({acc[0]})")
        except sqlite3.IntegrityError:
            print(f"⚠️  Account {acc[0]} already exists.")
            
    print("\n--- 2. Establishing Pairings ---")
    for pair in PAIRS_TO_CREATE:
        try:
            c.execute("INSERT INTO MentorMenteePair (mentor_email, mentee_email) VALUES (?, ?)", pair)
            print(f"✅ Paired Mentor: {pair[0]}  <--->  Mentee: {pair[1]}")
        except sqlite3.IntegrityError:
            print(f"⚠️  Pair {pair[0]} <-> {pair[1]} already exists.")
            
    conn.commit()
    conn.close()
    
    print("\n-------------------------------------------")
    print("Database successfully updated! You can now log in.")
    print("-------------------------------------------\n")

if __name__ == "__main__":
    run()
