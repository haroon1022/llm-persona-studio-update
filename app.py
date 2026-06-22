from __future__ import annotations

import io
import os
import re
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd
import streamlit as st

from database import (
    get_all_projects,
    get_attachments_for_project,
    get_chat_logs_for_project,
    get_persona,
    get_personas_for_project,
    get_project,
    init_db,
    insert_attachment,
    insert_chat,
    insert_persona,
    insert_project,
    update_persona,
)
from llm_client import generate_persona_reply, has_openai_key
from prompt_engine import build_persona_prompt, generate_rule_based_personas, persona_consistency_rubric

# -----------------------------------------------------------------------------
# App configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="LLM Persona Studio",
    page_icon="🧩",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db()

FEEDBACK_FORM_URL = "https://forms.office.com/Pages/ResponsePage.aspx?id=OTEyrjoJKk2Bpl0zS82QGV34qXS2kE1IiMcEFqUpwmVUOFc0RFpZWDE3NDRWUTBYV0JBRVRaWlBJSC4u"
ALLOWED_ATTACHMENT_TYPES = ["png", "jpg", "jpeg", "pdf", "docx", "txt", "md"]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def secret_value(name: str, default: str = "") -> str:
    """Read a secret from Streamlit secrets or environment variables."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.getenv(name, default)


def ensure_state() -> None:
    defaults = {
        "page": "Home",
        "participant_code": "P-" + secrets.token_hex(4).upper(),
        "project_id": None,
        "project": None,
        "personas": [],
        "selected_persona_id": None,
        "chat_history": {},
        "chat_count": 0,
        "interacted_persona_ids": set(),
        "feedback_completed": False,
        "reminder_dismissed": False,
        "feedback_popup_shown": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def set_page(page: str) -> None:
    st.session_state.page = page
    st.rerun()


def refresh_personas() -> None:
    st.session_state.personas = get_personas_for_project(st.session_state.project_id)


def load_project_into_session(project_id: int, page: Optional[str] = None) -> None:
    """Load an existing project, its personas and chat logs into session state."""
    project = get_project(project_id)
    if not project:
        st.warning("This project could not be found.")
        return

    personas = get_personas_for_project(project_id)
    logs = get_chat_logs_for_project(project_id)

    chat_history: Dict[int, List[Dict[str, str]]] = {int(p["id"]): [] for p in personas}
    interacted: Set[int] = set()
    for log in logs:
        pid = int(log.get("persona_id"))
        if pid not in chat_history:
            chat_history[pid] = []
        chat_history[pid].append({"role": "user", "content": log.get("user_question", "")})
        chat_history[pid].append({"role": "assistant", "content": log.get("persona_response", "")})
        interacted.add(pid)

    st.session_state.project_id = project_id
    st.session_state.project = project
    st.session_state.personas = personas
    st.session_state.selected_persona_id = int(personas[0]["id"]) if personas else None
    st.session_state.chat_history = chat_history
    st.session_state.chat_count = len(logs)
    st.session_state.interacted_persona_ids = interacted
    st.session_state.feedback_popup_shown = False
    st.session_state.reminder_dismissed = False
    if page:
        st.session_state.page = page


def top_nav() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #f5f7fb 0%, #ffffff 55%);
        }
        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2.2rem;
            max-width: 1100px;
        }
        h1, h2, h3 {
            letter-spacing: -0.025em;
            color: #253047;
        }
        p, li, label, span {
            color: #344054;
        }
        .top-box {
            border: 1px solid #e3e8f2;
            border-radius: 20px;
            padding: 0.85rem;
            margin-bottom: 1.35rem;
            background: rgba(255, 255, 255, 0.96);
            box-shadow: 0 10px 28px rgba(16, 24, 40, 0.07);
        }
        .persona-card {
            border: 1px solid #e2e8f0;
            border-radius: 20px;
            padding: 1.1rem;
            margin-bottom: 1rem;
            background: linear-gradient(180deg, #ffffff 0%, #fbfcff 100%);
            min-height: 290px;
            box-shadow: 0 8px 24px rgba(16, 24, 40, 0.06);
        }
        .persona-card:hover {
            transform: translateY(-2px);
            transition: 0.15s ease-in-out;
            box-shadow: 0 14px 32px rgba(16, 24, 40, 0.10);
        }
        div[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f3f6fb 0%, #eef3f9 100%);
            border-right: 1px solid #e2e8f0;
        }
        .stButton > button, .stLinkButton > a {
            border-radius: 14px;
            font-weight: 650;
            border: 1px solid #d8e0ec;
            box-shadow: 0 3px 10px rgba(16, 24, 40, 0.05);
        }
        /* Force all Streamlit primary/red buttons to use white text.
           Covers st.button and st.form_submit_button across Streamlit versions. */
        div[data-testid="stButton"] button[kind="primary"],
        div[data-testid="stButton"] button[kind="primary"] *,
        div[data-testid="stFormSubmitButton"] button[kind="primary"],
        div[data-testid="stFormSubmitButton"] button[kind="primary"] *,
        button[kind="primary"],
        button[kind="primary"] *,
        button[data-testid="stBaseButton-primary"],
        button[data-testid="stBaseButton-primary"] *,
        button[data-testid="baseButton-primary"],
        button[data-testid="baseButton-primary"] *,
        [data-testid="stBaseButton-primary"],
        [data-testid="stBaseButton-primary"] *,
        [data-testid="baseButton-primary"],
        [data-testid="baseButton-primary"] * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        div[data-testid="stButton"] button[kind="primary"] p,
        div[data-testid="stFormSubmitButton"] button[kind="primary"] p,
        [data-testid="stBaseButton-primary"] p,
        [data-testid="baseButton-primary"] p {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        .st-key-start_project button,
        .st-key-generate_personas_button button,
        .st-key-save_attachments_button button {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        .st-key-start_project button *,
        .st-key-generate_personas_button button *,
        .st-key-save_attachments_button button * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        .st-key-feedback_popup_continue button,
        .st-key-feedback_popup_continue button * {
            color: #344054 !important;
            -webkit-text-fill-color: #344054 !important;
        }
        .stButton > button:hover, .stLinkButton > a:hover {
            border-color: #b9c8dc;
            box-shadow: 0 5px 14px rgba(16, 24, 40, 0.08);
        }
        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
            border-radius: 14px;
        }
        div[data-testid="stForm"] {
            border: 1px solid #e2e8f0;
            border-radius: 22px;
            padding: 1.2rem;
            background: rgba(255,255,255,0.90);
            box-shadow: 0 8px 22px rgba(16,24,40,0.045);
        }
        .muted-note {color: #667085; font-size: 0.92rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="top-box">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([1.0, 1.7, 1.2, 1.2])
    with col1:
        if st.button("Home", use_container_width=True):
            set_page("Home")
    with col2:
        if st.button("Project & Personas", use_container_width=True):
            set_page("Project")
    with col3:
        if st.button("Chat", use_container_width=True):
            set_page("Chat")
    with col4:
        st.link_button("Feedback", FEEDBACK_FORM_URL, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _feedback_popup_content() -> None:
    st.write(
        "You have interacted with multiple personas. Please complete the Microsoft Forms feedback questionnaire when you are ready. "
        "Your feedback will help evaluate the usefulness and usability of this tool."
    )
    c1, c2 = st.columns(2)
    with c1:
        st.link_button("Complete feedback now", FEEDBACK_FORM_URL, use_container_width=True)
    with c2:
        if st.button("Continue exploring", use_container_width=True, key="feedback_popup_continue"):
            st.session_state.reminder_dismissed = True
            st.rerun()


if hasattr(st, "dialog"):
    @st.dialog("Feedback reminder")
    def feedback_popup() -> None:
        _feedback_popup_content()
else:
    def feedback_popup() -> None:
        with st.container(border=True):
            st.info("Feedback reminder")
            _feedback_popup_content()


def maybe_feedback_reminder() -> None:
    """Show a pop-up reminder only after real interaction with personas."""
    if st.session_state.feedback_completed or st.session_state.reminder_dismissed:
        return
    if st.session_state.feedback_popup_shown:
        return
    enough_questions = st.session_state.chat_count >= 3
    enough_personas = len(st.session_state.interacted_persona_ids) >= 2
    if bool(st.session_state.personas) and enough_questions and enough_personas:
        st.session_state.feedback_popup_shown = True
        feedback_popup()


def get_current_project() -> Dict[str, Any]:
    if st.session_state.project:
        return st.session_state.project
    project = get_project(st.session_state.project_id)
    if project:
        st.session_state.project = project
    return project or {}


def get_current_persona() -> Dict[str, Any]:
    pid = st.session_state.selected_persona_id
    persona = get_persona(pid)
    if persona:
        return persona
    for p in st.session_state.personas:
        if p.get("id") == pid:
            return p
    return {}


def save_persona_edits(project: Dict[str, Any], persona_id: int, data: Dict[str, str]) -> None:
    data["system_prompt"] = build_persona_prompt(project, data)
    update_persona(persona_id, data)
    refresh_personas()


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", filename.strip())
    return cleaned or "uploaded_file"


def _extract_text_from_file(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    try:
        if suffix in {".txt", ".md"}:
            return data.decode("utf-8", errors="ignore")
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
            except Exception:
                return ""
            reader = PdfReader(io.BytesIO(data))
            pages = []
            for page in reader.pages[:8]:
                pages.append(page.extract_text() or "")
            return "\n".join(pages)
        if suffix == ".docx":
            try:
                from docx import Document
            except Exception:
                return ""
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        return ""
    return ""


def _save_project_attachment(project_id: int, uploaded_file: Any) -> int:
    data = uploaded_file.getvalue()
    safe_name = _safe_filename(uploaded_file.name)
    upload_dir = Path(__file__).with_name("uploads") / f"project_{project_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / f"{secrets.token_hex(4)}_{safe_name}"
    target.write_bytes(data)
    extracted_text = _extract_text_from_file(uploaded_file.name, data)
    file_type = "image" if (uploaded_file.type or "").startswith("image/") else "document"
    return insert_attachment(
        project_id=project_id,
        filename=uploaded_file.name,
        file_type=file_type,
        mime_type=uploaded_file.type or "",
        path=str(target),
        extracted_text=extracted_text[:12000],
    )


def render_project_attachments(project: Dict[str, Any]) -> None:
    project_id = int(project["id"])
    st.markdown("### Design images and documents")
    st.caption(
        "Attach design images or documents for this project. Do not upload files containing names, emails, confidential data or sensitive personal information."
    )

    attachments = get_attachments_for_project(project_id)
    if attachments:
        with st.expander("Attached files for this project", expanded=True):
            for item in attachments:
                st.write(f"**{item.get('filename')}** ({item.get('file_type')})")
                if str(item.get("mime_type", "")).startswith("image/") and Path(item.get("path", "")).exists():
                    st.image(item.get("path"), caption=item.get("filename"), use_column_width=True)
                elif item.get("extracted_text"):
                    st.caption("Text extracted and available for persona review.")
                else:
                    st.caption("File saved. Text preview is not available for this file type.")
    else:
        st.info("No design image or document has been attached to this project yet.")

    uploaded = st.file_uploader(
        "Attach design image or document",
        type=ALLOWED_ATTACHMENT_TYPES,
        accept_multiple_files=True,
        key=f"attachments_{project_id}",
        help="Supported files: PNG, JPG, PDF, DOCX, TXT and MD.",
    )
    if uploaded:
        if st.button("Save attachments", type="primary", key="save_attachments_button"):
            saved = 0
            for file in uploaded:
                _save_project_attachment(project_id, file)
                saved += 1
            st.success(f"{saved} attachment(s) saved for this project.")
            st.rerun()


def persona_edit_form(project: Dict[str, Any], persona: Dict[str, Any]) -> None:
    pid = int(persona["id"])
    with st.expander(f"Edit {persona.get('name', 'persona')}"):
        with st.form(f"edit_persona_{pid}"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Name", value=persona.get("name", ""), key=f"name_{pid}")
                user_group = st.text_input("User group", value=persona.get("user_group", ""), key=f"group_{pid}")
                age_group = st.text_input("Age group", value=persona.get("age_group", ""), key=f"age_{pid}")
                literacy_options = ["Very low", "Low", "Low to moderate", "Moderate", "Moderate to high", "High"]
                digital_literacy = st.selectbox(
                    "Digital literacy",
                    literacy_options,
                    index=literacy_options.index(persona.get("digital_literacy", "Moderate"))
                    if persona.get("digital_literacy", "Moderate") in literacy_options
                    else 3,
                    key=f"literacy_{pid}",
                )
                accessibility_need = st.text_input("Accessibility need", value=persona.get("accessibility_need", ""), key=f"access_{pid}")
            with c2:
                device = st.text_input("Main device", value=persona.get("device", ""), key=f"device_{pid}")
                language_preference = st.text_input("Language preference", value=persona.get("language_preference", ""), key=f"lang_{pid}")
                goal = st.text_area("Goal", value=persona.get("goal", ""), height=80, key=f"goal_{pid}")
                frustration = st.text_area("Main frustration", value=persona.get("frustration", ""), height=80, key=f"frustration_{pid}")
            context = st.text_area("Context of use", value=persona.get("context", ""), height=90, key=f"context_{pid}")
            saved = st.form_submit_button("Save persona changes")
        if saved:
            save_persona_edits(
                project,
                pid,
                {
                    "name": name,
                    "user_group": user_group,
                    "age_group": age_group,
                    "digital_literacy": digital_literacy,
                    "accessibility_need": accessibility_need,
                    "device": device,
                    "language_preference": language_preference,
                    "goal": goal,
                    "frustration": frustration,
                    "context": context,
                },
            )
            st.success("Persona updated.")
            st.rerun()


# -----------------------------------------------------------------------------
# Pages
# -----------------------------------------------------------------------------
def page_home() -> None:
    st.title("LLM Persona Studio")
    st.subheader("A project-based tool for generating and interacting with multiple personas for inclusive design")

    st.write(
        "Enter a design project, generate several personas, attach design images or documents if needed, "
        "and ask each persona questions about the design. The aim is to support early-stage reflection on user needs, "
        "accessibility barriers and inclusive design considerations."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### Project context")
        st.write("Describe the system or service you are designing.")
    with c2:
        st.markdown("### Multiple personas")
        st.write("Generate, review and edit several personas for that project.")
    with c3:
        st.markdown("### Persona chat")
        st.write("Ask design-related questions and compare perspectives.")

    st.markdown("### How the system works")
    st.markdown(
        """
        1. Enter a project or design context.
        2. Generate multiple personas for that project.
        3. Optionally attach design images or documents.
        4. Review and edit the personas if needed.
        5. Select a persona and ask design-related questions.
        6. Compare how different personas respond to the same design task.
        """
    )

    st.warning(
        "Ethical note: generated personas are simulated viewpoints. They should be used for reflection and hypothesis generation, not as evidence that replaces real users."
    )

    if st.button("Start by creating a project", type="primary", key="start_project"):
        set_page("Project")


def page_project() -> None:
    st.title("Project Setup and Personas")
    st.write("Enter a project/design context. The system will suggest three editable personas related to that project.")

    with st.form("project_form"):
        title = st.text_input("Project title", placeholder="e.g. Mobile app for booking GP appointments")
        description = st.text_area(
            "Project description / design context",
            placeholder="Briefly describe the system, expected users and main purpose.",
            height=120,
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            platform = st.selectbox("Platform", ["Mobile app", "Website", "Web app", "Kiosk", "Service", "Other"])
        with c2:
            domain = st.selectbox("Domain", ["Healthcare", "Education", "Finance", "Public service", "E-commerce", "Travel", "Other"])
        with c3:
            target_task = st.text_input("Main user task", placeholder="e.g. book an appointment")
        submitted = st.form_submit_button("Generate multiple personas", type="primary", key="generate_personas_button")

    if submitted:
        if not title.strip() or not description.strip() or not target_task.strip():
            st.error("Please complete project title, description and main task before generating personas.")
            return
        project_id = insert_project(title.strip(), description.strip(), platform, domain, target_task.strip())
        project = {
            "id": project_id,
            "title": title.strip(),
            "description": description.strip(),
            "platform": platform,
            "domain": domain,
            "target_task": target_task.strip(),
        }
        generated = generate_rule_based_personas(project)
        saved_personas: List[Dict[str, Any]] = []
        for persona in generated:
            persona_id = insert_persona(project_id, persona)
            persona["id"] = persona_id
            persona["project_id"] = project_id
            saved_personas.append(persona)

        st.session_state.project_id = project_id
        st.session_state.project = project
        st.session_state.personas = saved_personas
        st.session_state.selected_persona_id = saved_personas[0]["id"]
        st.session_state.chat_history = {int(p["id"]): [] for p in saved_personas}
        st.session_state.chat_count = 0
        st.session_state.interacted_persona_ids = set()
        st.session_state.reminder_dismissed = False
        st.session_state.feedback_popup_shown = False
        st.success("Three project-specific personas have been generated. You can edit them before chatting.")

    project = get_current_project()
    if project and st.session_state.personas:
        st.markdown("### Current project")
        st.info(f"**{project.get('title')}** — {project.get('target_task')} ({project.get('platform')}, {project.get('domain')})")

        render_project_attachments(project)

        st.markdown("### Suggested personas")
        st.caption("These are starting points. Edit them if your design case needs different user characteristics.")
        cols = st.columns(3)
        for idx, persona in enumerate(st.session_state.personas):
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"#### {persona.get('name')}")
                    st.write(f"**User group:** {persona.get('user_group')}")
                    st.write(f"**Age group:** {persona.get('age_group')}")
                    st.write(f"**Digital literacy:** {persona.get('digital_literacy')}")
                    st.write(f"**Accessibility need:** {persona.get('accessibility_need')}")
                    st.write(f"**Goal:** {persona.get('goal')}")
                    if st.button(f"Chat with {persona.get('name')}", key=f"chat_{persona.get('id')}", use_container_width=True):
                        st.session_state.selected_persona_id = int(persona.get("id"))
                        set_page("Chat")

        st.markdown("### Edit personas")
        for persona in st.session_state.personas:
            persona_edit_form(project, persona)

        st.markdown("### Add a custom persona")
        with st.expander("Create an additional persona manually"):
            with st.form("custom_persona_form"):
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Name", placeholder="e.g. Farah")
                    user_group = st.text_input("User group", placeholder="e.g. International student with limited confidence using university systems")
                    age_group = st.text_input("Age group", placeholder="e.g. 25-34")
                    digital_literacy = st.selectbox("Digital literacy", ["Very low", "Low", "Low to moderate", "Moderate", "Moderate to high", "High"], key="custom_lit")
                    accessibility_need = st.text_input("Accessibility need", placeholder="e.g. Plain language and predictable navigation")
                with c2:
                    device = st.text_input("Main device", placeholder="e.g. smartphone")
                    language_preference = st.text_input("Language preference", placeholder="e.g. simple English")
                    goal = st.text_area("Goal", placeholder="What does this persona want to do?", height=80)
                    frustration = st.text_area("Main frustration", placeholder="What barriers might this persona face?", height=80)
                context = st.text_area("Context of use", placeholder="Where and how might this persona use the system?", height=90)
                add = st.form_submit_button("Add custom persona")
            if add:
                if not name.strip() or not user_group.strip():
                    st.error("Please provide at least a name and user group.")
                else:
                    custom = {
                        "name": name.strip(),
                        "user_group": user_group.strip(),
                        "age_group": age_group.strip(),
                        "digital_literacy": digital_literacy,
                        "accessibility_need": accessibility_need.strip(),
                        "device": device.strip(),
                        "language_preference": language_preference.strip(),
                        "goal": goal.strip(),
                        "frustration": frustration.strip(),
                        "context": context.strip(),
                    }
                    custom["system_prompt"] = build_persona_prompt(project, custom)
                    insert_persona(int(project["id"]), custom)
                    refresh_personas()
                    st.success("Custom persona added.")
                    st.rerun()

        with st.expander("Persona-consistency rubric used for manual analysis"):
            st.dataframe(pd.DataFrame(persona_consistency_rubric()), use_container_width=True, hide_index=True)


def page_chat() -> None:
    st.title("Chat with Personas")
    project = get_current_project()
    if not project or not st.session_state.personas:
        st.warning("Please create a project and generate personas first.")
        if st.button("Go to Project Setup"):
            set_page("Project")
        return

    st.markdown(f"**Current project:** {project.get('title')}")
    st.caption(project.get("description", ""))

    attachments = get_attachments_for_project(int(project["id"]))
    if attachments:
        with st.expander("Project attachments available to personas", expanded=False):
            for item in attachments:
                st.write(f"- **{item.get('filename')}** ({item.get('file_type')})")
            st.caption("When you ask a question, the selected persona can use these attached design images/documents as context.")

    persona_options = {f"{p.get('name')} — {p.get('user_group')}": int(p.get("id")) for p in st.session_state.personas}
    selected_label = st.selectbox("Select a persona", list(persona_options.keys()))
    st.session_state.selected_persona_id = persona_options[selected_label]
    persona = get_current_persona()

    with st.expander("Selected persona details", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**Name:** {persona.get('name')}")
            st.write(f"**User group:** {persona.get('user_group')}")
            st.write(f"**Age group:** {persona.get('age_group')}")
            st.write(f"**Digital literacy:** {persona.get('digital_literacy')}")
        with c2:
            st.write(f"**Accessibility need:** {persona.get('accessibility_need')}")
            st.write(f"**Device:** {persona.get('device')}")
            st.write(f"**Goal:** {persona.get('goal')}")
            st.write(f"**Frustration:** {persona.get('frustration')}")

    pid = int(persona.get("id"))
    if pid not in st.session_state.chat_history:
        st.session_state.chat_history[pid] = []

    st.markdown("### Ask design-related questions")
    suggested = st.selectbox(
        "Optional suggested question",
        [
            "",
            "What would you find difficult about this design?",
            "Which part of this process might confuse you?",
            "What would make this interface easier for you to use?",
            "Would the language and instructions be clear for you?",
            "What accessibility barriers might you experience?",
            "Based on the attached design image or document, what problems might you face?",
            "Please review the attached design/document from your persona perspective.",
        ],
    )
    if suggested and st.button("Ask suggested question"):
        st.session_state.pending_question = suggested
        st.rerun()

    st.markdown("### Conversation")
    for msg in st.session_state.chat_history[pid]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    default_q = st.session_state.pop("pending_question", "") if "pending_question" in st.session_state else ""
    user_question = st.chat_input("Ask this persona about the project, design, or attached files")
    if not user_question and default_q:
        user_question = default_q

    if user_question:
        st.session_state.chat_history[pid].append({"role": "user", "content": user_question})
        api_key = secret_value("OPENAI_API_KEY")
        model = secret_value("OPENAI_MODEL", "gpt-4o-mini")
        response = generate_persona_reply(
            project=project,
            persona=persona,
            user_question=user_question,
            history=st.session_state.chat_history[pid][:-1],
            api_key=api_key,
            model=model,
            attachments=attachments,
        )
        st.session_state.chat_history[pid].append({"role": "assistant", "content": response})
        st.session_state.chat_count += 1
        st.session_state.interacted_persona_ids.add(pid)
        insert_chat(int(project["id"]), pid, user_question, response)
        st.rerun()

    if not has_openai_key(secret_value("OPENAI_API_KEY")):
        st.info("Demo mode is active because no LLM API key is configured. Add OPENAI_API_KEY in Streamlit secrets to enable live LLM responses. In demo mode, uploaded image content is not visually analysed.")


def page_feedback() -> None:
    st.title("Feedback")
    st.write("Please complete the project evaluation questionnaire using Microsoft Forms.")
    st.link_button("Open Microsoft Forms questionnaire", FEEDBACK_FORM_URL, use_container_width=True)


# -----------------------------------------------------------------------------
# Main routing
# -----------------------------------------------------------------------------
ensure_state()
top_nav()
maybe_feedback_reminder()

with st.sidebar:
    st.header("LLM Persona Studio")
    st.write(f"Current page: **{st.session_state.page}**")
    st.divider()
    st.write("Core flow")
    st.markdown("Project → Multiple personas → Chat → Feedback")
    st.divider()
    st.markdown("### Projects")
    if st.button("+ New project", use_container_width=True):
        st.session_state.project_id = None
        st.session_state.project = None
        st.session_state.personas = []
        st.session_state.selected_persona_id = None
        st.session_state.chat_history = {}
        set_page("Project")

    projects = get_all_projects()
    if projects:
        for project_item in projects:
            title = str(project_item.get("title", "Untitled project"))
            label = title if len(title) <= 36 else title[:33] + "..."
            active = " ✓" if st.session_state.project_id == project_item.get("id") else ""
            if st.button(f"{label}{active}", key=f"sidebar_project_{project_item.get('id')}", use_container_width=True):
                load_project_into_session(int(project_item["id"]), page=st.session_state.page if st.session_state.page in {"Project", "Chat"} else "Project")
                st.rerun()
    else:
        st.caption("No projects yet.")
    st.divider()
    st.caption("Create and interact with personas for one or more design projects.")

page = st.session_state.page
if page == "Home":
    page_home()
elif page == "Project":
    page_project()
elif page == "Chat":
    page_chat()
elif page == "Feedback":
    page_feedback()
else:
    page_home()
