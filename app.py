import streamlit as st
import pandas as pd
import sqlite3
import qrcode
import os
import cv2
from datetime import datetime
from pyzbar.pyzbar import decode, ZBarSymbol

# --- CONFIGURATION ---
st.set_page_config(page_title="QR Attendance System", layout="wide")
QR_FOLDER = "qr_codes"
DB_NAME = "attendance.db"
os.makedirs(QR_FOLDER, exist_ok=True)

# --- DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Table for final attendance logs
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
    # Table for registered students (from Excel)
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

# --- APP TABS ---
tab1, tab2, tab3 = st.tabs(["📤 Register & QR", "📷 Scan Attendance", "📊 View Records"])

# --- TAB 1: UPLOAD EXCEL ---
with tab1:
    st.title("Student Registration")
    uploaded_file = st.file_uploader("Upload Student List (Excel)", type=["xlsx"])
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        st.write("Preview of Data:", df.head())
        
        if st.button("Register Students & Create QRs"):
            conn = sqlite3.connect(DB_NAME)
            for _, row in df.iterrows():
                sid, name, mob = str(row["Student ID"]), str(row["Name"]), str(row["Mobile"])
                
                # 1. Save to Database
                conn.execute("INSERT OR REPLACE INTO students (student_id, name, mobile) VALUES (?,?,?)", (sid, name, mob))
                
                # 2. Generate QR
                qr_text = f"{sid}|{name}|{mob}"
                img = qrcode.make(qr_text)
                img.save(os.path.join(QR_FOLDER, f"{sid}.png"))
                
            conn.commit()
            conn.close()
            st.success(f"✅ Registered {len(df)} students and generated QR codes!")

# --- TAB 2: THE SCANNER ---
with tab2:
    st.title("QR Scanner")
    
    # Session state to manage the "detection" flow
    if 'detected_user' not in st.session_state:
        st.session_state.detected_user = None

    # Step A: Show Camera if no one is detected yet
    if st.session_state.detected_user is None:
        cam_toggle = st.checkbox("Turn On Camera", value=True)
        FRAME_WINDOW = st.image([])
        cap = cv2.VideoCapture(0)

        while cam_toggle:
            ret, frame = cap.read()
            if not ret: break
            
            # Scan for QR
            decoded_objs = decode(frame, symbols=[ZBarSymbol.QRCODE])
            for obj in decoded_objs:
                raw_data = obj.data.decode("utf-8")
                try:
                    sid, name, mob = raw_data.split("|")
                    st.session_state.detected_user = {"id": sid, "name": name, "mob": mob}
                    cam_toggle = False # Break the loop
                except ValueError:
                    st.warning("QR Format Invalid. Use: ID|Name|Mobile")
            
            # Display feed
            if cam_toggle:
                FRAME_WINDOW.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        
        cap.release()

    # Step B: Show Detection Result and Action Buttons
    if st.session_state.detected_user:
        u = st.session_state.detected_user
        st.info(f"📍 **Detected Student:** {u['name']} (ID: {u['id']})")
        
        c1, c2 = st.columns(2)
        if c1.button("✅ Mark Present", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            conn.execute("INSERT INTO attendance (student_id, name, mobile, status, scan_time) VALUES (?,?,?,?,?)",
                         (u['id'], u['name'], u['mob'], "Present", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
            st.success(f"Attendance saved for {u['name']}!")
            st.session_state.detected_user = None # Clear and refresh
            st.rerun()

        if c2.button("🔄 Clear/Rescan", use_container_width=True):
            st.session_state.detected_user = None
            st.rerun()

# --- TAB 3: RECORDS ---
with tab3:
    st.title("Attendance Database")
    if st.button("Refresh Table"):
        conn = sqlite3.connect(DB_NAME)
        logs_df = pd.read_sql("SELECT * FROM attendance ORDER BY scan_time DESC", conn)
        conn.close()
        st.dataframe(logs_df, use_container_width=True)