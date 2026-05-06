from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Test", layout="wide")
st.write("ok")

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import pandas as pd
import streamlit as st


Role = Literal["user", "assistant"]
Page = Literal["💬 WhatsApp Simülasyonu", "📊 Admin Dashboard"]


SYSTEM_PROMPT = (
    "Sen bir Hediyelik Eşya ve Kozmetik Dükkanının akıllı WhatsApp sipariş asistanı "
    "OrderFlow AI'sın. Müşteriyle çok doğal, kısa ve kibar bir dille konuş. "
    "Müşteri sipariş verdiğinde (Limon Kolonyası, El Kremi, Zeytinyağlı Sabun vb.) "
    "niyeti anla, ürünleri teyit et ve siparişi aldığına dair bir cevap dön."
)


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str
    ts: str


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_env() -> None:
    """Load `.env` into environment (best-effort)."""
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(override=False)
        return
    except Exception:
        pass

    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


@st.cache_resource(show_spinner=False)
def get_gemini_model() -> Any:
    load_env()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY bulunamadı. Proje köküne `.env` ekleyip "
            "`GEMINI_API_KEY=...` şeklinde tanımlayın."
        )

    try:
        import google.generativeai as genai  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "`google-generativeai` kütüphanesi bulunamadı. Kurulum için: "
            "`pip install google-generativeai`"
        ) from e

    genai.configure(api_key=api_key)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash").strip()

    try:
        return genai.GenerativeModel(model_name=model_name, system_instruction=SYSTEM_PROMPT)
    except TypeError:
        return genai.GenerativeModel(model_name=model_name)


def ensure_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            ChatMessage(
                role="assistant",
                content=(
                    "Merhaba! Ben OrderFlow AI.\n\n"
                    "Sipariş vermek istediğiniz ürünleri ve varsa adresinizi yazabilirsiniz."
                ),
                ts=now_ts(),
            )
        ]


def to_gemini_history(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for m in messages:
        role = "user" if m.role == "user" else "model"
        history.append({"role": role, "parts": [m.content]})
    return history


def gemini_reply(user_text: str, messages: list[ChatMessage]) -> str:
    model = get_gemini_model()
    history = to_gemini_history(messages[:-1])

    try:
        chat = model.start_chat(history=history)
        resp = chat.send_message(user_text)
        text = getattr(resp, "text", None)
        return str(text).strip() if text else "Şu an yanıt oluşturamadım. Lütfen tekrar dener misiniz?"
    except Exception:
        prompt = f"{SYSTEM_PROMPT}\n\nMüşteri mesajı:\n{user_text}"
        resp = model.generate_content(prompt)
        text = getattr(resp, "text", None)
        return str(text).strip() if text else "Şu an yanıt oluşturamadım. Lütfen tekrar dener misiniz?"


def render_sidebar() -> Page:
    st.sidebar.title("OrderFlow AI")
    st.sidebar.caption("Hediyelik Eşya & Kozmetik")
    page: Page = st.sidebar.radio(
        "Menü",
        options=["💬 WhatsApp Simülasyonu", "📊 Admin Dashboard"],
        index=0,
    )
    st.sidebar.divider()
    st.sidebar.markdown("**Env**: `.env` → `GEMINI_API_KEY=...`")
    return page


def render_whatsapp_page() -> None:
    st.title("💬 WhatsApp Simülasyonu")
    st.caption("Gerçekçi chat UI (`st.chat_message` + `st.chat_input`) + Gemini.")

    for m in st.session_state.messages:
        with st.chat_message(m.role):
            st.markdown(m.content)
            st.caption(m.ts)

    user_text = st.chat_input("Mesaj yaz…")
    if not user_text:
        return

    st.session_state.messages.append(ChatMessage(role="user", content=user_text, ts=now_ts()))

    with st.chat_message("assistant"):
        with st.spinner("Yanıt hazırlanıyor…"):
            try:
                reply = gemini_reply(user_text, st.session_state.messages)
            except Exception as e:
                reply = f"Konfigürasyon hatası: {e}"
        st.markdown(reply)
        st.caption(now_ts())

    st.session_state.messages.append(ChatMessage(role="assistant", content=reply, ts=now_ts()))
    st.rerun()


def render_admin_dashboard_page() -> None:
    st.title("📊 Admin Dashboard")
    st.caption("Mock sipariş akışı kaldırıldı. Bu sayfa sohbet geçmişini listeler.")

    messages: list[ChatMessage] = st.session_state.messages
    total = len(messages)
    user_count = sum(1 for m in messages if m.role == "user")
    assistant_count = sum(1 for m in messages if m.role == "assistant")

    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Mesaj", f"{total}")
    c2.metric("Müşteri", f"{user_count}")
    c3.metric("Asistan", f"{assistant_count}")

    st.divider()
    df = pd.DataFrame(
        [{"Zaman": m.ts, "Rol": ("Müşteri" if m.role == "user" else "Asistan"), "İçerik": m.content} for m in messages]
    )
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Zaman": st.column_config.TextColumn(),
            "Rol": st.column_config.TextColumn(),
            "İçerik": st.column_config.TextColumn(width="large"),
        },
    )


