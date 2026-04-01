import streamlit as st
import urllib.parse
import json
import os
import uuid
from PyPDF2 import PdfReader
from docx import Document
from pydantic import BaseModel
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

# =========================
# 🔐 LOAD ENV VARIABLES
# =========================
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("❌ GROQ_API_KEY not found. Please check your .env file.")
    st.stop()

# =========================
# ⚙️ CONFIG
# =========================
st.set_page_config(page_title="AI Mail Engine", page_icon="✉️", layout="centered")

# =========================
# 🎨 CSS
# =========================
st.markdown("""
<style>
    *:focus { outline: none !important; }

    .email-card {
        background-color: #1F2937; 
        padding: 25px; 
        border-radius: 12px; 
        border-left: 5px solid #00B4D8; 
    }

    .page-counter { 
        text-align: center; 
        padding-top: 8px; 
        font-weight: bold; 
        color: #00B4D8; 
    }
</style>
""", unsafe_allow_html=True)

# =========================
# 🤖 MODEL
# =========================
class EmailOutput(BaseModel):
    subject: str
    body: str

llm = ChatGroq(
    temperature=0.6,
    model_name="llama-3.3-70b-versatile",
    api_key=api_key
)

structured_llm = llm.with_structured_output(EmailOutput)

# =========================
# 🧹 HELPERS
# =========================
def clean_for_gmail(text: str) -> str:
    return text.replace("**", "").replace("### ", "").replace("\n* ", "\n• ").replace("\n- ", "\n• ")

def extract_text_from_file(uploaded_file):
    try:
        if uploaded_file.type == "application/pdf":
            reader = PdfReader(uploaded_file)
            return " ".join([page.extract_text() for page in reader.pages])

        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = Document(uploaded_file)
            return " ".join([para.text for para in doc.paragraphs])

        else:
            return str(uploaded_file.read(), "utf-8")

    except Exception as e:
        return f"Error reading file: {str(e)}"

# =========================
# 💾 DATABASE
# =========================
DB_FILE = "saved_emails.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# =========================
# 🧠 SESSION
# =========================
if "db" not in st.session_state:
    st.session_state.db = load_db()

if "current_id" not in st.session_state:
    st.session_state.current_id = None

# =========================
# 📚 SIDEBAR
# =========================
with st.sidebar:
    st.markdown("### 🗂️ Inbox History")

    if st.button("➕ Create New Draft", use_container_width=True, type="primary"):
        st.session_state.current_id = None
        st.rerun()

    st.divider()

    for email_id, email_data in reversed(st.session_state.db.items()):
        col1, col2 = st.columns([8, 2])
        display_title = email_data['title'][:20] + "..." if len(email_data['title']) > 20 else email_data['title']

        with col1:
            if st.button(f"✉️ {display_title}", key=f"load_{email_id}", use_container_width=True):
                st.session_state.current_id = email_id
                st.rerun()

        with col2:
            with st.popover("⋮", use_container_width=True):
                new_title = st.text_input("Rename", value=email_data['title'], key=f"input_{email_id}")

                if st.button("💾 Save", key=f"save_{email_id}", use_container_width=True):
                    st.session_state.db[email_id]['title'] = new_title
                    save_db(st.session_state.db)
                    st.rerun()

                if st.button("🗑️ Delete", key=f"del_{email_id}", use_container_width=True):
                    del st.session_state.db[email_id]
                    if st.session_state.current_id == email_id:
                        st.session_state.current_id = None
                    save_db(st.session_state.db)
                    st.rerun()

# =========================
# 🖥️ MAIN
# =========================
st.markdown("<h1 style='text-align: center;'>✉️ Mail Engine</h1>", unsafe_allow_html=True)

is_new_email = st.session_state.current_id is None

