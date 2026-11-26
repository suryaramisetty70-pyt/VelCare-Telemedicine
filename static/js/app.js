let currentUser = null;
let doctorsList = [];
let appointmentsList = [];
let activeConsultationId = null;
let localMediaStream = null;
let serverGeminiConfigured = false;

const LS_API_KEY = "velcare_gemini_api_key";
const LS_MODEL_KEY = "velcare_gemini_model";

document.addEventListener("DOMContentLoaded", async () => {
  const dateInput = document.getElementById("apptDate");
  if (dateInput) {
    const today = new Date().toISOString().split("T")[0];
    dateInput.value = today;
    dateInput.min = today;
  }

  await checkHealth();
  await loadDoctors();
  await refreshAuth();
});

function showSection(sectionId) {
  document.querySelectorAll(".page-section").forEach((sec) => sec.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach((btn) => btn.classList.remove("active"));

  const target = document.getElementById(`section-${sectionId}`);
  if (target) {
    target.classList.add("active");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const activeBtn = document.querySelector(`.nav-btn[data-section="${sectionId}"]`);
  if (activeBtn) activeBtn.classList.add("active");

  if (sectionId === "appointments" || sectionId === "consultation" || sectionId === "patient") {
    if (currentUser) loadAppointments();
  }
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.remove("hidden");
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => toast.classList.add("hidden"), 3200);
}

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    serverGeminiConfigured = Boolean(data.gemini_configured);
    updateAiEngineBadge();
  } catch (e) {
    console.error(e);
  }
}

function getSavedApiKey() {
  return (localStorage.getItem(LS_API_KEY) || "").trim();
}

function getSavedModel() {
  return localStorage.getItem(LS_MODEL_KEY) || "gemini-2.0-flash";
}

function updateAiEngineBadge() {
  const badge = document.getElementById("aiEngineBadge");
  if (!badge) return;
  const userKey = getSavedApiKey();
  let label = "NLP + Safety Engine Active";
  if (userKey) {
    label = `Gemini AI Active (${getSavedModel()})`;
  } else if (serverGeminiConfigured) {
    label = "Gemini AI Connected (Server)";
  }
  badge.innerHTML = `<span class="pulse-dot"></span>${label}`;
}

function openSettingsModal() {
  document.getElementById("geminiApiKeyInput").value = getSavedApiKey();
  document.getElementById("geminiModelSelect").value = getSavedModel();
  document.getElementById("apiTestStatus").textContent = "";
  document.getElementById("settingsModal").classList.remove("hidden");
}

function closeSettingsModal() {
  document.getElementById("settingsModal").classList.add("hidden");
}

function toggleApiKeyVisibility() {
  const input = document.getElementById("geminiApiKeyInput");
  const btn = document.getElementById("toggleKeyVisBtn");
  if (input.type === "password") {
    input.type = "text";
    btn.textContent = "Hide";
  } else {
    input.type = "password";
    btn.textContent = "Show";
  }
}

function saveApiSettings(e) {
  e.preventDefault();
  const key = document.getElementById("geminiApiKeyInput").value.trim();
  const model = document.getElementById("geminiModelSelect").value;
  if (key) {
    localStorage.setItem(LS_API_KEY, key);
  } else {
    localStorage.removeItem(LS_API_KEY);
  }
  localStorage.setItem(LS_MODEL_KEY, model);
  updateAiEngineBadge();
  closeSettingsModal();
  showToast(key ? `Gemini AI enabled (${model})!` : "Using built-in NLP engine.");
}

function clearApiSettings() {
  localStorage.removeItem(LS_API_KEY);
  document.getElementById("geminiApiKeyInput").value = "";
  document.getElementById("apiTestStatus").textContent = "Cleared. Using built-in NLP & Safety Engine.";
  updateAiEngineBadge();
  showToast("API key cleared.");
}

async function testApiSettings() {
  const key = document.getElementById("geminiApiKeyInput").value.trim();
  const model = document.getElementById("geminiModelSelect").value;
  const statusEl = document.getElementById("apiTestStatus");
  statusEl.style.color = "var(--muted)";
  statusEl.textContent = "Testing connection...";

  try {
    const res = await fetch("/api/settings/test-gemini", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: key, model }),
    });
    const data = await res.json();
    if (data.ok) {
      statusEl.style.color = "var(--secondary-dark)";
      statusEl.textContent = "✓ " + data.message;
    } else {
      statusEl.style.color = "var(--danger)";
      statusEl.textContent = "✕ " + (data.error || "Connection failed");
    }
  } catch (err) {
    statusEl.style.color = "var(--danger)";
    statusEl.textContent = "✕ Network error while testing key.";
  }
}