def main() -> None:
    st.set_page_config(
        page_title="OrderFlow AI — Hediyelik & Kozmetik",
        page_icon="🧴",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    ensure_session_state()
    page = render_sidebar()

    if page == "💬 WhatsApp Simülasyonu":
        render_whatsapp_page()
    else:
        render_admin_dashboard_page()


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import pandas as pd
import streamlit as st


Role = Literal["user", "assistant"]
Page = Literal["💬 WhatsApp Simülasyonu", "📊 Admin Dashboard"]


SYSTEM_PROMPT = (
    "Sen bir Hediyelik Eşya ve Kozmetik Dükkanının akıllı WhatsApp sipariş asistanı "
    "OrderFlow AI'sın. Müşteriyle çok doğal, kısa ve kibar bir dille konuş. "
    "Müşteri sipariş verdiğinde (Limon Kolonyası, El Kremi, Zeytinyağlı Sabun vb.) "
    "niyeti anla, ürünleri teyit et ve siparişi aldığına dair bir cevap dön."
)


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str
    ts: str


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_env() -> None:
    """Load `.env` into environment (best-effort)."""
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(override=False)
        return
    except Exception:
        pass

    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        return


@st.cache_resource(show_spinner=False)
def get_gemini_model() -> Any:
    load_env()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY bulunamadı. Proje köküne `.env` ekleyip "
            "`GEMINI_API_KEY=...` şeklinde tanımlayın."
        )

    try:
        import google.generativeai as genai  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "`google-generativeai` kütüphanesi bulunamadı. Kurulum için: "
            "`pip install google-generativeai`"
        ) from e

    genai.configure(api_key=api_key)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash").strip()

    try:
        return genai.GenerativeModel(model_name=model_name, system_instruction=SYSTEM_PROMPT)
    except TypeError:
        return genai.GenerativeModel(model_name=model_name)


def ensure_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            ChatMessage(
                role="assistant",
                content=(
                    "Merhaba! Ben OrderFlow AI.\n\n"
                    "Sipariş vermek istediğiniz ürünleri ve varsa adresinizi yazabilirsiniz."
                ),
                ts=now_ts(),
            )
        ]


def to_gemini_history(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for m in messages:
        role = "user" if m.role == "user" else "model"
        history.append({"role": role, "parts": [m.content]})
    return history


def gemini_reply(user_text: str, messages: list[ChatMessage]) -> str:
    model = get_gemini_model()
    history = to_gemini_history(messages[:-1])  # exclude the newly appended user message

    try:
        chat = model.start_chat(history=history)
        resp = chat.send_message(user_text)
        text = getattr(resp, "text", None)
        return str(text).strip() if text else "Şu an yanıt oluşturamadım. Lütfen tekrar dener misiniz?"
    except Exception:
        prompt = f"{SYSTEM_PROMPT}\n\nMüşteri mesajı:\n{user_text}"
        resp = model.generate_content(prompt)
        text = getattr(resp, "text", None)
        return str(text).strip() if text else "Şu an yanıt oluşturamadım. Lütfen tekrar dener misiniz?"


def render_sidebar() -> Page:
    st.sidebar.title("OrderFlow AI")
    st.sidebar.caption("Hediyelik Eşya & Kozmetik")
    page: Page = st.sidebar.radio(
        "Menü",
        options=["💬 WhatsApp Simülasyonu", "📊 Admin Dashboard"],
        index=0,
    )
    st.sidebar.divider()
    st.sidebar.markdown("**Env**: `.env` → `GEMINI_API_KEY=...`")
    return page


def render_whatsapp_page() -> None:
    st.title("💬 WhatsApp Simülasyonu")
    st.caption("Gerçekçi chat UI (`st.chat_message` + `st.chat_input`) + Gemini.")

    for m in st.session_state.messages:
        with st.chat_message(m.role):
            st.markdown(m.content)
            st.caption(m.ts)

    user_text = st.chat_input("Mesaj yaz…")
    if not user_text:
        return

    st.session_state.messages.append(ChatMessage(role="user", content=user_text, ts=now_ts()))

    with st.chat_message("assistant"):
        with st.spinner("Yanıt hazırlanıyor…"):
            try:
                reply = gemini_reply(user_text, st.session_state.messages)
            except Exception as e:
                reply = f"Konfigürasyon hatası: {e}"
        st.markdown(reply)
        st.caption(now_ts())

    st.session_state.messages.append(ChatMessage(role="assistant", content=reply, ts=now_ts()))
    st.rerun()


def render_admin_dashboard_page() -> None:
    st.title("📊 Admin Dashboard")
    st.caption("Mock sipariş akışı kaldırıldı. Bu sayfa sohbet geçmişini listeler.")

    messages: list[ChatMessage] = st.session_state.messages
    total = len(messages)
    user_count = sum(1 for m in messages if m.role == "user")
    assistant_count = sum(1 for m in messages if m.role == "assistant")

    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Mesaj", f"{total}")
    c2.metric("Müşteri", f"{user_count}")
    c3.metric("Asistan", f"{assistant_count}")

    st.divider()
    df = pd.DataFrame(
        [
            {"Zaman": m.ts, "Rol": ("Müşteri" if m.role == "user" else "Asistan"), "İçerik": m.content}
            for m in messages
        ]
    )
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Zaman": st.column_config.TextColumn(),
            "Rol": st.column_config.TextColumn(),
            "İçerik": st.column_config.TextColumn(width="large"),
        },
    )

    st.divider()
    if st.button("Sohbeti sıfırla"):
        st.session_state.messages = [
            ChatMessage(
                role="assistant",
                content=(
                    "Merhaba! Ben OrderFlow AI.\n\n"
                    "Sipariş vermek istediğiniz ürünleri ve varsa adresinizi yazabilirsiniz."
                ),
                ts=now_ts(),
            )
        ]
        st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="OrderFlow AI — Hediyelik & Kozmetik",
        page_icon="🧴",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    ensure_session_state()
    page = render_sidebar()

    if page == "💬 WhatsApp Simülasyonu":
        render_whatsapp_page()
    else:
        render_admin_dashboard_page()


