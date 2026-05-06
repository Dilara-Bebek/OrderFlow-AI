from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st


SYSTEM_PROMPT = """
Sen bir kozmetik ve hediyelik esya dukkaninin WhatsApp siparis asistani "OrderFlow AI"sin.
Musteriyle dogal, kibar ve kisa konus.

Kurallar:
1) Siparisin tamamlanmasi icin 5 bilgi kesinlikle sarttir:
   - customer_name (ad-soyad)
   - urun(ler)
   - miktar(lar)
   - acik adres
   - sehir
   Bu 5 alandan biri eksikse ASLA siparisi tamamlama.

2) Eksik bilgi kontrolu:
   - Sadece eksik olan bilgiyi sor.
   - Ornek:
     "Adiniza kayit acabilmem icin isminizi ve soyisminizi ogrenebilir miyim?"
     "Hangi sehre gonderecegiz?"
   - Bilgiler tamamlanmadan JSON uretme.

3) Sepet mantigi:
   - Musteri ayni anda birden fazla urun isteyebilir.
   - Tum urunleri ve miktarlari hafizada tut.
   - Katalog:
     ["Limon Kolonyasi", "Gul Kremi", "Zeytinyagli Sabun", "Gul Suyu"]
   - Fuzzy matching uygula:
     "isparta gulu", "gul krem", "gul kremi" -> "Gul Kremi"
   - Dogal dilden miktar cikar:
     "1 gul kremi", "iki sabun", "100 kolonya"

4) Onay asamasi (cok kritik):
   - Tum 5 bilgi tamamlandiginda HEMEN JSON URETME.
   - Once "Siparis Ozeti" ver:
     - ad-soyad
     - sehir
     - acik adres
     - tum urunler ve miktarlar
   - Ardindan acikca sor:
     "Siparisinizi onayliyor musunuz?"

5) JSON uretim kurali:
   - Sadece musteri "Evet", "Onayliyorum", "Onay" gibi kesin onay verirse JSON uret.
   - JSON disinda hicbir metin ekleme.
   - Cikti semasi:
{
  "status": "complete",
  "data": {
    "customer_name": "Ahmet Yilmaz",
    "city": "Isparta",
    "address": "Karaoz Mah. Hasan Namal Cad. No: 74",
    "items": [
      {"product_name": "Limon Kolonyasi", "quantity": 100},
      {"product_name": "Zeytinyagli Sabun", "quantity": 20}
    ]
  }
}
""".strip()


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_env() -> None:
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
        raise RuntimeError("GEMINI_API_KEY bulunamadi. Lutfen .env dosyasini kontrol edin.")

    try:
        import google.generativeai as genai  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "google-generativeai kutuphanesi bulunamadi. Kurulum: pip install google-generativeai"
        ) from exc

    genai.configure(api_key=api_key)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()

    try:
        return genai.GenerativeModel(model_name=model_name, system_instruction=SYSTEM_PROMPT)
    except TypeError:
        return genai.GenerativeModel(model_name=model_name)


def ensure_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Merhaba, ben OrderFlow AI. Siparisinizi olusturmak icin yardimci olayim. "
                    "Urun, miktar ve mumkunse adresinizi yazabilirsiniz."
                ),
                "ts": now_ts(),
            }
        ]
    if "last_complete_order" not in st.session_state:
        st.session_state.last_complete_order = None


