# Generative AI Based Virtual Medical Assistance for Telemedicine

A full-stack **HTML, CSS, JavaScript, and Python (Flask + SQLite)** web application implementing all 5 core modules of the **VelCare Telemedicine** project.

## Features Implemented
1. **Home Page:** Hospital introduction, navigation menu, login & registration modal, quick demo access, and "Book Appointment" CTA.
2. **AI Medical Chatbot:** Natural-language health Q&A with safe self-care suggestions, automatic emergency symptom triage (e.g., chest pain, difficulty breathing), optional Google Gemini API integration, and built-in NLP fallback.
3. **Appointment Management:** Select specialist doctor, date, and time slot; book, view, cancel, and receive upcoming appointment reminders (with double-booking prevention).
4. **Patient Management:** Patient registration, editable personal & basic health information (age, gender, blood group, allergies, chronic conditions, medications, emergency contact), and appointment history.
5. **Doctor Consultation:** Specialist directory, online consultation room with live patient–doctor messaging, webcam/simulated video call toggle, consultation status tracking (`Scheduled`, `In Progress`, `Completed`, `Cancelled`), and consultation notes.

## How to Run
```bash
cd C:\Users\surya\.gemini\antigravity\scratch\thalapa-sai-telemedicine
python app.py
```
Then open **http://127.0.0.1:5000** in your browser.

### Optional: Enable Live Gemini AI
1. Copy `.env.example` to `.env`
2. Set `GEMINI_API_KEY=your_api_key_here`
3. Restart `python app.py`

*(Without an API key, the built-in NLP & Safety Triage engine handles all queries offline.)*

## Demo Credentials
- **Patient:** `patient@velcare.com` / `patient123`
- **Doctor:** `doctor@velcare.com` / `doctor123`