if __name__ == "__main__":
    main()
*** End of File


SYSTEM_PROMPT = (
    "Sen bir Hediyelik Eşya ve Kozmetik Dükkanının akıllı WhatsApp sipariş asistanı "
    "OrderFlow AI'sın. Müşteriyle çok doğal, kısa ve kibar bir dille konuş. "
    "Müşteri sipariş verdiğinde (Limon Kolonyası, El Kremi, Zeytinyağlı Sabun vb.) "
    "niyeti anla, ürünleri teyit et ve siparişi aldığına dair bir cevap dön."
)


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str
    ts: str


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_env() -> None:
    """
    Load `.env` into environment (best-effort).
    - Prefers python-dotenv if present.
    - Falls back to a tiny `.env` parser (KEY=VALUE lines).
    """
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(override=False)
        return
    except Exception:
        pass

    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        return


@st.cache_resource(show_spinner=False)
def get_gemini_model() -> Any:
    load_env()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY bulunamadı. Proje köküne `.env` ekleyip "
            "`GEMINI_API_KEY=...` şeklinde tanımlayın."
        )

    try:
        import google.generativeai as genai  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "`google-generativeai` kütüphanesi bulunamadı. Kurulum için: "
            "`pip install google-generativeai`"
        ) from e

    genai.configure(api_key=api_key)

    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash").strip()
    try:
        return genai.GenerativeModel(model_name=model_name, system_instruction=SYSTEM_PROMPT)
    except TypeError:
        # Older library versions may not support system_instruction.
        return genai.GenerativeModel(model_name=model_name)


def ensure_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            ChatMessage(
                role="assistant",
                content=(
                    "Merhaba! Ben OrderFlow AI.\n\n"
                    "Sipariş vermek istediğiniz ürünleri ve varsa adresinizi yazabilirsiniz."
                ),
                ts=now_ts(),
            )
        ]


