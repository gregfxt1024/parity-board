import streamlit as st
import os
import time
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI

# ==========================================
# 1. SETUP & UI CONFIG
# ==========================================
st.set_page_config(page_title="Parity Boardroom", page_icon="👔", layout="wide")
load_dotenv()

def get_key(name):
    if name in st.secrets:
        return st.secrets[name]
    return os.getenv(name)

KEYS = {
    "GOOGLE": get_key("GOOGLE_API_KEY"),
    "XAI": get_key("XAI_API_KEY"),
    "OPENAI": get_key("OPENAI_API_KEY")
}

# ==========================================
# 2. CLIENT INITIALIZATION (Dynamic)
# ==========================================
@st.cache_resource
def init_clients():
    clients = {}
    
    # --- A. GOOGLE (VC) ---
    if KEYS["GOOGLE"]:
        try:
            genai.configure(api_key=KEYS["GOOGLE"])
            # PRIORITY: GEMINI 3 -> 1.5 PRO (Quality First)
            priority = [
                'models/gemini-3.0-pro', 
                'models/gemini-3-pro', 
                'models/gemini-1.5-pro-latest',
                'models/gemini-1.5-pro'
            ]
            try:
                available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                clients["VC_AVAILABLE"] = available
                # Default to best Pro model available
                clients["VC_DEFAULT"] = next((m for m in priority if m in available), available[0])
            except:
                clients["VC_AVAILABLE"] = ["models/gemini-1.5-flash"]
                clients["VC_DEFAULT"] = "models/gemini-1.5-flash"
                
            clients["VC_CLIENT"] = genai 
        except Exception as e: st.error(f"Google Init Failed: {e}")

    # --- B. OPENAI (ARCHITECT) ---
    if KEYS["OPENAI"]:
        try:
            clients["ARCHITECT"] = OpenAI(api_key=KEYS["OPENAI"])
        except Exception as e: st.error(f"OpenAI Init Failed: {e}")

    # --- C. XAI (SCOUT) ---
    if KEYS["XAI"]:
        try:
            clients["SCOUT"] = OpenAI(api_key=KEYS["XAI"], base_url="https://api.x.ai/v1")
        except Exception as e: st.error(f"xAI Init Failed: {e}")
    
    return clients

clients = init_clients()

# ==========================================
# 3. SIDEBAR CONFIGURATION
# ==========================================
with st.sidebar:
    st.header("⚙️ Boardroom Settings")
    
    # A. STYLE TOGGLE
    response_style = st.radio(
        "Response Style", 
        ["Executive (Brief)", "Founder (Detailed)"],
        index=0
    )
    
    st.divider()
    
    # B. MODEL SELECTOR (VC)
    st.subheader("🧠 VC Brain")
    vc_options = clients.get("VC_AVAILABLE", ["models/gemini-1.5-flash"])
    default_vc = clients.get("VC_DEFAULT", vc_options[0])
    
    # Ensure default is selected index
    try:
        def_idx = vc_options.index(default_vc)
    except:
        def_idx = 0
            
    selected_vc_model = st.selectbox(
        "Model ID", 
        vc_options, 
        index=def_idx
    )
    
    st.divider()
    
    # C. MEMORY CONTROL
    if st.button("🗑️ Wipe Memory"):
        if os.path.exists("context.md"):
            os.remove("context.md")
        st.session_state.messages = []
        st.toast("Memory Wiped.")

# ==========================================
# 4. THE ROUTER (THE SMART VC)
# ==========================================
def ask_vc_router(prompt, model_id):
    """Decides which agent should handle the request."""
    if "VC_CLIENT" not in clients: return "ALL"
    
    model = clients["VC_CLIENT"].GenerativeModel(model_id)
    system_instruction = (
        "You are the CEO of an AI agency. Your goal is EFFICIENCY.\n"
        "Analyze the user's prompt and decide who should answer.\n\n"
        "ROLES:\n"
        "1. SCOUT: Market research, news, trends, searching for info, 'Find me X'.\n"
        "2. ARCHITECT: Code, tech stacks, libraries, 'Write a script', implementation.\n"
        "3. VC: Business strategy, ROI, 'Should I do this?', final verdict.\n"
        "4. ALL: Complex requests requiring research -> code -> decision.\n\n"
        "OUTPUT: Return ONLY one word: 'SCOUT', 'ARCHITECT', 'VC', or 'ALL'."
    )
    
    try:
        resp = model.generate_content(system_instruction + "\n\nPROMPT: " + prompt)
        decision = resp.text.strip().upper().replace("*", "")
        # Safety fallback
        if decision not in ["SCOUT", "ARCHITECT", "VC", "ALL"]: return "ALL"
        return decision
    except:
        return "ALL"

# ==========================================
# 5. DIRECTOR AGENTS
# ==========================================

def get_agent_rules(agent_name):
    if os.path.exists("rules.md"):
        with open("rules.md", "r", encoding="utf-8") as f:
            content = f.read()
        return f"\n\n[YOUR TRAINED RULES]:\n{content}" if agent_name in content else ""
    return ""

