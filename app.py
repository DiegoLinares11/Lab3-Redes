import os, json, threading, queue, time
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
import redis

# ── Configuración desde .env ──
load_dotenv()
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PWD  = os.getenv("REDIS_PWD", None)
SECTION = os.getenv("SECTION", "sec10")
TOPO    = os.getenv("TOPO", "topo1")
NODE    = os.getenv("NODE", "B")
PROTO   = os.getenv("PROTO", "lsr")
TTL_DEF = int(os.getenv("TTL_DEFAULT", "5"))

MY_CHANNEL = f"{SECTION}.{TOPO}.{NODE}"

# ── Estado global ──
if "incoming" not in st.session_state:
    st.session_state.incoming = queue.Queue()
if "listener_thread" not in st.session_state:
    st.session_state.listener_thread = None
if "stop_event" not in st.session_state:
    st.session_state.stop_event = threading.Event()
if "listening" not in st.session_state:
    st.session_state.listening = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ── Utilidades ──
def now(ts=None):
    return datetime.fromtimestamp(ts or time.time()).strftime("%H:%M")

def get_client():
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PWD,
        decode_responses=True
    )

def listener(stop_event):
    r = get_client()
    pubsub = r.pubsub()
    pubsub.subscribe(MY_CHANNEL)
    while not stop_event.is_set():
        msg = pubsub.get_message(timeout=1.0)
        if msg and msg["type"] == "message":
            st.session_state.incoming.put((time.time(), msg["data"]))

# ── UI ──
st.set_page_config(page_title=f"Chat Nodo {NODE}", layout="centered")
st.title(f"💬 Chat Nodo {NODE}")

# Enviar mensajes
with st.form("send_form", clear_on_submit=True):
    col1, col2 = st.columns([3, 1])
    to = col1.text_input("Enviar a:", "A")
    ttl = col2.number_input("TTL", 1, 10, TTL_DEF)
    body = st.text_input("Mensaje:", "hola")
    send = st.form_submit_button("Enviar 🚀")
    if send:
        pkt = {
            "proto": PROTO,
            "type": "message",
            "from": NODE,
            "to": to,
            "ttl": ttl,
            "headers": [{"trace": True}],
            "payload": body,
            "_ts": int(time.time() * 1000)
        }
        get_client().publish(f"{SECTION}.{TOPO}.{to}", json.dumps(pkt))
        st.session_state.chat_history.append(("out", now(), pkt["to"], pkt["payload"], pkt["ttl"]))

# Start/Stop con toggle
toggle = st.checkbox("🟢 Escuchar mensajes", value=st.session_state.listening)
if toggle and not st.session_state.listening:
    st.session_state.stop_event.clear()
    th = threading.Thread(target=listener, args=(st.session_state.stop_event,), daemon=True)
    st.session_state.listener_thread = th
    th.start()
    st.session_state.listening = True
elif not toggle and st.session_state.listening:
    st.session_state.stop_event.set()
    st.session_state.listening = False

# Procesar recibidos → guardar en historial
while not st.session_state.incoming.empty():
    ts, raw = st.session_state.incoming.get()
    try:
        pkt = json.loads(raw)
        if pkt.get("type") == "message":
            if pkt.get("to") == NODE:
                st.session_state.chat_history.append(("in", now(ts), pkt["from"], pkt["payload"], pkt["ttl"]))
            else:
                st.session_state.chat_history.append(("fwd", now(ts), f"{pkt['from']}→{pkt['to']}", pkt["payload"], pkt["ttl"]))
        elif pkt.get("type") == "hello":
            st.session_state.chat_history.append(("sys", now(ts), pkt["from"], "HELLO", None))
        elif pkt.get("type") == "info":
            st.session_state.chat_history.append(("sys", now(ts), pkt["from"], "INFO", None))
        else:
            st.session_state.chat_history.append(("raw", now(ts), "-", raw, None))
    except Exception:
        st.session_state.chat_history.append(("raw", now(ts), "-", raw, None))

# CSS para estilo WhatsApp
st.markdown("""
<style>
.chat-bubble {
    padding: 8px 12px;
    border-radius: 15px;
    margin: 5px;
    max-width: 70%;
    word-wrap: break-word;
    display: inline-block;
}
.bubble-in {
    background-color: #e5e5ea;
    color: black;
    text-align: left;
    float: left;
}
.bubble-out {
    background-color: #0078fe;
    color: white;
    text-align: right;
    float: right;
}
.bubble-sys {
    background-color: #ffe082;
    color: black;
    text-align: center;
    margin: auto;
}
.clearfix {
    clear: both;
}
</style>
""", unsafe_allow_html=True)

# Mostrar historial tipo chat
st.subheader("Chat")
chat_box = st.container()

for kind, tss, who, msg, ttl in st.session_state.chat_history:
    if kind == "out":
        chat_box.markdown(f"""
        <div class="chat-bubble bubble-out">
            <b>Yo → {who}</b><br>{msg}<br><small>{tss} · ttl={ttl}</small>
        </div><div class="clearfix"></div>
        """, unsafe_allow_html=True)
    elif kind == "in":
        chat_box.markdown(f"""
        <div class="chat-bubble bubble-in">
            <b>{who} → Yo</b><br>{msg}<br><small>{tss} · ttl={ttl}</small>
        </div><div class="clearfix"></div>
        """, unsafe_allow_html=True)
    elif kind == "fwd":
        chat_box.markdown(f"""
        <div class="chat-bubble bubble-in">
            <b>{who}</b><br>{msg}<br><small>{tss} · ttl={ttl}</small>
        </div><div class="clearfix"></div>
        """, unsafe_allow_html=True)
    elif kind == "sys":
        chat_box.markdown(f"""
        <div class="chat-bubble bubble-sys">
            🔔 {msg} de {who} · {tss}
        </div><div class="clearfix"></div>
        """, unsafe_allow_html=True)
    else:
        chat_box.code(f"[{tss}] {msg}")

# Auto-scroll al final
st.write("<script>window.scrollTo(0, document.body.scrollHeight);</script>", unsafe_allow_html=True)