def to_gemini_history(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """
    Convert Streamlit message list into google-generativeai chat history.
    Roles: "user" | "model"
    """
    history: list[dict[str, Any]] = []
    for m in messages:
        role = "user" if m.role == "user" else "model"
        history.append({"role": role, "parts": [m.content]})
    return history


def gemini_reply(user_text: str, messages: list[ChatMessage]) -> str:
    model = get_gemini_model()
    history = to_gemini_history(messages[:-1])  # exclude newly appended user msg

    try:
        chat = model.start_chat(history=history)
        resp = chat.send_message(user_text)
        text = getattr(resp, "text", None)
        if text:
            return str(text).strip()
        return "Şu an yanıt oluşturamadım. Lütfen tekrar dener misiniz?"
    except Exception:
        prompt = f"{SYSTEM_PROMPT}\n\nMüşteri mesajı:\n{user_text}"
        resp = model.generate_content(prompt)
        text = getattr(resp, "text", None)
        if text:
            return str(text).strip()
        return "Şu an yanıt oluşturamadım. Lütfen tekrar dener misiniz?"


def render_sidebar() -> Page:
    st.sidebar.title("OrderFlow AI")
    st.sidebar.caption("Hediyelik Eşya & Kozmetik")

    page: Page = st.sidebar.radio(
        "Menü",
        options=["💬 WhatsApp Simülasyonu", "📊 Admin Dashboard"],
        index=0,
    )

    st.sidebar.divider()
    st.sidebar.markdown("**Env**: `.env` → `GEMINI_API_KEY=...`")
    return page


def render_whatsapp_page() -> None:
    st.title("💬 WhatsApp Simülasyonu")
    st.caption("Akıcı chat UI: `st.chat_message` + `st.chat_input` (Gemini entegrasyonu).")

    for m in st.session_state.messages:
        with st.chat_message(m.role):
            st.markdown(m.content)
            st.caption(m.ts)

    user_text = st.chat_input("Mesaj yaz…")
    if not user_text:
        return

    st.session_state.messages.append(ChatMessage(role="user", content=user_text, ts=now_ts()))

    with st.chat_message("assistant"):
        with st.spinner("Yanıt hazırlanıyor…"):
            try:
                reply = gemini_reply(user_text, st.session_state.messages)
            except Exception as e:
                reply = f"Konfigürasyon hatası: {e}"
        st.markdown(reply)
        st.caption(now_ts())

    st.session_state.messages.append(ChatMessage(role="assistant", content=reply, ts=now_ts()))
    st.rerun()


def render_admin_dashboard_page() -> None:
    st.title("📊 Admin Dashboard")
    st.caption("Mock sipariş akışı kaldırıldı. Bu sayfa sohbet geçmişini listeler.")

    messages: list[ChatMessage] = st.session_state.messages
    total = len(messages)
    user_count = sum(1 for m in messages if m.role == "user")
    assistant_count = sum(1 for m in messages if m.role == "assistant")

    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Mesaj", f"{total}")
    c2.metric("Müşteri", f"{user_count}")
    c3.metric("Asistan", f"{assistant_count}")

    st.divider()
    df = pd.DataFrame(
        [
            {
                "Zaman": m.ts,
                "Rol": ("Müşteri" if m.role == "user" else "Asistan"),
                "İçerik": m.content,
            }
            for m in messages
        ]
    )
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Zaman": st.column_config.TextColumn(),
            "Rol": st.column_config.TextColumn(),
            "İçerik": st.column_config.TextColumn(width="large"),
        },
    )

    st.divider()
    if st.button("Sohbeti sıfırla"):
        st.session_state.messages = [
            ChatMessage(
                role="assistant",
                content=(
                    "Merhaba! Ben OrderFlow AI.\n\n"
                    "Sipariş vermek istediğiniz ürünleri ve varsa adresinizi yazabilirsiniz."
                ),
                ts=now_ts(),
            )
        ]
        st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="OrderFlow AI — Hediyelik & Kozmetik",
        page_icon="🧴",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    ensure_session_state()
    page = render_sidebar()

    if page == "💬 WhatsApp Simülasyonu":
        render_whatsapp_page()
    else:
        render_admin_dashboard_page()


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import pandas as pd
import streamlit as st


Role = Literal["user", "assistant"]
Page = Literal["💬 WhatsApp Simülasyonu", "📊 Admin Dashboard"]


SYSTEM_PROMPT = (
    "Sen bir Hediyelik Eşya ve Kozmetik Dükkanının akıllı WhatsApp sipariş asistanı "
    "OrderFlow AI'sın. Müşteriyle çok doğal, kısa ve kibar bir dille konuş. "
    "Müşteri sipariş verdiğinde (Limon Kolonyası, El Kremi, Zeytinyağlı Sabun vb.) "
    "niyeti anla, ürünleri teyit et ve siparişi aldığına dair bir cevap dön."
)


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str
    ts: str


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_env() -> None:
    """
    Load `.env` into environment (best-effort).
    - Prefers python-dotenv if present.
    - Falls back to a tiny `.env` parser (KEY=VALUE lines).
    """
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(override=False)
        return
    except Exception:
        pass

    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        return


@st.cache_resource(show_spinner=False)
def get_gemini_model() -> Any:
    load_env()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY bulunamadı. Proje köküne `.env` ekleyip "
            "`GEMINI_API_KEY=...` şeklinde tanımlayın."
        )

    try:
        import google.generativeai as genai  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "`google-generativeai` kütüphanesi bulunamadı. Kurulum için: "
            "`pip install google-generativeai`"
        ) from e

    genai.configure(api_key=api_key)

    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash").strip()
    try:
        return genai.GenerativeModel(model_name=model_name, system_instruction=SYSTEM_PROMPT)
    except TypeError:
        # Older library versions may not support system_instruction.
        return genai.GenerativeModel(model_name=model_name)


def ensure_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            ChatMessage(
                role="assistant",
                content=(
                    "Merhaba! Ben OrderFlow AI.\n\n"
                    "Sipariş vermek istediğiniz ürünleri ve varsa adresinizi yazabilirsiniz."
                ),
                ts=now_ts(),
            )
        ]


