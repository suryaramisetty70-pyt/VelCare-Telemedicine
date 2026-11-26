import os
import re
import sqlite3
from datetime import datetime
from functools import wraps

import requests
from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "telemedicine.db")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "velcare-telemedicine-secret-key-2026")


def load_env_file():
    """Load key=value pairs from .env if present without external dependencies."""
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


load_env_file()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'patient',
            phone TEXT DEFAULT '',
            age INTEGER,
            gender TEXT DEFAULT '',
            blood_group TEXT DEFAULT '',
            allergies TEXT DEFAULT '',
            chronic_conditions TEXT DEFAULT '',
            medications TEXT DEFAULT '',
            emergency_contact TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialty TEXT NOT NULL,
            qualification TEXT NOT NULL,
            experience_years INTEGER NOT NULL,
            available_days TEXT NOT NULL,
            available_hours TEXT NOT NULL,
            rating REAL NOT NULL DEFAULT 4.8,
            bio TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available'
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            symptoms TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Scheduled',
            consultation_notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            intent TEXT DEFAULT 'general',
            is_emergency INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS consultation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            sender_role TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE
        );
        """
    )

    # Seed doctors if empty
    doc_count = cur.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]
    if doc_count == 0:
        doctors_seed = [
            (
                "Dr. Ananya Sharma",
                "General Physician",
                "MBBS, MD (Internal Medicine)",
                10,
                "Mon - Sat",
                "09:00 AM - 05:00 PM",
                4.9,
                "Specializes in primary care, fever management, preventive health, and chronic lifestyle conditions.",
                "Available",
            ),
            (
                "Dr. Rajesh Kumar",
                "Cardiologist",
                "MBBS, MD, DM (Cardiology)",
                14,
                "Mon - Fri",
                "10:00 AM - 04:00 PM",
                4.8,
                "Expert in hypertension, heart health screening, ECG evaluation, and cardiac preventive care.",
                "Available",
            ),
            (
                "Dr. Priya Nair",
                "Dermatologist",
                "MBBS, MD (Dermatology)",
                8,
                "Tue - Sun",
                "11:00 AM - 06:00 PM",
                4.8,
                "Focuses on skin allergies, rashes, acne, eczema, and teledermatology consultations.",
                "Available",
            ),
            (
                "Dr. Vikram Reddy",
                "Pediatrician",
                "MBBS, DCH, MD (Pediatrics)",
                11,
                "Mon - Sat",
                "09:30 AM - 05:30 PM",
                4.9,
                "Provides remote pediatric guidance, immunization schedules, and child nutrition advice.",
                "Available",
            ),
            (
                "Dr. Meera Krishnan",
                "Neurologist",
                "MBBS, MD, DM (Neurology)",
                12,
                "Mon - Fri",
                "10:00 AM - 03:00 PM",
                4.7,
                "Treats migraines, chronic headaches, sleep disorders, and neurological follow-ups.",
                "Available",
            ),
        ]
        cur.executemany(
            """
            INSERT INTO doctors (name, specialty, qualification, experience_years, available_days, available_hours, rating, bio, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            doctors_seed,
        )

    # Seed demo patient & demo doctor accounts if not present
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not cur.execute("SELECT id FROM users WHERE email = ?", ("patient@velcare.com",)).fetchone():
        cur.execute(
            """
            INSERT INTO users (name, email, password_hash, role, phone, age, gender, blood_group, allergies, chronic_conditions, medications, emergency_contact, created_at)
            VALUES (?, ?, ?, 'patient', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "K. Venkata Thalpa Sai",
                "patient@velcare.com",
                generate_password_hash("patient123"),
                "+91 98765 43210",
                21,
                "Male",
                "O+",
                "None known",
                "None",
                "Vitamin D3 (weekly)",
                "+91 98765 00000",
                now,
            ),
        )
        demo_patient_id = cur.lastrowid
        # Seed a sample appointment for demo patient
        cur.execute(
            """
            INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, symptoms, status, consultation_notes, created_at)
            VALUES (?, 1, ?, '10:30 AM', 'Mild seasonal cold and fatigue', 'Scheduled', '', ?)
            """,
            (demo_patient_id, datetime.now().strftime("%Y-%m-%d"), now),
        )
        appt_id = cur.lastrowid
        cur.execute(
            """
            INSERT INTO consultation_messages (appointment_id, sender_role, sender_name, message, created_at)
            VALUES (?, 'doctor', 'Dr. Ananya Sharma', 'Hello! I have received your appointment request. Please share how long you have had the cold and if you have any fever.', ?)
            """,
            (appt_id, now),
        )

    if not cur.execute("SELECT id FROM users WHERE email = ?", ("doctor@velcare.com",)).fetchone():
        cur.execute(
            """
            INSERT INTO users (name, email, password_hash, role, phone, created_at)
            VALUES (?, ?, ?, 'doctor', ?, ?)
            """,
            (
                "Dr. Ananya Sharma",
                "doctor@velcare.com",
                generate_password_hash("doctor123"),
                "+91 98000 11111",
                now,
            ),
        )

    conn.commit()
    conn.close()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required. Please log in."}), 401
        return fn(*args, **kwargs)

    return wrapper


# --- NLP Intent Classification & Safety Engine ---
EMERGENCY_KEYWORDS = [
    "chest pain",
    "heart attack",
    "can't breathe",
    "cannot breathe",
    "difficulty breathing",
    "shortness of breath",
    "severe bleeding",
    "unconscious",
    "fainted",
    "stroke",
    "paralysis",
    "seizure",
    "suicide",
    "overdose",
    "choking",
    "severe burn",
]

KNOWLEDGE_BASE = [
    {
        "intent": "hydration_wellness",
        "keywords": ["water", "hydration", "drink water", "dehydration", "thirst"],
        "reply": (
            "Drinking sufficient water is essential for regulating body temperature, supporting kidney function, "
            "improving digestion, and maintaining energy levels. Most adults benefit from around 2–3 liters (8–10 glasses) "
            "of fluids daily, adjusted for climate and activity.\n\n"
            "Safe Suggestions:\n"
            "- Sip water steadily throughout the day rather than all at once.\n"
            "- Watch for signs of dehydration such as dark urine, dizziness, or dry mouth.\n"
            "- If dehydration is accompanied by persistent vomiting or diarrhea, consult a doctor promptly."
        ),
    },
    {
        "intent": "headache",
        "keywords": ["headache", "migraine", "head pain", "head ache"],
        "reply": (
            "Mild headaches are commonly linked to dehydration, eye strain, stress, or lack of sleep.\n\n"
            "Safe Suggestions:\n"
            "- Rest in a quiet, dimly lit room and hydrate with water.\n"
            "- Take a break from screens and apply a cool or warm compress.\n"
            "- Seek medical consultation if the headache is sudden and severe, lasts more than 2–3 days, "
            "or is accompanied by fever, stiff neck, vision changes, or nausea."
        ),
    },
    {
        "intent": "fever_cold",
        "keywords": ["fever", "temperature", "cold", "cough", "sore throat", "flu", "sneezing"],
        "reply": (
            "Mild fever and cold symptoms often indicate a common viral infection that improves with rest and supportive care.\n\n"
            "Safe Suggestions:\n"
            "- Stay well hydrated with water, warm broths, or oral rehydration fluids.\n"
            "- Get adequate rest and monitor your temperature regularly.\n"
            "- Avoid self-medicating with antibiotics without a doctor's prescription.\n"
            "- Consult a General Physician if fever exceeds 102°F (38.9°C), lasts more than 3 days, or causes breathing discomfort."
        ),
    },
    {
        "intent": "stomach_digestion",
        "keywords": ["stomach", "acidity", "gastric", "indigestion", "nausea", "vomit", "diarrhea", "abdomen"],
        "reply": (
            "Mild digestive discomfort is often caused by dietary triggers, acidity, or mild gastroenteritis.\n\n"
            "Safe Suggestions:\n"
            "- Eat light, bland meals (rice, bananas, toast, yogurt) and avoid spicy or oily foods.\n"
            "- Sip oral rehydration solution (ORS) or water frequently if experiencing loose stools.\n"
            "- Book a consultation if you experience severe abdominal pain, persistent vomiting, blood in stool, or high fever."
        ),
    },
    {
        "intent": "skin_allergy",
        "keywords": ["rash", "skin", "itch", "itching", "allergy", "acne", "eczema", "hives"],
        "reply": (
            "Skin rashes or itching can result from contact allergies, dryness, or mild infections.\n\n"
            "Safe Suggestions:\n"
            "- Keep the area clean and avoid scratching or applying unprescribed steroid creams.\n"
            "- Use a gentle, fragrance-free moisturizer and wear breathable cotton clothing.\n"
            "- If the rash spreads rapidly, blisters, or comes with facial/throat swelling, seek immediate medical care."
        ),
    },
    {
        "intent": "sleep_stress",
        "keywords": ["sleep", "insomnia", "stress", "anxiety", "tired", "fatigue"],
        "reply": (
            "Quality sleep and stress management are key pillars of overall health.\n\n"
            "Safe Suggestions:\n"
            "- Maintain a consistent sleep schedule (7–8 hours) and avoid screens 45 minutes before bed.\n"
            "- Limit caffeine in the late afternoon and try deep-breathing or light stretching.\n"
            "- If fatigue or insomnia persists for several weeks, consult a physician to rule out nutritional or thyroid causes."
        ),
    },
    {
        "intent": "appointment_help",
        "keywords": ["appointment", "book", "doctor", "schedule", "consult", "visit"],
        "reply": (
            "I can help you prepare for a doctor consultation! You can use the **Appointment Management** section "
            "to select a specialist (General Physician, Cardiologist, Dermatologist, Pediatrician, or Neurologist), "
            "choose a convenient date and time slot, and confirm your booking."
        ),
    },
]


ALLOWED_GEMINI_MODELS = {"gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"}


def classify_and_respond(
    user_message: str,
    patient_context: dict = None,
    custom_api_key: str = None,
    model_name: str = "gemini-2.0-flash",
):
    text_lower = user_message.lower().strip()

    # 1. Emergency Triage Check (Highest Priority)
    for kw in EMERGENCY_KEYWORDS:
        if kw in text_lower:
            return {
                "reply": (
                    "⚠️ **URGENT MEDICAL ALERT**: Your message mentions symptoms (`"
                    + kw
                    + "`) that may require **immediate emergency medical attention**.\n\n"
                    "Please call your local emergency number (e.g., **108 / 112** in India or **911**) "
                    "or visit the nearest hospital emergency department right away. "
                    "Do not wait for an online consultation for emergency symptoms."
                ),
                "intent": "emergency_referral",
                "is_emergency": True,
                "source": "Safety Triage Engine",
            }

    # 2. Optional Live Gemini API Call (uses frontend Settings key or server env key)
    api_key = (custom_api_key or "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
    selected_model = model_name if model_name in ALLOWED_GEMINI_MODELS else "gemini-2.0-flash"
    api_warning = None
    if api_key:
        try:
            system_prompt = (
                "You are a safe, empathetic Virtual Medical Assistant for a Telemedicine platform. "
                "Provide clear, preliminary general health information and safe self-care suggestions. "
                "Never diagnose definitively or prescribe controlled medications. "
                "Always advise consulting a qualified doctor if symptoms persist or worsen. "
                "Keep responses concise, structured, and easy to understand."
            )
            context_note = ""
            if patient_context:
                context_note = (
                    f"\nPatient profile context: Age={patient_context.get('age') or 'N/A'}, "
                    f"Gender={patient_context.get('gender') or 'N/A'}, "
                    f"Allergies={patient_context.get('allergies') or 'None'}, "
                    f"Conditions={patient_context.get('chronic_conditions') or 'None'}."
                )
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": f"{system_prompt}{context_note}\n\nPatient Question: {user_message}"}],
                    }
                ]
            }
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    ai_text = candidates[0]["content"]["parts"][0]["text"]
                    return {
                        "reply": ai_text + "\n\n*Disclaimer: This is preliminary AI guidance and does not replace professional medical advice.*",
                        "intent": "gemini_ai",
                        "is_emergency": False,
                        "source": f"Gemini AI ({selected_model})",
                    }
            else:
                err_msg = resp.json().get("error", {}).get("message", f"HTTP {resp.status_code}")
                api_warning = f"Gemini API returned an error ({err_msg}); used built-in NLP fallback."
        except Exception as exc:
            api_warning = f"Gemini API request failed ({exc}); used built-in NLP fallback."

    # 3. Local NLP Keyword & Intent Matching Engine
    for entry in KNOWLEDGE_BASE:
        for kw in entry["keywords"]:
            if re.search(r"\b" + re.escape(kw) + r"\b", text_lower) or kw in text_lower:
                return {
                    "reply": entry["reply"] + "\n\n*Disclaimer: Preliminary guidance only — not a medical diagnosis.*",
                    "intent": entry["intent"],
                    "is_emergency": False,
                    "source": "NLP Medical Assistant",
                }

    # 4. General Fallback Response
    return {
        "reply": (
            "Thank you for sharing your health question. Based on what you described:\n\n"
            "- Monitor your symptoms (duration, severity, and any triggers).\n"
            "- Stay hydrated, get adequate rest, and avoid unprescribed medications.\n"
            "- For personalized evaluation, please book an online consultation with one of our specialists "
            "in the **Appointment Management** tab.\n\n"
            "*Disclaimer: This is preliminary AI guidance and does not replace professional medical advice.*"
        ),
        "intent": "general_guidance",
        "is_emergency": False,
        "source": "NLP Medical Assistant",
    }


# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({"status": "ok", "gemini_configured": bool(os.environ.get("GEMINI_API_KEY", "").strip())})


# --- Auth & Patient Management APIs ---
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = data.get("role", "patient")
    if role not in ("patient", "doctor"):
        role = "patient"

    if not name or not email or len(password) < 4:
        return jsonify({"error": "Name, valid email, and password (min 4 chars) are required."}), 400

    conn = get_db()
    if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
        conn.close()
        return jsonify({"error": "An account with this email already exists."}), 409

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO users (name, email, password_hash, role, phone, age, gender, blood_group, allergies, chronic_conditions, medications, emergency_contact, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            email,
            generate_password_hash(password),
            role,
            (data.get("phone") or "").strip(),
            data.get("age") or None,
            (data.get("gender") or "").strip(),
            (data.get("blood_group") or "").strip(),
            (data.get("allergies") or "None").strip(),
            (data.get("chronic_conditions") or "None").strip(),
            (data.get("medications") or "None").strip(),
            (data.get("emergency_contact") or "").strip(),
            now,
        ),
    )
    user_id = cur.lastrowid
    conn.commit()
    user = dict(conn.execute("SELECT id, name, email, role, phone, age, gender, blood_group, allergies, chronic_conditions, medications, emergency_contact FROM users WHERE id = ?", (user_id,)).fetchone())
    conn.close()

    session["user_id"] = user["id"]
    session["role"] = user["role"]
    return jsonify({"message": "Registration successful.", "user": user}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid email or password."}), 401

    session["user_id"] = row["id"]
    session["role"] = row["role"]
    user = {k: row[k] for k in row.keys() if k != "password_hash"}
    return jsonify({"message": "Login successful.", "user": user})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully."})


@app.route("/api/auth/me", methods=["GET"])
def me():
    if "user_id" not in session:
        return jsonify({"user": None})
    conn = get_db()
    row = conn.execute(
        "SELECT id, name, email, role, phone, age, gender, blood_group, allergies, chronic_conditions, medications, emergency_contact FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    conn.close()
    return jsonify({"user": dict(row) if row else None})


@app.route("/api/patient/profile", methods=["PUT"])
@login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    conn = get_db()
    conn.execute(
        """
        UPDATE users
        SET name = ?, phone = ?, age = ?, gender = ?, blood_group = ?,
            allergies = ?, chronic_conditions = ?, medications = ?, emergency_contact = ?
        WHERE id = ?
        """,
        (
            (data.get("name") or "").strip(),
            (data.get("phone") or "").strip(),
            data.get("age") or None,
            (data.get("gender") or "").strip(),
            (data.get("blood_group") or "").strip(),
            (data.get("allergies") or "").strip(),
            (data.get("chronic_conditions") or "").strip(),
            (data.get("medications") or "").strip(),
            (data.get("emergency_contact") or "").strip(),
            session["user_id"],
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, name, email, role, phone, age, gender, blood_group, allergies, chronic_conditions, medications, emergency_contact FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    conn.close()
    return jsonify({"message": "Patient profile updated.", "user": dict(row)})


# --- Doctors API ---
@app.route("/api/doctors", methods=["GET"])
def list_doctors():
    conn = get_db()
    rows = conn.execute("SELECT * FROM doctors ORDER BY id ASC").fetchall()
    conn.close()
    return jsonify({"doctors": [dict(r) for r in rows]})


# --- AI Medical Chatbot APIs ---
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    custom_api_key = (data.get("api_key") or "").strip()
    model_name = (data.get("model") or "gemini-2.0-flash").strip()
    if not message:
        return jsonify({"error": "Please enter a health question or symptom."}), 400

    user_id = session.get("user_id")
    patient_context = None
    conn = get_db()
    if user_id:
        row = conn.execute(
            "SELECT age, gender, allergies, chronic_conditions FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row:
            patient_context = dict(row)

    result = classify_and_respond(message, patient_context, custom_api_key=custom_api_key, model_name=model_name)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute(
        "INSERT INTO chat_messages (user_id, sender, message, intent, is_emergency, created_at) VALUES (?, 'user', ?, ?, ?, ?)",
        (user_id, message, result["intent"], 1 if result["is_emergency"] else 0, now),
    )
    conn.execute(
        "INSERT INTO chat_messages (user_id, sender, message, intent, is_emergency, created_at) VALUES (?, 'assistant', ?, ?, ?, ?)",
        (user_id, result["reply"], result["intent"], 1 if result["is_emergency"] else 0, now),
    )
    conn.commit()
    conn.close()

    return jsonify(result)


@app.route("/api/settings/test-gemini", methods=["POST"])
def test_gemini_key():
    data = request.get_json(silent=True) or {}
    api_key = (data.get("api_key") or "").strip()
    model_name = (data.get("model") or "gemini-2.0-flash").strip()
    selected_model = model_name if model_name in ALLOWED_GEMINI_MODELS else "gemini-2.0-flash"

    if not api_key:
        return jsonify({"ok": False, "error": "Please enter a Gemini API key first."}), 400

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent?key={api_key}"
    try:
        resp = requests.post(
            url,
            json={"contents": [{"role": "user", "parts": [{"text": "Reply with OK only."}]}]},
            timeout=10,
        )
        if resp.status_code == 200:
            return jsonify({"ok": True, "message": f"Connected successfully to {selected_model}!"})
        err = resp.json().get("error", {}).get("message", f"HTTP {resp.status_code}")
        return jsonify({"ok": False, "error": err}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/chat/history", methods=["GET"])
def chat_history():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"messages": []})
    conn = get_db()
    rows = conn.execute(
        "SELECT sender, message, intent, is_emergency, created_at FROM chat_messages WHERE user_id = ? ORDER BY id ASC LIMIT 50",
        (user_id,),
    ).fetchall()
    conn.close()
    return jsonify({"messages": [dict(r) for r in rows]})


# --- Appointment Management APIs ---
@app.route("/api/appointments", methods=["GET"])
@login_required
def get_appointments():
    conn = get_db()
    if session.get("role") == "doctor":
        rows = conn.execute(
            """
            SELECT a.*, d.name AS doctor_name, d.specialty, u.name AS patient_name, u.age AS patient_age,
                   u.gender AS patient_gender, u.blood_group, u.allergies, u.chronic_conditions
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            JOIN users u ON a.patient_id = u.id
            ORDER BY a.appointment_date DESC, a.id DESC
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT a.*, d.name AS doctor_name, d.specialty, d.qualification
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            WHERE a.patient_id = ?
            ORDER BY a.appointment_date DESC, a.id DESC
            """,
            (session["user_id"],),
        ).fetchall()
    conn.close()
    return jsonify({"appointments": [dict(r) for r in rows]})


@app.route("/api/appointments", methods=["POST"])
@login_required
def create_appointment():
    data = request.get_json(silent=True) or {}
    doctor_id = data.get("doctor_id")
    appointment_date = (data.get("appointment_date") or "").strip()
    appointment_time = (data.get("appointment_time") or "").strip()
    symptoms = (data.get("symptoms") or "").strip()

    if not doctor_id or not appointment_date or not appointment_time:
        return jsonify({"error": "Doctor, date, and time slot are required."}), 400

    conn = get_db()
    conflict = conn.execute(
        """
        SELECT id FROM appointments
        WHERE doctor_id = ? AND appointment_date = ? AND appointment_time = ? AND status != 'Cancelled'
        """,
        (doctor_id, appointment_date, appointment_time),
    ).fetchone()
    if conflict:
        conn.close()
        return jsonify({"error": "This time slot is already booked for the selected doctor. Please choose another slot."}), 409

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, symptoms, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'Scheduled', ?)
        """,
        (session["user_id"], doctor_id, appointment_date, appointment_time, symptoms, now),
    )
    appt_id = cur.lastrowid

    doc = conn.execute("SELECT name FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
    doc_name = doc["name"] if doc else "Doctor"
    cur.execute(
        """
        INSERT INTO consultation_messages (appointment_id, sender_role, sender_name, message, created_at)
        VALUES (?, 'doctor', ?, ?, ?)
        """,
        (
            appt_id,
            doc_name,
            f"Appointment confirmed for {appointment_date} at {appointment_time}. You can share any additional symptoms or reports here before the call.",
            now,
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Appointment booked successfully.", "appointment_id": appt_id}), 201


@app.route("/api/appointments/<int:appt_id>", methods=["PUT"])
@login_required
def update_appointment(appt_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    appt = conn.execute("SELECT * FROM appointments WHERE id = ?", (appt_id,)).fetchone()
    if not appt:
        conn.close()
        return jsonify({"error": "Appointment not found."}), 404

    if session.get("role") != "doctor" and appt["patient_id"] != session["user_id"]:
        conn.close()
        return jsonify({"error": "Unauthorized."}), 403

    new_date = data.get("appointment_date", appt["appointment_date"])
    new_time = data.get("appointment_time", appt["appointment_time"])
    new_status = data.get("status", appt["status"])
    new_notes = data.get("consultation_notes", appt["consultation_notes"])

    conn.execute(
        """
        UPDATE appointments
        SET appointment_date = ?, appointment_time = ?, status = ?, consultation_notes = ?
        WHERE id = ?
        """,
        (new_date, new_time, new_status, new_notes, appt_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Appointment updated."})


# --- Doctor Consultation Chat APIs ---
@app.route("/api/consultations/<int:appt_id>/messages", methods=["GET"])
@login_required
def get_consultation_messages(appt_id):
    conn = get_db()
    appt = conn.execute("SELECT * FROM appointments WHERE id = ?", (appt_id,)).fetchone()
    if not appt:
        conn.close()
        return jsonify({"error": "Appointment not found."}), 404
    if session.get("role") != "doctor" and appt["patient_id"] != session["user_id"]:
        conn.close()
        return jsonify({"error": "Unauthorized."}), 403

    msgs = conn.execute(
        "SELECT * FROM consultation_messages WHERE appointment_id = ? ORDER BY id ASC",
        (appt_id,),
    ).fetchall()
    conn.close()
    return jsonify({"messages": [dict(m) for m in msgs]})


@app.route("/api/consultations/<int:appt_id>/messages", methods=["POST"])
@login_required
def post_consultation_message(appt_id):
    data = request.get_json(silent=True) or {}
    text = (data.get("message") or "").strip()
    if not text:
        return jsonify({"error": "Message cannot be empty."}), 400

    conn = get_db()
    appt = conn.execute("SELECT * FROM appointments WHERE id = ?", (appt_id,)).fetchone()
    if not appt:
        conn.close()
        return jsonify({"error": "Appointment not found."}), 404
    if session.get("role") != "doctor" and appt["patient_id"] != session["user_id"]:
        conn.close()
        return jsonify({"error": "Unauthorized."}), 403

    user = conn.execute("SELECT name, role FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """
        INSERT INTO consultation_messages (appointment_id, sender_role, sender_name, message, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (appt_id, user["role"], user["name"], text, now),
    )
    if appt["status"] == "Scheduled":
        conn.execute("UPDATE appointments SET status = 'In Progress' WHERE id = ?", (appt_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Sent."}), 201


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    use_reloader = os.environ.get("FLASK_RELOAD", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=use_reloader)