def init_db(db_path: str = "orderflow_ai.db") -> None:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT,
                city TEXT,
                address TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                status TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                product_name TEXT,
                quantity INTEGER
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT,
                stock INTEGER
            )
            """
        )

        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = int(cursor.fetchone()[0])
        if product_count == 0:
            seed_data = [
                ("Limon Kolonyası", 150),
                ("Gül Kremi", 80),
                ("Zeytinyağlı Sabun", 200),
                ("Gül Suyu", 100),
            ]
            cursor.executemany(
                "INSERT INTO products (product_name, stock) VALUES (?, ?)",
                seed_data,
            )
            conn.commit()


def save_complete_order_to_db(order_payload: dict[str, Any], db_path: str = "orderflow_ai.db") -> int:
    data = order_payload["data"]
    customer_name = str(data["customer_name"]).strip()
    city = str(data["city"]).strip()
    address = str(data["address"]).strip()
    items = data["items"]

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO customers (customer_name, city, address)
            VALUES (?, ?, ?)
            """,
            (customer_name, city, address),
        )
        customer_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO orders (customer_id, status)
            VALUES (?, ?)
            """,
            (customer_id, "Bekliyor"),
        )
        order_id = int(cursor.lastrowid)
        for item in items:
            cursor.execute(
                """
                INSERT INTO order_items (order_id, product_name, quantity)
                VALUES (?, ?, ?)
                """,
                (order_id, str(item["product_name"]).strip(), int(item["quantity"])),
            )
        conn.commit()
    return order_id


def render_admin_dashboard() -> None:
    st.title("OrderFlow AI | Isletme Yonetim Portali")
    st.caption("Operasyon, siparis ve musteri analiz paneli")
    tab_orders, tab_stock = st.tabs(["Sipariş Yönetimi", "Ürün Stok Durumu"])

    with sqlite3.connect("orderflow_ai.db") as conn:
        total_orders = int(
            pd.read_sql_query("SELECT COUNT(*) AS cnt FROM orders", conn).iloc[0]["cnt"]
        )
        pending_orders = int(
            pd.read_sql_query(
                "SELECT COUNT(*) AS cnt FROM orders WHERE status = 'Bekliyor'", conn
            ).iloc[0]["cnt"]
        )
        order_item_columns = {
            row["name"]
            for _, row in pd.read_sql_query("PRAGMA table_info(order_items)", conn).iterrows()
        }
        if "price" in order_item_columns:
            total_revenue = float(
                pd.read_sql_query(
                    "SELECT COALESCE(SUM(quantity * price), 0) AS total FROM order_items",
                    conn,
                ).iloc[0]["total"]
            )
            third_metric_label = "Toplam Ciro"
            third_metric_value = f"{total_revenue:,.0f} TL".replace(",", ".")
        elif "unit_price" in order_item_columns:
            total_revenue = float(
                pd.read_sql_query(
                    "SELECT COALESCE(SUM(quantity * unit_price), 0) AS total FROM order_items",
                    conn,
                ).iloc[0]["total"]
            )
            third_metric_label = "Toplam Ciro"
            third_metric_value = f"{total_revenue:,.0f} TL".replace(",", ".")
        else:
            active_customers = int(
                pd.read_sql_query(
                    "SELECT COUNT(DISTINCT customer_id) AS cnt FROM orders", conn
                ).iloc[0]["cnt"]
            )
            third_metric_label = "Aktif Musteri"
            third_metric_value = str(active_customers)

        col1, col2, col3 = st.columns(3)
        col1.metric("Toplam Siparis Sayisi", total_orders)
        col2.metric("Bekleyen Siparisler", pending_orders)
        col3.metric(third_metric_label, third_metric_value)

        with tab_orders:
            orders_query = """
                SELECT o.id, c.customer_name, c.city, c.address, oi.product_name, oi.quantity, o.status FROM orders o JOIN customers c ON o.customer_id = c.id JOIN order_items oi ON o.id = oi.order_id ORDER BY o.id DESC
            """
            orders_df = pd.read_sql_query(orders_query, conn)
            if orders_df.empty:
                st.info("Sipariş yok")
            else:
                edited_df = st.data_editor(
                    orders_df,
                    use_container_width=True,
                    hide_index=True,
                    key="orders_status_editor",
                    column_config={
                        "status": st.column_config.SelectboxColumn(
                            "status",
                            options=[
                                "Bekliyor",
                                "Onaylandı",
                                "Reddedildi",
                                "Hazırlanıyor",
                                "Kargoya Verildi",
                            ],
                            required=True,
                        )
                    },
                    disabled=["id", "customer_name", "city", "address", "product_name", "quantity"],
                )
                status_badge_colors = {
                    "Bekliyor": "#f59e0b",
                    "Onaylandı": "#22c55e",
                    "Reddedildi": "#ef4444",
                    "Hazırlanıyor": "#3b82f6",
                    "Kargoya Verildi": "#8b5cf6",
                }
                status_counts = edited_df["status"].value_counts().to_dict()
                if status_counts:
                    badges = "".join(
                        (
                            "<span style='display:inline-block;padding:6px 10px;margin:0 8px 8px 0;"
                            f"border-radius:999px;background:{status_badge_colors.get(k, '#6b7280')};"
                            "color:white;font-size:12px;font-weight:600;'>"
                            f"{k}: {v}</span>"
                        )
                        for k, v in status_counts.items()
                    )
                    st.markdown(badges, unsafe_allow_html=True)

                status_changes = edited_df.loc[
                    edited_df["status"] != orders_df["status"], ["id", "status"]
                ].drop_duplicates(subset=["id"], keep="last")

                if not status_changes.empty:
                    conn.executemany(
                        "UPDATE orders SET status = ? WHERE id = ?",
                        [(row["status"], int(row["id"])) for _, row in status_changes.iterrows()],
                    )
                    conn.commit()
                    st.toast("Sipariş durumu başarıyla güncellendi!")
                    st.rerun()

        with tab_stock:
            stock_query = 'SELECT product_name as "Ürün Adı", stock as "Stok" FROM products'
            stock_df = pd.read_sql_query(stock_query, conn)
            st.dataframe(stock_df, use_container_width=True)


def apply_whatsapp_css() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif !important;
}

.block-container {
    max-width: 1120px !important;
    padding-top: 1.2rem !important;
    padding-bottom: 1rem !important;
}

[data-testid="stSidebar"] > div:first-child {
    background: #f8fafc;
}

[data-testid="stSidebarNav"] {
    margin-top: 0.35rem;
}

div[data-testid="stChatMessage"] {
    border-radius: 16px;
    padding: 0.5rem 0.6rem;
    margin: 0.45rem 0;
    width: fit-content;
    max-width: 78%;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}
div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-assistant"]) {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    margin-right: auto;
}
div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) {
    background-color: #dcf8c6;
    border: 1px solid #cdebb7;
    margin-left: auto;
}

[data-testid="stChatMessageContent"] p {
    margin-bottom: 0.2rem;
}

[data-testid="stChatInput"] {
    margin-top: 0.35rem;
}

.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    border: 1px solid #166534 !important;
    background: #166534 !important;
    color: #ffffff !important;
}

.stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {
    background: #14532d !important;
    border-color: #14532d !important;
}

h1 {
    font-size: 2rem !important;
    line-height: 1.2 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


def to_gemini_history(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        history.append({"role": role, "parts": [msg["content"]]})
    return history


def gemini_reply(user_text: str, messages: list[dict[str, str]]) -> str:
    model = get_gemini_model()
    history = to_gemini_history(messages[:-1])

    try:
        chat = model.start_chat(history=history)
        response = chat.send_message(user_text)
        text = getattr(response, "text", None)
        return str(text).strip() if text else ""
    except Exception:
        prompt = f"{SYSTEM_PROMPT}\n\nMusteri mesaji:\n{user_text}"
        response = model.generate_content(prompt)
        text = getattr(response, "text", None)
        return str(text).strip() if text else ""


def parse_complete_order_json(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, flags=re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()

    try:
        payload = json.loads(candidate)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("status") != "complete":
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None

    customer_name = data.get("customer_name")
    city = data.get("city")
    address = data.get("address")
    items = data.get("items")

    if not isinstance(customer_name, str) or not customer_name.strip():
        return None
    if not isinstance(city, str) or not city.strip():
        return None
    if not isinstance(address, str) or not address.strip():
        return None
    if not isinstance(items, list) or not items:
        return None
    for item in items:
        if not isinstance(item, dict):
            return None
        product_name = item.get("product_name")
        quantity = item.get("quantity")
        if not isinstance(product_name, str) or not product_name.strip():
            return None
        if not isinstance(quantity, int) or quantity <= 0:
            return None

    return payload


def render_order_receipt(order_payload: dict[str, Any]) -> None:
    data = order_payload.get("data", {})
    customer_name = data.get("customer_name", "-")
    city = data.get("city", "-")
    address = data.get("address", "-")
    items = data.get("items", [])

    st.markdown("### Siparis Ozeti Fisi")
    summary_df = pd.DataFrame(
        [
            {"Alan": "Musteri Adi", "Deger": customer_name},
            {"Alan": "Sehir", "Deger": city},
            {"Alan": "Adres", "Deger": address},
        ]
    )
    st.table(summary_df)

    item_rows = []
    for item in items:
        quantity = item.get("quantity", "-")
        product_name = item.get("product_name", "-")
        item_rows.append({"Alinan Urunler": f"{quantity} - {product_name}"})
    if item_rows:
        st.table(pd.DataFrame(item_rows))


def render_chat() -> None:
    st.title("OrderFlow AI | Isletme Yonetim Portali")
    st.subheader("WhatsApp Simulasyonu")
    st.caption("Gemini destekli siparis asistani")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            st.caption(msg["ts"])

    user_text = st.chat_input("Mesajinizi yazin...")
    if not user_text:
        if st.session_state.last_complete_order:
            st.success("✅ Siparişiniz başarıyla oluşturuldu!")
            render_order_receipt(st.session_state.last_complete_order)
        return

    st.session_state.messages.append({"role": "user", "content": user_text, "ts": now_ts()})

    with st.chat_message("user"):
        st.markdown(user_text)
        st.caption(st.session_state.messages[-1]["ts"])

    with st.spinner("OrderFlow AI yaziyor..."):
        try:
            reply = gemini_reply(user_text, st.session_state.messages)
        except Exception as exc:
            reply = f"Sistem hatasi: {exc}"

    parsed = parse_complete_order_json(reply)
    if parsed is not None:
        try:
            save_complete_order_to_db(parsed)
            st.session_state.last_complete_order = parsed
            st.success("Sipariş fişi başarıyla oluşturuldu")
            render_order_receipt(parsed)
        except Exception as exc:
            st.error(f"Sipariş kaydedilirken hata oluştu: {exc}")
        return

    if not reply:
        reply = "Siparisinizi aliyorum, devam etmek icin bilgileri biraz daha detaylandirabilir misiniz?"

    with st.chat_message("assistant"):
        st.markdown(reply)
        st.caption(now_ts())

    st.session_state.messages.append({"role": "assistant", "content": reply, "ts": now_ts()})


def main() -> None:
    init_db()
    st.set_page_config(page_title="OrderFlow AI | Isletme Yonetim Portali", page_icon="💬", layout="wide")
    ensure_state()
    apply_whatsapp_css()
    st.sidebar.markdown(
        """
        <div style="padding:12px;border-radius:14px;background:#e2e8f0;margin-bottom:10px;">
            <div style="font-size:28px;">🧾</div>
            <div style="font-size:14px;font-weight:700;color:#0f172a;">OrderFlow AI</div>
            <div style="font-size:12px;color:#334155;">Isletme Paneli</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    page = st.sidebar.radio("Menu", ["💬 WhatsApp Simülasyonu", "📊 Admin Dashboard"], index=0)

    if page == "📊 Admin Dashboard":
        render_admin_dashboard()
    else:
        render_chat()


if __name__ == "__main__":
    main()