def to_gemini_history(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """
    Convert Streamlit message list into google-generativeai chat history.
    Roles: "user" | "model"
    """
    history: list[dict[str, Any]] = []
    for m in messages:
        role = "user" if m.role == "user" else "model"
        history.append({"role": role, "parts": [m.content]})
    return history


def gemini_reply(user_text: str, messages: list[ChatMessage]) -> str:
    model = get_gemini_model()
    history = to_gemini_history(messages[:-1])  # exclude newly appended user msg

    try:
        chat = model.start_chat(history=history)
        resp = chat.send_message(user_text)
        text = getattr(resp, "text", None)
        if text:
            return str(text).strip()
        return "Şu an yanıt oluşturamadım. Lütfen tekrar dener misiniz?"
    except Exception:
        prompt = f"{SYSTEM_PROMPT}\n\nMüşteri mesajı:\n{user_text}"
        resp = model.generate_content(prompt)
        text = getattr(resp, "text", None)
        if text:
            return str(text).strip()
        return "Şu an yanıt oluşturamadım. Lütfen tekrar dener misiniz?"


def render_sidebar() -> Page:
    st.sidebar.title("OrderFlow AI")
    st.sidebar.caption("Hediyelik Eşya & Kozmetik")

    page: Page = st.sidebar.radio(
        "Menü",
        options=["💬 WhatsApp Simülasyonu", "📊 Admin Dashboard"],
        index=0,
    )

    st.sidebar.divider()
    st.sidebar.markdown("**Env**: `.env` → `GEMINI_API_KEY=...`")
    return page


def render_whatsapp_page() -> None:
    st.title("💬 WhatsApp Simülasyonu")
    st.caption("Akıcı chat UI: `st.chat_message` + `st.chat_input` (Gemini entegrasyonu).")

    for m in st.session_state.messages:
        with st.chat_message(m.role):
            st.markdown(m.content)
            st.caption(m.ts)

    user_text = st.chat_input("Mesaj yaz…")
    if not user_text:
        return

    st.session_state.messages.append(ChatMessage(role="user", content=user_text, ts=now_ts()))

    with st.chat_message("assistant"):
        with st.spinner("Yanıt hazırlanıyor…"):
            try:
                reply = gemini_reply(user_text, st.session_state.messages)
            except Exception as e:
                reply = f"Konfigürasyon hatası: {e}"
        st.markdown(reply)
        st.caption(now_ts())

    st.session_state.messages.append(ChatMessage(role="assistant", content=reply, ts=now_ts()))
    st.rerun()


def render_admin_dashboard_page() -> None:
    st.title("📊 Admin Dashboard")
    st.caption("Mock sipariş akışı kaldırıldı. Bu sayfa sohbet geçmişini listeler.")

    messages: list[ChatMessage] = st.session_state.messages
    total = len(messages)
    user_count = sum(1 for m in messages if m.role == "user")
    assistant_count = sum(1 for m in messages if m.role == "assistant")

    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Mesaj", f"{total}")
    c2.metric("Müşteri", f"{user_count}")
    c3.metric("Asistan", f"{assistant_count}")

    st.divider()
    df = pd.DataFrame(
        [{"Zaman": m.ts, "Rol": ("Müşteri" if m.role == "user" else "Asistan"), "İçerik": m.content} for m in messages]
    )
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Zaman": st.column_config.TextColumn(),
            "Rol": st.column_config.TextColumn(),
            "İçerik": st.column_config.TextColumn(width="large"),
        },
    )

    st.divider()
    if st.button("Sohbeti sıfırla"):
        st.session_state.messages = [
            ChatMessage(
                role="assistant",
                content=(
                    "Merhaba! Ben OrderFlow AI.\n\n"
                    "Sipariş vermek istediğiniz ürünleri ve varsa adresinizi yazabilirsiniz."
                ),
                ts=now_ts(),
            )
        ]
        st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="OrderFlow AI — Hediyelik & Kozmetik",
        page_icon="🧴",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    ensure_session_state()
    page = render_sidebar()

    if page == "💬 WhatsApp Simülasyonu":
        render_whatsapp_page()
    else:
        render_admin_dashboard_page()


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import pandas as pd
import streamlit as st


Role = Literal["user", "assistant"]
Page = Literal["💬 WhatsApp Simülasyonu", "📊 Admin Dashboard"]


SYSTEM_PROMPT = (
    "Sen bir Hediyelik Eşya ve Kozmetik Dükkanının akıllı WhatsApp sipariş asistanı "
    "OrderFlow AI'sın. Müşteriyle çok doğal, kısa ve kibar bir dille konuş. "
    "Müşteri sipariş verdiğinde (Limon Kolonyası, El Kremi, Zeytinyağlı Sabun vb.) "
    "niyeti anla, ürünleri teyit et ve siparişi aldığına dair bir cevap dön."
)


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str
    ts: str


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_env() -> None:
    """
    Load `.env` into environment (best-effort).
    - Prefers python-dotenv if present.
    - Falls back to a tiny `.env` parser (KEY=VALUE lines).
    """
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(override=False)
        return
    except Exception:
        pass

    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        return