// --- Auth ---
function openAuthModal(tab = "login") {
  document.getElementById("authModal").classList.remove("hidden");
  switchAuthTab(tab);
}

function closeAuthModal() {
  document.getElementById("authModal").classList.add("hidden");
}

function switchAuthTab(tab) {
  const isLogin = tab === "login";
  document.getElementById("tabLogin").classList.toggle("active", isLogin);
  document.getElementById("tabRegister").classList.toggle("active", !isLogin);
  document.getElementById("loginForm").classList.toggle("hidden", !isLogin);
  document.getElementById("registerForm").classList.toggle("hidden", isLogin);
}

async function refreshAuth() {
  const res = await fetch("/api/auth/me");
  const data = await res.json();
  currentUser = data.user;
  renderAuthUI();
  if (currentUser) {
    await loadChatHistory();
    await loadAppointments();
    populateProfileForm();
  }
}

function renderAuthUI() {
  const navAuth = document.getElementById("navAuth");
  const guestNotice = document.getElementById("patientGuestNotice");
  const dashboard = document.getElementById("patientDashboard");

  if (currentUser) {
    navAuth.innerHTML = `
      <span class="user-pill">${escapeHtml(currentUser.name)} (${escapeHtml(currentUser.role)})</span>
      <button class="btn btn-outline btn-sm" onclick="handleLogout()">Logout</button>
    `;
    guestNotice.classList.add("hidden");
    dashboard.classList.remove("hidden");
  } else {
    navAuth.innerHTML = `
      <button class="btn btn-outline" onclick="openAuthModal('login')">Login</button>
      <button class="btn btn-primary" onclick="openAuthModal('register')">Register</button>
    `;
    guestNotice.classList.remove("hidden");
    dashboard.classList.add("hidden");
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById("loginEmail").value;
  const password = document.getElementById("loginPassword").value;

  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || "Login failed");
    return;
  }
  closeAuthModal();
  showToast(`Welcome back, ${data.user.name}!`);
  await refreshAuth();
}

async function handleRegister(e) {
  e.preventDefault();
  const payload = {
    name: document.getElementById("regName").value,
    email: document.getElementById("regEmail").value,
    password: document.getElementById("regPassword").value,
    role: document.getElementById("regRole").value,
    age: document.getElementById("regAge").value || null,
    gender: document.getElementById("regGender").value,
  };
  const res = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || "Registration failed");
    return;
  }
  closeAuthModal();
  showToast("Account created and logged in!");
  await refreshAuth();
}

async function handleLogout() {
  await fetch("/api/auth/logout", { method: "POST" });
  currentUser = null;
  appointmentsList = [];
  renderAuthUI();
  document.getElementById("appointmentsList").innerHTML = `<p class="muted">Please log in to view and manage your appointments.</p>`;
  document.getElementById("reminderBanner").classList.add("hidden");
  showToast("Logged out successfully.");
}

async function demoLogin(type) {
  const creds =
    type === "doctor"
      ? { email: "doctor@velcare.com", password: "doctor123" }
      : { email: "patient@velcare.com", password: "patient123" };

  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(creds),
  });
  const data = await res.json();
  if (res.ok) {
    showToast(`Logged in as Demo ${type === "doctor" ? "Doctor" : "Patient"} (${data.user.name})`);
    await refreshAuth();
  }
}

// --- AI Medical Chatbot ---
function usePrompt(text) {
  const input = document.getElementById("chatInput");
  input.value = text;
  const form = document.getElementById("chatForm");
  if (typeof form.requestSubmit === "function") {
    form.requestSubmit();
  } else {
    sendChatMessage(new Event("submit", { cancelable: true }));
  }
}

async function loadChatHistory() {
  const res = await fetch("/api/chat/history");
  const data = await res.json();
  if (!data.messages || data.messages.length === 0) return;
  const container = document.getElementById("chatMessages");
  container.innerHTML = "";
  data.messages.forEach((m) => {
    appendChatBubble(m.sender, m.message, m.is_emergency === 1, m.intent);
  });
}