def ask_scout(prompt, history, style):
    if "SCOUT" not in clients: return "❌ Scout (Grok) missing."
    growth_prompt = get_agent_rules("SCOUT")
    
    if style == "Executive (Brief)":
        style_inst = "CORE DIRECTIVE: EXTREME BREVITY. Max 150 words. Bullets ONLY."
    else:
        style_inst = "CORE DIRECTIVE: DETAILED ANALYSIS. Provide context and reasoning."

    system_prompt = (
        f"You are Scout. History:\n{history}\n{growth_prompt}\n\n"
        f"{style_inst}\n"
        "CITATION REQUIRED: [Link](url) format."
    )

    try:
        resp = clients["SCOUT"].chat.completions.create(
            model="grok-3", 
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
        )
        return f"**[🤖 Grok-3]**\n{resp.choices[0].message.content}"
    except Exception as e: return f"⚠️ Scout Crashed: {e}"

def ask_architect(prompt, history, style):
    if "ARCHITECT" not in clients: return "❌ Architect (GPT-4o) missing."
    growth_prompt = get_agent_rules("ARCHITECT")
    
    if style == "Executive (Brief)":
        style_inst = "CORE DIRECTIVE: CODE ONLY. Code Block first. Max 3 sentences explanation."
    else:
        style_inst = "CORE DIRECTIVE: TECHNICAL SPEC. Include reasoning and trade-offs."

    system_prompt = (
        f"You are Architect. History:\n{history}\n{growth_prompt}\n\n"
        f"{style_inst}\n"
        "NO HALLUCINATED LIBRARIES."
    )

    try:
        resp = clients["ARCHITECT"].chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Task: {prompt}"}]
        )
        return f"**[🤖 GPT-4o]**\n{resp.choices[0].message.content}"
    except Exception as e: return f"⚠️ Architect Crashed: {e}"

def ask_vc(prompt, history, style, model_id):
    if "VC_CLIENT" not in clients: return "❌ VC (Gemini) missing."
    growth_prompt = get_agent_rules("VC")
    
    if style == "Executive (Brief)":
        style_inst = "STYLE: VERDICT (YES/NO) + 1 Bullet Point Reason. Max 50 words."
    else:
        style_inst = "STYLE: Detailed Critique, Principles (Lean/Blue Ocean), Risk Analysis."

    full_prompt = (
        f"You are VC. History:\n{history}\n{growth_prompt}\n\n"
        "Critique this:\n" + prompt + "\n\n"
        f"{style_inst}"
    )
    
    model = clients["VC_CLIENT"].GenerativeModel(model_id)
    for attempt in range(3):
        try:
            resp = model.generate_content(full_prompt)
            return f"**[🤖 {model_id}]**\n{resp.text}"
        except Exception as e:
            if "429" in str(e): time.sleep(2); continue
            return f"⚠️ VC Crashed: {e}"
    return "⚠️ VC Timed Out"

# ==========================================
# 6. EXECUTION UI
# ==========================================

st.title("👔 Parity Boardroom")

# History
if "messages" not in st.session_state: st.session_state.messages = []
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# INPUT
if prompt := st.chat_input("Direct the board..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Load Context
    history = ""
    if os.path.exists("context.md"):
        with open("context.md", "r", encoding="utf-8") as f: history = f.read()

    # ROUTING LOGIC
    target = "ALL"
    
    # 1. Manual Override
    if "@scout" in prompt.lower(): target = "SCOUT"
    elif "@architect" in prompt.lower(): target = "ARCHITECT"
    elif "@vc" in prompt.lower(): target = "VC"
    
    # 2. VC Smart Router (Default)
    else:
        with st.status("VC is deciding who to ask...", expanded=False) as status:
            target = ask_vc_router(prompt, selected_vc_model)
            status.update(label=f"VC delegated to: {target}", state="complete", expanded=False)

    # EXECUTION
    with st.chat_message("assistant"):
        final_response = ""
        
        # Helper
        def run(name, func, p, h, **k):
            with st.spinner(f"{name} is working..."):
                r = func(p, h, **k)
                st.write(r)
            return r

        if target == "SCOUT":
            resp = run("Scout", ask_scout, prompt, history, style=response_style)
            final_response = f"**SCOUT:**\n{resp}"
            
        elif target == "ARCHITECT":
            resp = run("Architect", ask_architect, prompt, history, style=response_style)
            final_response = f"**ARCHITECT:**\n{resp}"
            
        elif target == "VC":
            resp = run("VC", ask_vc, prompt, history, style=response_style, model_id=selected_vc_model)
            final_response = f"**VC:**\n{resp}"
            
        else: # ALL
            tab1, tab2, tab3 = st.tabs(["Scout", "Architect", "VC"])
            with tab1: r1 = run("Scout", ask_scout, f"Analyze: {prompt}", history, style=response_style)
            with tab2: r2 = run("Architect", ask_architect, f"Context: {r1}\n\nTask: Tech Spec.", history, style=response_style)
            with tab3: r3 = run("VC", ask_vc, f"Scout: {r1}\n\nArchitect: {r2}\n\nVerdict?", history, style=response_style, model_id=selected_vc_model)
            final_response = f"### BOARD MEETING\n\n**SCOUT:**\n{r1}\n\n**ARCHITECT:**\n{r2}\n\n**VC VERDICT:**\n{r3}"

        st.session_state.messages.append({"role": "assistant", "content": final_response})
        
        with open("context.md", "a", encoding="utf-8") as f:
            f.write(f"\n\nDATE: {time.strftime('%Y-%m-%d %H:%M')}\nUSER: {prompt}\nBOARD: {final_response}")