@st.cache_resource(show_spinner=False)
def get_gemini_model() -> Any:
    load_env()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY bulunamadı. Proje köküne `.env` ekleyip "
            "`GEMINI_API_KEY=...` şeklinde tanımlayın."
        )

    try:
        import google.generativeai as genai  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "`google-generativeai` kütüphanesi bulunamadı. Kurulum için: "
            "`pip install google-generativeai`"
        ) from e

    genai.configure(api_key=api_key)

    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash").strip()
    try:
        return genai.GenerativeModel(model_name=model_name, system_instruction=SYSTEM_PROMPT)
    except TypeError:
        # Older library versions may not support system_instruction.
        return genai.GenerativeModel(model_name=model_name)


def ensure_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            ChatMessage(
                role="assistant",
                content=(
                    "Merhaba! Ben OrderFlow AI.\n\n"
                    "Sipariş vermek istediğiniz ürünleri ve varsa adresinizi yazabilirsiniz."
                ),
                ts=now_ts(),
            )
        ]


def to_gemini_history(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """
    Convert Streamlit message list into google-generativeai chat history.
    Roles: "user" | "model"
    """
    history: list[dict[str, Any]] = []
    for m in messages:
        role = "user" if m.role == "user" else "model"
        history.append({"role": role, "parts": [m.content]})
    return history


def gemini_reply(user_text: str, messages: list[ChatMessage]) -> str:
    model = get_gemini_model()
    history = to_gemini_history(messages[:-1])  # exclude the newly appended user msg

    # Prefer multi-turn chat; fallback to single-turn generation.
    try:
        chat = model.start_chat(history=history)
        resp = chat.send_message(user_text)
        text = getattr(resp, "text", None)
        if text:
            return str(text).strip()
        return "Şu an yanıt oluşturamadım. Lütfen tekrar dener misiniz?"
    except Exception:
        prompt = f"{SYSTEM_PROMPT}\n\nMüşteri mesajı:\n{user_text}"
        resp = model.generate_content(prompt)
        text = getattr(resp, "text", None)
        if text:
            return str(text).strip()
        return "Şu an yanıt oluşturamadım. Lütfen tekrar dener misiniz?"


def render_sidebar() -> Page:
    st.sidebar.title("OrderFlow AI")
    st.sidebar.caption("Hediyelik Eşya & Kozmetik")
    page: Page = st.sidebar.radio(
        "Menü",
        options=["💬 WhatsApp Simülasyonu", "📊 Admin Dashboard"],
        index=0,
    )
    st.sidebar.divider()
    st.sidebar.markdown("**Env**: `.env` → `GEMINI_API_KEY=...`")
    return page


def render_whatsapp_page() -> None:
    st.title("💬 WhatsApp Simülasyonu")
    st.caption("Gerçekçi mesajlaşma arayüzü (Gemini entegrasyonu).")

    for m in st.session_state.messages:
        with st.chat_message(m.role):
            st.markdown(m.content)
            st.caption(m.ts)

    user_text = st.chat_input("Mesaj yaz…")
    if not user_text:
        return

    st.session_state.messages.append(ChatMessage(role="user", content=user_text, ts=now_ts()))

    with st.chat_message("assistant"):
        with st.spinner("Yanıt hazırlanıyor…"):
            try:
                reply = gemini_reply(user_text, st.session_state.messages)
            except Exception as e:
                reply = f"Konfigürasyon hatası: {e}"
        st.markdown(reply)
        st.caption(now_ts())

    st.session_state.messages.append(ChatMessage(role="assistant", content=reply, ts=now_ts()))
    st.rerun()


def render_admin_dashboard_page() -> None:
    st.title("📊 Admin Dashboard")
    st.caption("Mock sipariş akışı kaldırıldı. Bu sayfa sohbet geçmişini listeler.")

    messages: list[ChatMessage] = st.session_state.messages
    total = len(messages)
    user_count = sum(1 for m in messages if m.role == "user")
    assistant_count = sum(1 for m in messages if m.role == "assistant")

    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Mesaj", f"{total}")
    c2.metric("Müşteri", f"{user_count}")
    c3.metric("Asistan", f"{assistant_count}")

    st.divider()
    df = pd.DataFrame(
        [
            {
                "Zaman": m.ts,
                "Rol": "Müşteri" if m.role == "user" else "Asistan",
                "İçerik": m.content,
            }
            for m in messages
        ]
    )
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Zaman": st.column_config.TextColumn(),
            "Rol": st.column_config.TextColumn(),
            "İçerik": st.column_config.TextColumn(width="large"),
        },
    )

    st.divider()
    if st.button("Sohbeti sıfırla"):
        st.session_state.messages = [
            ChatMessage(
                role="assistant",
                content=(
                    "Merhaba! Ben OrderFlow AI.\n\n"
                    "Sipariş vermek istediğiniz ürünleri ve varsa adresinizi yazabilirsiniz."
                ),
                ts=now_ts(),
            )
        ]
        st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="OrderFlow AI — Hediyelik & Kozmetik",
        page_icon="🧴",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    ensure_session_state()
    page = render_sidebar()

    if page == "💬 WhatsApp Simülasyonu":
        render_whatsapp_page()
    else:
        render_admin_dashboard_page()