function showTypingIndicator() {
  const container = document.getElementById("chatMessages");
  const div = document.createElement("div");
  div.id = "typingIndicator";
  div.className = "msg assistant";
  div.innerHTML = `
    <div class="msg-meta">Virtual Medical Assistant • Analyzing...</div>
    <div class="typing-dots"><span></span><span></span><span></span></div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function removeTypingIndicator() {
  const el = document.getElementById("typingIndicator");
  if (el) el.remove();
}

async function sendChatMessage(e) {
  e.preventDefault();
  const input = document.getElementById("chatInput");
  const text = input.value.trim();
  if (!text) return;

  appendChatBubble("user", text, false, "user");
  input.value = "";

  const btn = document.getElementById("chatSendBtn");
  btn.disabled = true;
  btn.textContent = "Thinking...";
  showTypingIndicator();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        api_key: getSavedApiKey(),
        model: getSavedModel(),
      }),
    });
    const data = await res.json();
    removeTypingIndicator();
    if (!res.ok) {
      showToast(data.error || "Could not get response");
      return;
    }
    appendChatBubble("assistant", data.reply, data.is_emergency, data.source);
  } catch (err) {
    removeTypingIndicator();
    showToast("Network error while contacting AI assistant.");
  } finally {
    btn.disabled = false;
    btn.textContent = "Send";
  }
}

function appendChatBubble(sender, text, isEmergency, metaLabel) {
  const container = document.getElementById("chatMessages");
  const div = document.createElement("div");
  div.className = `msg ${sender} ${isEmergency ? "emergency" : ""}`;
  const label = sender === "user" ? "You" : metaLabel || "Virtual Medical Assistant";
  div.innerHTML = `
    <div class="msg-meta">${escapeHtml(label)}</div>
    <div class="msg-body">${formatMessage(text)}</div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

// --- Doctors & Appointments ---
async function loadDoctors() {
  const res = await fetch("/api/doctors");
  const data = await res.json();
  doctorsList = data.doctors || [];

  const select = document.getElementById("apptDoctor");
  select.innerHTML = doctorsList
    .map((d) => `<option value="${d.id}">${escapeHtml(d.name)} — ${escapeHtml(d.specialty)}</option>`)
    .join("");

  const grid = document.getElementById("doctorsGrid");
  grid.innerHTML = doctorsList
    .map(
      (d, idx) => `
      <div class="doctor-card" style="animation: fadeSlideUp 0.4s ease ${idx * 0.06}s backwards;">
        <div>
          <h4>${escapeHtml(d.name)}</h4>
          <div class="doc-spec">${escapeHtml(d.specialty)}</div>
          <div class="doc-meta">${escapeHtml(d.qualification)} • ${d.experience_years} yrs exp • ★ ${d.rating}</div>
          <p class="muted" style="margin-top:8px">${escapeHtml(d.bio)}</p>
        </div>
        <div>
          <div class="doc-meta" style="margin-bottom:10px">Available: ${escapeHtml(d.available_days)} (${escapeHtml(d.available_hours)})</div>
          <button class="btn btn-sm btn-primary btn-full" onclick="quickSelectDoctor(${d.id})">Book with ${escapeHtml(d.name.split(" ")[1] || d.name)}</button>
        </div>
      </div>
    `
    )
    .join("");
}

function quickSelectDoctor(doctorId) {
  showSection("appointments");
  document.getElementById("apptDoctor").value = doctorId;
}

async function bookAppointment(e) {
  e.preventDefault();
  if (!currentUser) {
    showToast("Please log in or register to book an appointment.");
    openAuthModal("login");
    return;
  }

  const payload = {
    doctor_id: Number(document.getElementById("apptDoctor").value),
    appointment_date: document.getElementById("apptDate").value,
    appointment_time: document.getElementById("apptTime").value,
    symptoms: document.getElementById("apptSymptoms").value,
  };

  const res = await fetch("/api/appointments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || "Failed to book appointment.");
    return;
  }
  document.getElementById("apptSymptoms").value = "";
  showToast("Appointment confirmed!");
  await loadAppointments();
}

async function loadAppointments() {
  if (!currentUser) return;
  const res = await fetch("/api/appointments");
  if (!res.ok) return;
  const data = await res.json();
  appointmentsList = data.appointments || [];

  renderAppointmentsList();
  renderReminderBanner();
  renderConsultationSelector();
}

function renderReminderBanner() {
  const banner = document.getElementById("reminderBanner");
  const upcoming = appointmentsList.find((a) => a.status === "Scheduled" || a.status === "In Progress");
  if (!upcoming) {
    banner.classList.add("hidden");
    return;
  }
  banner.classList.remove("hidden");
  banner.innerHTML = `<strong>Upcoming Appointment Reminder:</strong> ${escapeHtml(upcoming.doctor_name)} (${escapeHtml(upcoming.specialty)}) on <strong>${escapeHtml(upcoming.appointment_date)}</strong> at <strong>${escapeHtml(upcoming.appointment_time)}</strong>.`;
}

function renderAppointmentsList() {
  const listEl = document.getElementById("appointmentsList");
  const historyEl = document.getElementById("patientHistoryList");

  if (appointmentsList.length === 0) {
    const emptyHtml = `<p class="muted">No appointments found. Book one using the form.</p>`;
    listEl.innerHTML = emptyHtml;
    historyEl.innerHTML = emptyHtml;
    return;
  }

  const html = appointmentsList
    .map((a, idx) => {
      const statusClass = a.status.replace(/\s+/g, "");
      return `
      <div class="appt-item" style="animation-delay: ${idx * 0.05}s">
        <div class="appt-top">
          <strong>${escapeHtml(a.doctor_name)} (${escapeHtml(a.specialty)})</strong>
          <span class="status-pill ${statusClass}">${escapeHtml(a.status)}</span>
        </div>
        <div class="doc-meta">Date: ${escapeHtml(a.appointment_date)} • Time: ${escapeHtml(a.appointment_time)}</div>
        ${a.patient_name ? `<div class="doc-meta">Patient: ${escapeHtml(a.patient_name)} (Allergies: ${escapeHtml(a.allergies || "None")})</div>` : ""}
        ${a.symptoms ? `<div style="font-size:0.88rem; margin-top:4px;">Symptoms: ${escapeHtml(a.symptoms)}</div>` : ""}
        ${a.consultation_notes ? `<div style="font-size:0.86rem; margin-top:4px; color:var(--primary-dark)">Notes: ${escapeHtml(a.consultation_notes)}</div>` : ""}
        <div class="appt-actions">
          <button class="btn btn-sm btn-secondary" onclick="openConsultationFor(${a.id})">Open Consultation</button>
          ${a.status !== "Cancelled" && a.status !== "Completed" ? `<button class="btn btn-sm btn-outline" onclick="cancelAppointment(${a.id})">Cancel</button>` : ""}
        </div>
      </div>
    `;
    })
    .join("");

  listEl.innerHTML = html;
  historyEl.innerHTML = html;
}

async function cancelAppointment(apptId) {
  const res = await fetch(`/api/appointments/${apptId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: "Cancelled" }),
  });
  if (res.ok) {
    showToast("Appointment cancelled.");
    await loadAppointments();
  }
}

// --- Patient Profile ---
function populateProfileForm() {
  if (!currentUser) return;
  document.getElementById("profName").value = currentUser.name || "";
  document.getElementById("profPhone").value = currentUser.phone || "";
  document.getElementById("profAge").value = currentUser.age || "";
  document.getElementById("profGender").value = currentUser.gender || "";
  document.getElementById("profBlood").value = currentUser.blood_group || "";
  document.getElementById("profAllergies").value = currentUser.allergies || "";
  document.getElementById("profConditions").value = currentUser.chronic_conditions || "";
  document.getElementById("profMeds").value = currentUser.medications || "";
  document.getElementById("profEmergency").value = currentUser.emergency_contact || "";
}

async function saveProfile(e) {
  e.preventDefault();
  const payload = {
    name: document.getElementById("profName").value,
    phone: document.getElementById("profPhone").value,
    age: document.getElementById("profAge").value || null,
    gender: document.getElementById("profGender").value,
    blood_group: document.getElementById("profBlood").value,
    allergies: document.getElementById("profAllergies").value,
    chronic_conditions: document.getElementById("profConditions").value,
    medications: document.getElementById("profMeds").value,
    emergency_contact: document.getElementById("profEmergency").value,
  };
  const res = await fetch("/api/patient/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (res.ok) {
    currentUser = data.user;
    renderAuthUI();
    showToast("Patient health information saved!");
  } else {
    showToast(data.error || "Could not save profile.");
  }
}

// --- Doctor Consultation Room ---
function renderConsultationSelector() {
  const select = document.getElementById("consultApptSelect");
  if (!appointmentsList.length) {
    select.innerHTML = `<option value="">No appointments available</option>`;
    return;
  }
  select.innerHTML = appointmentsList
    .map((a) => `<option value="${a.id}">#${a.id} — ${escapeHtml(a.doctor_name)} (${a.appointment_date} ${a.appointment_time}) [${a.status}]</option>`)
    .join("");

  if (!activeConsultationId || !appointmentsList.some((a) => a.id === activeConsultationId)) {
    activeConsultationId = appointmentsList[0].id;
  }
  select.value = activeConsultationId;
  selectConsultation(activeConsultationId);
}

function openConsultationFor(apptId) {
  activeConsultationId = apptId;
  showSection("consultation");
}

async function selectConsultation(apptId) {
  activeConsultationId = Number(apptId);
  const appt = appointmentsList.find((a) => a.id === activeConsultationId);
  if (!appt) return;

  document.getElementById("consultDoctorName").textContent = appt.doctor_name;
  document.getElementById("consultDoctorSpec").textContent = `${appt.specialty} • ${appt.appointment_date} at ${appt.appointment_time}`;
  document.getElementById("consultDoctorAvatar").textContent = appt.doctor_name.split(" ").slice(0, 2).map((w) => w[0]).join("");
  document.getElementById("consultSubTitle").textContent = appt.symptoms ? `Reason: ${appt.symptoms}` : "Online Telemedicine Consultation";
  document.getElementById("consultNotesInput").value = appt.consultation_notes || "";

  const badge = document.getElementById("consultStatusBadge");
  badge.textContent = appt.status;
  badge.className = `status-pill ${appt.status.replace(/\s+/g, "")}`;

  await loadConsultationMessages(activeConsultationId);
}

async function loadConsultationMessages(apptId) {
  const res = await fetch(`/api/consultations/${apptId}/messages`);
  if (!res.ok) return;
  const data = await res.json();
  const box = document.getElementById("consultMessages");
  if (!data.messages.length) {
    box.innerHTML = `<p class="muted">No messages yet. Start the consultation conversation below.</p>`;
    return;
  }
  box.innerHTML = data.messages
    .map((m) => {
      const isMe = currentUser && m.sender_role === currentUser.role;
      return `
      <div class="msg ${isMe ? "user" : "assistant"}">
        <div class="msg-meta">${escapeHtml(m.sender_name)} (${escapeHtml(m.sender_role)}) • ${escapeHtml(m.created_at)}</div>
        <div class="msg-body">${escapeHtml(m.message)}</div>
      </div>
    `;
    })
    .join("");
  box.scrollTop = box.scrollHeight;
}

async function sendConsultMessage(e) {
  e.preventDefault();
  if (!activeConsultationId) {
    showToast("Select an appointment first.");
    return;
  }
  const input = document.getElementById("consultMsgInput");
  const message = input.value.trim();
  if (!message) return;

  const res = await fetch(`/api/consultations/${activeConsultationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (res.ok) {
    input.value = "";
    await loadConsultationMessages(activeConsultationId);
    await loadAppointments();
  }
}

async function markConsultationCompleted() {
  if (!activeConsultationId) return;
  const res = await fetch(`/api/appointments/${activeConsultationId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: "Completed" }),
  });
  if (res.ok) {
    showToast("Consultation marked as Completed.");
    await loadAppointments();
  }
}

