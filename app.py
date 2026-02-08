"""
Personal AI Career & Clarity Coach - Powered by your Notion notes.
Run: streamlit run app.py

Login with Gmail. 10 prompts per user per day.
"""
# Patch Authlib to handle session=None (Streamlit passes None; base class fails)
from auth_patch import apply as _apply_auth_patch

_apply_auth_patch()

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Sync Streamlit Cloud secrets to env (so rag.py's os.getenv works)
if hasattr(st, "secrets"):
    for key in ("OPENAI_API_KEY", "NOTION_API_KEY", "NOTION_PAGE_IDS"):
        if key in st.secrets and st.secrets.get(key):
            os.environ[key] = str(st.secrets[key])

# Validate: OpenAI key should start with sk- (catches accidental swap with Notion key)
_openai = os.getenv("OPENAI_API_KEY", "")
if _openai and not _openai.startswith("sk-"):
    st.error(
        "**API key error:** `OPENAI_API_KEY` should be your **OpenAI** key (starts with `sk-`), "
        "not your Notion key. In Streamlit Cloud → Manage app → Secrets, ensure OPENAI_API_KEY has the key from platform.openai.com"
    )

# Catch auth config errors and show a helpful message
try:
    from streamlit.errors import StreamlitAuthError
except ImportError:
    StreamlitAuthError = Exception  # fallback for older streamlit

# Design tokens
COLORS = {
    "cream": "#f8f6f3",
    "text": "#2d2d2d",
    "text_light": "#5a5a5a",
    "accent": "#6bb3d0",
    "accent_hover": "#5a9fbd",
    "white": "#ffffff",
}

st.set_page_config(
    page_title="Kessie Zhang AI",
    page_icon="💁🏻‍♀️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(f"""
<style>
    .stApp {{ background: {COLORS["cream"]} !important; }}
    .hero-title {{ font-size: 2rem; font-weight: 600; color: {COLORS["text"]}; }}
    .hero-title .accent {{ color: {COLORS["accent"]}; }}
    .hero-subtitle {{ color: {COLORS["text_light"]}; font-size: 1.05rem; }}
    .info-card {{
        background: {COLORS["white"]};
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
        min-height: 180px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        border: 1px solid rgba(0,0,0,0.04);
    }}
    .info-card h4 {{ color: {COLORS["text"]} !important; font-size: 1rem; margin-bottom: 0.75rem; }}
    .info-card ul {{ margin: 0; padding-left: 1.2rem; color: {COLORS["text_light"]}; font-size: 0.95rem; line-height: 1.7; }}
    .info-card li::marker {{ color: {COLORS["accent"]}; }}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_rag():
    from rag import load_vector_store, build_rag_chain, DEFAULT_PERSIST_DIR
    if not Path(DEFAULT_PERSIST_DIR).exists():
        return None
    vs = load_vector_store(persist_directory=DEFAULT_PERSIST_DIR)
    return build_rag_chain(vs, k=8)


def get_answer(question: str) -> str:
    chain = get_rag()
    if chain is None:
        return "⚠️ No knowledge base found. Run ingest first to index your Notion notes."
    try:
        return chain.invoke(question).content
    except Exception as e:
        return f"Sorry, something went wrong: {str(e)}"


WELCOME_MSG = """Welcome — I'm really glad you're here. ✨

Whether you're feeling stuck, thinking about your next career move, or figuring out how to stay ahead in the AI era, I'm here to help you find clarity and move forward with confidence.

What's on your mind today?"""

SUGGESTED_PROMPTS = [
    "I feel stuck in my career",
    "I want to plan my next move",
    "I feel behind in AI",
    "I'm overthinking a decision",
]

DAILY_LIMIT_MSG = """You've used your 10 prompts for today. ✨

Come back tomorrow for more — your daily limit resets at midnight."""


def _try_send_prompt(email: str, prompt: str):
    """Returns (success, response_or_error)."""
    from usage_store import get_usage, increment_usage

    used, can_send = get_usage(email)
    if not can_send:
        return False, DAILY_LIMIT_MSG
    answer = get_answer(prompt)
    increment_usage(email)
    return True, answer


def _login_screen():
    st.markdown(
        '<p class="hero-title">Think clearer. Move forward with <span class="accent">confidence.</span></p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="hero-subtitle">Your personal AI career and clarity coach — here to help you navigate decisions, build confidence, and stay ahead in the AI era.</p>',
        unsafe_allow_html=True,
    )

    # Three pillar info cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="info-card">
            <h4>✨ Built by Kessie</h4>
            <ul>
                <li>What should my next move be?</li>
                <li>How to get unstuck?</li>
                <li>How do I stay competitive?</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="info-card">
            <h4>Confidence & Overthinking</h4>
            <ul>
                <li>Breaking decision paralysis</li>
                <li>Building confidence</li>
                <li>Handling career doubts</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="info-card">
            <h4>AI & Career Growth</h4>
            <ul>
                <li>Using AI to grow faster at work</li>
                <li>Staying competitive in tech</li>
                <li>Planning future skills</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Sign in to try the AI coach")
    st.markdown("Sign in to try the AI coach — **10 prompts per day**.")
    if st.button("Log in with Google", type="primary"):
        st.login()


def main():
    try:
        is_logged_in = st.user.is_logged_in
    except (AttributeError, KeyError):
        _login_screen()
        return

    if not is_logged_in:
        _login_screen()
        return

    # Safely get email/name (OIDC claim names can vary)
    email = getattr(st.user, "email", None) or getattr(st.user, "preferred_username", None) or "unknown"
    name = getattr(st.user, "name", None) or (email.split("@")[0] if "@" in email else "Guest")
    from usage_store import get_usage, DAILY_LIMIT

    used, can_send = get_usage(email)
    remaining = max(0, DAILY_LIMIT - used)

    with st.sidebar:
        if st.button("Log out"):
            st.logout()
        st.caption(f"Hi, {name}!")
        st.caption(f"Prompts today: {used}/{DAILY_LIMIT}")

    st.markdown(
        '<p class="hero-title">Think clearer. Move forward with <span class="accent">confidence.</span></p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="hero-subtitle">Your personal AI career and clarity coach.</p>',
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown("### Start a conversation")
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": WELCOME_MSG}]
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None

    # Handle new input: append user message and set pending for next rerun
    prompt = st.chat_input("Feel free to share." if can_send else "Daily limit reached — try again tomorrow")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.pending_prompt = prompt
        st.rerun()

    # Render all messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="✨" if msg["role"] == "assistant" else "🧑‍💻"):
            st.markdown(msg["content"])

    # If we have a pending prompt, show typing indicator, fetch, then update
    if st.session_state.pending_prompt:
        pending = st.session_state.pending_prompt
        st.session_state.pending_prompt = None  # Clear before blocking call
        with st.chat_message("assistant", avatar="✨"):
            placeholder = st.empty()
            placeholder.markdown("⌛ Thinking...")
            try:
                ok, response = _try_send_prompt(email, pending)
                placeholder.markdown(response)
            except Exception as e:
                placeholder.markdown(f"Sorry, something went wrong: {str(e)}")
                response = f"Sorry, something went wrong: {str(e)}"
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

    # Suggested prompts: same flow — append user, set pending, rerun
    st.markdown("**Try asking:**")
    prompt_cols = st.columns(4)
    for i, p in enumerate(SUGGESTED_PROMPTS):
        with prompt_cols[i % 4]:
            disabled = not can_send
            if st.button(p, key=f"prompt_{i}", use_container_width=True, disabled=disabled):
                st.session_state.messages.append({"role": "user", "content": p})
                st.session_state.pending_prompt = p
                st.rerun()

    if not can_send:
        st.info("You've used your 10 prompts for today. Come back tomorrow for more! ✨")


if __name__ == "__main__":
    try:
        main()
    except StreamlitAuthError:
        st.error(
            "**Auth configuration error.** Add secrets in Streamlit Cloud (Manage app → Settings → Secrets). "
            "`redirect_uri` must match your app URL, e.g. `https://yourapp.streamlit.app/oauth2callback`. "
            "See DEPLOY.md for full setup."
        )