if __name__ == "__main__":
    main()

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Literal

import pandas as pd
import streamlit as st


OrderStatus = Literal["pending", "confirmed"]


@dataclass(frozen=True)
class CatalogItem:
    key: str
    display_name: str
    unit_price: float
    synonyms: tuple[str, ...]


@dataclass(frozen=True)
class OrderItem:
    product_key: str
    product_name: str
    quantity: int
    unit_price: float

    @property
    def line_total(self) -> float:
        return self.quantity * self.unit_price


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _try_parse_quantity(text: str, needle: str) -> int | None:
    """
    Very small demo parser:
    - "2 ürün", "2x ürün", "ürün 2 adet", "2 adet ürün"
    """
    patterns = [
        rf"(?P<qty>\d+)\s*(?:x|adet)?\s*{re.escape(needle)}",
        rf"{re.escape(needle)}\s*(?P<qty>\d+)\s*(?:x|adet)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                qty = int(match.group("qty"))
                if qty > 0:
                    return qty
            except ValueError:
                return None
    return None


def parse_order_from_message(message: str, catalog: Iterable[CatalogItem]) -> list[OrderItem]:
    text = message.lower()
    found: list[OrderItem] = []
    for item in catalog:
        qty: int | None = None
        for syn in item.synonyms:
            if syn in text:
                qty = _try_parse_quantity(text, syn) or 1
                break
        if qty:
            found.append(
                OrderItem(
                    product_key=item.key,
                    product_name=item.display_name,
                    quantity=qty,
                    unit_price=item.unit_price,
                )
            )
    # merge duplicates (if multiple synonyms hit)
    merged: dict[str, OrderItem] = {}
    for it in found:
        if it.product_key not in merged:
            merged[it.product_key] = it
        else:
            prev = merged[it.product_key]
            merged[it.product_key] = OrderItem(
                product_key=prev.product_key,
                product_name=prev.product_name,
                quantity=prev.quantity + it.quantity,
                unit_price=prev.unit_price,
            )
    return list(merged.values())


def format_order_summary(items: list[OrderItem]) -> tuple[str, float]:
    total = sum(i.line_total for i in items)
    lines = []
    for it in items:
        lines.append(f"- {it.quantity} × {it.product_name} — {it.line_total:,.2f} ₺")
    summary = "\n".join(lines) + f"\n\n**Toplam:** {total:,.2f} ₺"
    return summary, total


def ensure_state() -> None:
    example = (
        "Merhaba, 2 şişe limon kolonyası (250ml), 1 tane el kremi ve 1 tane "
        "zeytinyağlı sabun siparişi vermek istiyorum. Adresim: Atatürk Cad. No:5 Isparta."
    )

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {
                "role": "assistant",
                "content": (
                    "Merhaba! Ben OrderFlow AI demo asistanıyım.\n\n"
                    "Satın almak istediğin ürünleri ve adresini yazabilirsin."
                ),
                "ts": _now_iso(),
            }
        ]

    if "orders" not in st.session_state:
        st.session_state.orders = []

    if "composer" not in st.session_state:
        st.session_state.composer = example

    if "next_order_id" not in st.session_state:
        max_id = max((o["id"] for o in st.session_state.orders), default=1000)
        st.session_state.next_order_id = max_id + 1


def compute_order_total(order: dict) -> float:
    total = 0.0
    for it in order.get("items", []):
        total += float(it["quantity"]) * float(it["unit_price"])
    return total


def _status_label(status: OrderStatus) -> str:
    return {"pending": "Bekliyor", "confirmed": "Onaylandı"}[status]