async function saveConsultationNotes() {
  if (!activeConsultationId) return;
  const notes = document.getElementById("consultNotesInput").value;
  const res = await fetch(`/api/appointments/${activeConsultationId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ consultation_notes: notes }),
  });
  if (res.ok) {
    showToast("Consultation notes saved.");
    await loadAppointments();
  }
}

async function toggleVideoSimulation() {
  const btn = document.getElementById("toggleVideoBtn");
  const tag = document.getElementById("videoStateTag");
  const stage = document.getElementById("videoStage");
  const videoEl = document.getElementById("localVideo");

  if (localMediaStream || tag.textContent === "Live Consultation Active") {
    if (localMediaStream) {
      localMediaStream.getTracks().forEach((t) => t.stop());
      localMediaStream = null;
    }
    videoEl.classList.add("hidden");
    stage.classList.remove("live");
    tag.textContent = "Video Standby";
    btn.textContent = "Start Video Call";
    return;
  }

  stage.classList.add("live");
  tag.textContent = "Live Consultation Active";
  btn.textContent = "End Video Call";

  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    try {
      localMediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      videoEl.srcObject = localMediaStream;
      videoEl.classList.remove("hidden");
    } catch {
      // Camera permission denied or unavailable — simulated video room remains active
    }
  }
}

// --- Helpers ---
function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatMessage(str) {
  return escapeHtml(str)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/\n/g, "<br />");
}
