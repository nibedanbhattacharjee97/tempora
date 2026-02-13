import streamlit as st
import pandas as pd
import sqlite3
import qrcode
import os
import cv2
from datetime import datetime
from pyzbar.pyzbar import decode, ZBarSymbol

# ---------------- CONFIG & DB ----------------
st.set_page_config(page_title="QR Attendance System", layout="wide")
QR_FOLDER = "qr_codes"
DB_NAME = "attendance.db"
os.makedirs(QR_FOLDER, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Create attendance table
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            name TEXT,
            mobile TEXT,
            status TEXT,
            scan_time TEXT
        )
    """)
    # Create student_registry table to store info from Excel
    c.execute("""
        CREATE TABLE IF NOT EXISTS students(
            student_id TEXT PRIMARY KEY,
            name TEXT,
            mobile TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------- HELPER FUNCTIONS ----------------
def save_to_db(student_id, name, mobile, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO attendance(student_id, name, mobile, status, scan_time) VALUES(?,?,?,?,?)",
              (student_id, name, mobile, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def generate_qr(data, file_name):
    img = qrcode.make(data)
    path = os.path.join(QR_FOLDER, file_name)
    img.save(path)
    return path

# ---------------- SIDEBAR ----------------
menu = st.sidebar.radio("Menu", ["Upload & Register", "Scan QR", "Records"])

# ---------------- PAGE 1: UPLOAD & REGISTER ----------------
if menu == "Upload & Register":
    st.title("📤 Register Students & Generate QR")
    file = st.file_uploader("Upload Student Excel", type=["xlsx"])
    
    if file:
        df = pd.read_excel(file)
        st.dataframe(df)
        
        if st.button("Generate QR & Save to Database"):
            conn = sqlite3.connect(DB_NAME)
            qr_paths = []
            for _, row in df.iterrows():
                sid, name, mob = str(row["Student ID"]), str(row["Name"]), str(row["Mobile"])
                
                # Save to student registry
                conn.execute("INSERT OR REPLACE INTO students (student_id, name, mobile) VALUES (?,?,?)", (sid, name, mob))
                
                # Generate QR
                qr_text = f"{sid}|{name}|{mob}"
                path = generate_qr(qr_text, f"{sid}.png")
                qr_paths.append(path)
            
            conn.commit()
            conn.close()
            st.success("Registration Complete & QR Codes Generated!")

# ---------------- PAGE 2: SCANNER (THE FIX) ----------------
elif menu == "Scan QR":
    st.title("📷 Attendance Scanner")
    
    # Session state to hold the 'found' user so the camera can stop
    if 'current_student' not in st.session_state:
        st.session_state.current_student = None

    if st.session_state.current_student is None:
        run = st.checkbox('Start Camera', value=True)
        FRAME_WINDOW = st.image([])
        camera = cv2.VideoCapture(0)

        while run:
            _, frame = camera.read()
            if frame is None: break
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            decoded_objs = decode(frame, symbols=[ZBarSymbol.QRCODE])
            
            for obj in decoded_objs:
                raw_data = obj.data.decode("utf-8")
                try:
                    sid, name, mob = raw_data.split("|")
                    st.session_state.current_student = {"id": sid, "name": name, "mob": mob}
                    run = False # Stop the loop
                except:
                    st.error("Invalid QR Code Format")
            
            FRAME_WINDOW.image(frame_rgb)
        camera.release()
    
    # If a student is found, show the data and the "Mark" button
    if st.session_state.current_student:
        s = st.session_state.current_student
        st.subheader("Student Detected")
        st.info(f"**ID:** {s['id']} | **Name:** {s['name']} | **Mobile:** {s['mob']}")
        
        col1, col2 = st.columns(2)
        if col1.button("✅ Confirm Attendance"):
            save_to_db(s['id'], s['name'], s['mob'], "Present")
            st.success(f"Saved: {s['name']}")
            st.session_state.current_student = None # Reset for next scan
            st.rerun()
            
        if col2.button("🔄 Rescan"):
            st.session_state.current_student = None
            st.rerun()

# ---------------- PAGE 3: VIEW ----------------
elif menu == "Records":
    st.title("📋 Attendance Logs")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM attendance ORDER BY scan_time DESC", conn)
    conn.close()
    st.dataframe(df, use_container_width=True)