def render_whatsapp_simulation(catalog: list[CatalogItem]) -> None:
    st.markdown("### WhatsApp Simülasyonu")
    st.caption("Mock veri ile çalışan chat akışı. (DB / AI entegrasyonu yok.)")

    with st.container(border=True):
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                st.caption(msg.get("ts", ""))

    with st.container(border=True):
        st.markdown("**Müşteri Mesajı**")
        actions = st.columns([1, 1, 2])
        with actions[0]:
            if st.button("Örnek mesajı ekle", use_container_width=True):
                st.session_state.composer = (
                    "Merhaba, 2 şişe limon kolonyası (250ml), 1 tane el kremi ve 1 tane "
                    "zeytinyağlı sabun siparişi vermek istiyorum. Adresim: Atatürk Cad. No:5 Isparta."
                )
        with actions[1]:
            if st.button("Temizle", use_container_width=True):
                st.session_state.composer = ""

        user_text = st.text_area(
            " ",
            key="composer",
            height=110,
            placeholder="Ürünleri ve adresini yaz…",
            label_visibility="collapsed",
        )
        send = st.button("Gönder", type="primary", use_container_width=True)

    if not send:
        return

    if not user_text.strip():
        st.warning("Lütfen bir mesaj yaz.")
        return

    st.session_state.chat_messages.append(
        {"role": "user", "content": user_text.strip(), "ts": _now_iso()}
    )
    #st.session_state.composer = ""

    items = parse_order_from_message(user_text, catalog)
    if not items:
        bot_text = (
            "Ürünleri tespit edemedim. Lütfen ürün isimlerini daha net yazar mısın?\n\n"
            "Örnek: `2 limon kolonyası, 1 el kremi, 1 zeytinyağlı sabun`"
        )
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": bot_text, "ts": _now_iso()}
        )
        st.rerun()

    summary, total = format_order_summary(items)
    order_id = int(st.session_state.next_order_id)
    st.session_state.next_order_id = order_id + 1

    st.session_state.orders.insert(
        0,
        {
            "id": order_id,
            "customer_name": "Demo Müşteri",
            "customer_whatsapp": "+90 5xx xxx xx xx",
            "status": "pending",
            "created_at": _now_iso(),
            "items": [
                {
                    "product_name": it.product_name,
                    "quantity": it.quantity,
                    "unit_price": it.unit_price,
                }
                for it in items
            ],
        },
    )

    bot_text = (
        f"Siparişini aldım. (Sipariş No: **#{order_id}**)\n\n"
        f"{summary}\n\n"
        "Bilgileri doğrulamak için işletme tarafından incelenecek."
    )
    st.session_state.chat_messages.append(
        {"role": "assistant", "content": bot_text, "ts": _now_iso()}
    )
    st.rerun()


def render_admin_dashboard() -> None:
    st.markdown("### Admin Dashboard")
    st.caption("Gelen siparişler — mock (oturum boyunca hafızada).")

    orders = st.session_state.orders
    if not orders:
        st.info("Henüz sipariş yok. Soldan bir mesaj göndererek sipariş oluşturabilirsin.")
        return

    pending_count = sum(1 for o in orders if o["status"] == "pending")
    confirmed_count = sum(1 for o in orders if o["status"] == "confirmed")

    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Sipariş", f"{len(orders)}")
    c2.metric("Bekliyor", f"{pending_count}")
    c3.metric("Onaylandı", f"{confirmed_count}")

    rows = []
    for o in orders:
        rows.append(
            {
                "Sipariş No": f"#{o['id']}",
                "Müşteri": o["customer_name"],
                "Durum": _status_label(o["status"]),
                "Oluşturma": o["created_at"],
            }
        )

    df = pd.DataFrame(rows)
    with st.container(border=True):
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Sipariş No": st.column_config.TextColumn(),
                "Durum": st.column_config.TextColumn(),
                "Oluşturma": st.column_config.TextColumn(),
            },
        )


def main() -> None:
    st.set_page_config(
        page_title="OrderFlow AI — Hediyelik & Kozmetik Demo",
        page_icon="🧴",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    ensure_state()

    catalog = [
        CatalogItem(
            key="lemon_cologne_250",
            display_name="Limon Kolonyası (250ml)",
            unit_price=89.0,
            synonyms=("limon kolonyası", "limon kolonyasi", "kolonya", "kolonyası", "kolonyasi"),
        ),
        CatalogItem(
            key="hand_cream",
            display_name="El Kremi",
            unit_price=79.0,
            synonyms=("el kremi", "el krem", "krem"),
        ),
        CatalogItem(
            key="olive_oil_soap",
            display_name="Zeytinyağlı Sabun",
            unit_price=49.0,
            synonyms=("zeytinyağlı sabun", "zeytinyagli sabun", "sabun"),
        ),
    ]

    st.title("Hediyelik Eşya ve Kozmetik Dükkanı")
    st.caption("Jüri demosu — Streamlit UI (tamamen mock veri)")

    left, right = st.columns([1.25, 1.0], gap="large")

    with left:
        render_whatsapp_simulation(catalog)
        st.markdown("#### Ürün Kataloğu (mock)")
        st.dataframe(
            pd.DataFrame(
                [
                    {"Ürün": c.display_name, "Fiyat (₺)": c.unit_price}
                    for c in catalog
                ]
            ),
            use_container_width=True,
            hide_index=True,
            column_config={"Fiyat (₺)": st.column_config.NumberColumn(format="%.2f ₺")},
        )

    with right:
        render_admin_dashboard()
        with st.expander("Not", expanded=False):
            st.markdown(
                "Bu demo, `ARCHITECTURE.md` içindeki **UI katmanı** için hazırlanan mock arayüzdür. "
                "Veriler oturum boyunca bellekte tutulur."
            )


if __name__ == "__main__":
    main()