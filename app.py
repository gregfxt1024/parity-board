import streamlit as st
import os
import time
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI

# ==========================================
# 1. SETUP & AUTH
# ==========================================
st.set_page_config(page_title="Parity Boardroom", page_icon="👔", layout="centered")
load_dotenv()

# KEYS
KEYS = {
    "GOOGLE": os.getenv("GOOGLE_API_KEY"),
    "XAI": os.getenv("XAI_API_KEY"),
    "OPENAI": os.getenv("OPENAI_API_KEY")
}

# CLIENTS
@st.cache_resource
def init_clients():
    clients = {}
    # Google (VC)
    if KEYS["GOOGLE"]:
        genai.configure(api_key=KEYS["GOOGLE"])
        # Audit for best model
        try:
            my_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            # Priority: 3.0 -> 2.5 -> 2.0 -> 1.5
            priority = ['models/gemini-3-pro-preview', 'models/gemini-2.5-pro', 'models/gemini-2.0-flash', 'models/gemini-1.5-pro-latest']
            chosen = next((m for m in priority if m in my_models), my_models[0])
            clients["VC"] = genai.GenerativeModel(chosen)
            clients["VC_NAME"] = chosen
        except: pass

    # OpenAI (Architect)
    if KEYS["OPENAI"]:
        clients["ARCHITECT"] = OpenAI(api_key=KEYS["OPENAI"])

    # xAI (Scout)
    if KEYS["XAI"]:
        clients["SCOUT"] = OpenAI(api_key=KEYS["XAI"], base_url="https://api.x.ai/v1")
    
    return clients

clients = init_clients()

# ==========================================
# 2. AGENT LOGIC
# ==========================================
def ask_scout(prompt, history):
    if "SCOUT" not in clients: return "❌ Scout (Grok) missing."
    try:
        resp = clients["SCOUT"].chat.completions.create(
            model="grok-3",
            messages=[{"role": "system", "content": f"You are Scout. History:\n{history}\n\nREQUIREMENT: Provide thought process."}, 
                      {"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content
    except Exception as e: return f"⚠️ Scout crashed: {e}"

def ask_architect(prompt, history):
    if "ARCHITECT" not in clients: return "❌ Architect (GPT-4o) missing."
    try:
        resp = clients["ARCHITECT"].chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": f"You are Architect. History:\n{history}\n\nREQUIREMENT: Include 'Technical Reasoning'."}, 
                      {"role": "user", "content": f"Task: {prompt}"}]
        )
        return resp.choices[0].message.content
    except Exception as e: return f"⚠️ Architect crashed: {e}"

def ask_vc(prompt, history):
    if "VC" not in clients: return "❌ VC (Gemini) missing."
    try:
        resp = clients["VC"].generate_content(f"You are VC. History:\n{history}\n\nCritique:\n{prompt}\n\nREQUIREMENT: Cite business principles.")
        return resp.text
    except Exception as e: return f"⚠️ VC crashed: {e}"

# ==========================================
# 3. UI LAYOUT (Mobile Friendly)
# ==========================================

st.title("👔 Parity Boardroom")

# Sidebar Status
with st.sidebar:
    st.header("Syndicate Status")
    st.success(f"Scout: {'Online (Grok-3)' if 'SCOUT' in clients else 'Offline'}")
    st.success(f"Architect: {'Online (GPT-4o)' if 'ARCHITECT' in clients else 'Offline'}")
    st.success(f"VC: {'Online (' + clients.get('VC_NAME', 'Unknown') + ')' if 'VC' in clients else 'Offline'}")
    
    if st.button("Clear Memory"):
        if os.path.exists("context.md"):
            os.remove("context.md")
        st.toast("Memory Wiped.")

# Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# INPUT BOX
if prompt := st.chat_input("Direct the board..."):
    # 1. User Message
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Load Context
    history = ""
    if os.path.exists("context.md"):
        with open("context.md", "r", encoding="utf-8") as f: history = f.read()

    # 2. Router
    target = "ALL"
    if "@scout" in prompt.lower(): target = "SCOUT"
    elif "@architect" in prompt.lower(): target = "ARCHITECT"
    elif "@vc" in prompt.lower(): target = "VC"

    # 3. Generate Response
    with st.chat_message("assistant"):
        final_response = ""
        
        if target == "SCOUT":
            with st.status("Scout is thinking...", expanded=True):
                resp = ask_scout(prompt, history)
                st.write(resp)
            final_response = f"**SCOUT:**\n{resp}"
            
        elif target == "ARCHITECT":
            with st.status("Architect is designing...", expanded=True):
                resp = ask_architect(prompt, history)
                st.write(resp)
            final_response = f"**ARCHITECT:**\n{resp}"
            
        elif target == "VC":
            with st.status("VC is deciding...", expanded=True):
                resp = ask_vc(prompt, history)
                st.write(resp)
            final_response = f"**VC:**\n{resp}"
            
        else: # FULL BOARD MEETING
            tab1, tab2, tab3 = st.tabs(["Scout", "Architect", "VC"])
            
            with tab1:
                with st.spinner("Scout researching..."):
                    r1 = ask_scout(f"Analyze: {prompt}", history)
                    st.markdown(r1)
            
            with tab2:
                with st.spinner("Architect designing..."):
                    r2 = ask_architect(f"Context: {r1}\n\nTask: Technical Spec.", history)
                    st.markdown(r2)
            
            with tab3:
                with st.spinner("VC judging..."):
                    r3 = ask_vc(f"Scout: {r1}\n\nArchitect: {r2}\n\nDecision?", history)
                    st.markdown(r3)
            
            final_response = f"### BOARD MINUTES\n\n**SCOUT:**\n{r1}\n\n**ARCHITECT:**\n{r2}\n\n**VC VERDICT:**\n{r3}"

        # Save to session
        st.session_state.messages.append({"role": "assistant", "content": final_response})
        
        # Save to persistent memory
        with open("context.md", "a", encoding="utf-8") as f:
            f.write(f"\n\nDATE: {time.strftime('%Y-%m-%d %H:%M')}\nUSER: {prompt}\nBOARD: {final_response}")