# =========================
# ✍️ COMPOSE MODE
# =========================
if is_new_email:
    st.markdown("### 📝 Compose Mail")

    with st.container(border=True):
        with st.form("email_generator_form"):

            col_a, col_b = st.columns(2)
            with col_a:
                sender_input = st.text_input("👤 From", placeholder="e.g., Alex")
            with col_b:
                recipient_input = st.text_input("🎯 To", placeholder="e.g., marketing@oneplus.com")

            col_c, col_d = st.columns(2)
            with col_c:
                tone_choice = st.selectbox("🎭 Select Tone",
                    ["Professional", "Casual", "Urgent", "Persuasive", "Enthusiastic", "Apologetic"])
            with col_d:
                length_choice = st.selectbox("📏 Select Length",
                    ["Concise (Short)", "Standard", "Detailed (Long)"])

            uploaded_file = st.file_uploader("📂 Attach Context (PDF, Docx, or TXT)", type=["pdf", "docx", "txt"])

            subject_input = st.text_input("📌 Subject Idea")
            description_input = st.text_area("🧠 Key Points", height=120)

            submitted = st.form_submit_button("✨ Generate", use_container_width=True)

        if submitted:
            if not all([sender_input, recipient_input, subject_input, description_input]):
                st.warning("⚠️ Please fill out all required fields.")
            else:
                file_context = extract_text_from_file(uploaded_file) if uploaded_file else ""

                with st.spinner("Generating..."):
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", """You are an expert copywriter.
                        Tone: {tone}. Length: {length}.
                        Use \\n\\n for spacing.
                        Include greeting and sign-off."""),
                        ("human", "From: {sender}\nTo: {recipient}\nSubject: {subject}\n\nPoints: {description}\n\nContext: {context}")
                    ])

                    res = (prompt | structured_llm).invoke({
                        "sender": sender_input,
                        "recipient": recipient_input,
                        "subject": subject_input,
                        "description": description_input,
                        "tone": tone_choice,
                        "length": length_choice,
                        "context": file_context
                    })

                    new_id = str(uuid.uuid4())

                    st.session_state.db[new_id] = {
                        "title": res.subject,
                        "recipient": recipient_input,
                        "drafts": [{"subject": res.subject, "body": res.body}],
                        "current_page": 0
                    }

                    save_db(st.session_state.db)
                    st.session_state.current_id = new_id
                    st.rerun()

# =========================
# 👁️ REVIEW MODE
# =========================
else:
    st.markdown("### 👁️ Review & Refine")

    thread = st.session_state.db[st.session_state.current_id]
    current_idx = thread["current_page"]
    current_draft = thread["drafts"][current_idx]

    nav_col1, nav_col2, nav_col3, gmail_col = st.columns([1, 1.5, 1, 4])

    with nav_col1:
        if st.button("◀", disabled=(current_idx == 0), key=f"prev_{st.session_state.current_id}"):
            thread["current_page"] -= 1
            save_db(st.session_state.db)
            st.rerun()

    with nav_col2:
        st.markdown(f"<div class='page-counter'>{current_idx + 1} / {len(thread['drafts'])}</div>", unsafe_allow_html=True)

    with nav_col3:
        if st.button("▶", disabled=(current_idx == len(thread["drafts"]) - 1), key=f"next_{st.session_state.current_id}"):
            thread["current_page"] += 1
            save_db(st.session_state.db)
            st.rerun()

    with gmail_col:
        gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={urllib.parse.quote(thread['recipient'])}&su={urllib.parse.quote(current_draft['subject'])}&body={urllib.parse.quote(clean_for_gmail(current_draft['body']))}"
        st.link_button("📤 Open in Gmail", gmail_url, type="primary", use_container_width=True)

    with st.container(border=True):
        st.markdown(f"### {current_draft['subject']}")
        st.divider()
        st.markdown(current_draft["body"])

    st.caption("Not quite right? Ask the AI to tweak this version.")

    # ✅ FIXED UNIQUE KEY
    if instruction := st.chat_input("Suggest changes...", key=f"chat_{st.session_state.current_id}"):
        with st.spinner("Refining..."):
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Expert editor. Use \\n\\n spacing."),
                ("human", "SUB: {s}\nBODY: {b}\nCHANGE: {c}")
            ])

            new_res = (prompt | structured_llm).invoke({
                "s": current_draft["subject"],
                "b": current_draft["body"],
                "c": instruction
            })

            thread["drafts"] = thread["drafts"][:current_idx + 1]
            thread["drafts"].append({
                "subject": new_res.subject,
                "body": new_res.body
            })

            thread["current_page"] = len(thread["drafts"]) - 1
            save_db(st.session_state.db)
            st.rerun()