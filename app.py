import streamlit as st
import pandas as pd
import json
import re
import urllib.parse
import requests
import base64
import os
from pathlib import Path

# Path for optional local persistence
DATA_FILE = Path(__file__).parent / "pipeline.json"

# Set up page config for a premium, wide-screen dashboard look
st.set_page_config(page_title="Hartford House-Hacking Command Center", layout="wide", initial_sidebar_state="expanded")

# Fun superhero header
st.title("🚀 Hartford House-Hacking Command Center — Guardians' Edition")
st.markdown("---")
st.markdown("#### 🛡️ 🧙‍♂️ 💪 💀 👊  — mix of power, mystic, and grit to help you house-hack like a hero")

# ---------- Helper: Gemini text parser ----------
def parse_gemini_text(text: str) -> dict:
    """Parse Gemini content - handles both JSON and plain text formats securely."""
    out = {"Address": "", "Units": 1, "Price": 0.0, "Rent": 0.0, "Status": "Monitoring", "Positives": "", "Negatives": ""}
    if not text:
        return out

    # Try JSON first
    try:
        data = json.loads(text)
        
        # 1. Extract address safely
        address_parts = []
        if data.get("address"):
            address_parts.append(data["address"])
        if data.get("city"):
            address_parts.append(data["city"])
        if data.get("state"):
            address_parts.append(data["state"])
        if address_parts:
            out["Address"] = ", ".join(address_parts)
        else:
            out["Address"] = "Unknown Address"
        
        # 2. Extract units count & rent
        if "totalUnits" in data:
            out["Units"] = int(data["totalUnits"])
        elif "units" in data and isinstance(data["units"], list):
            out["Units"] = len(data["units"])
            total_rent = sum(unit.get("estRent", 0) for unit in data["units"])
            out["Rent"] = float(total_rent) if total_rent else 0.0

        # 3. Extract price (handles both listPrice and listingPrice formats)
        if data.get("listingPrice"):
            out["Price"] = float(data["listingPrice"])
        elif "financials" in data and isinstance(data["financials"], dict):
            if data["financials"].get("listPrice"):
                out["Price"] = float(data["financials"]["listPrice"])
        
        # 4. Extract status
        if data.get("status"):
            out["Status"] = data["status"]
        
        # 5. Extract positives and negatives (checks root level first, then nested analysis)
        pos_list = data.get("positives")
        neg_list = data.get("negatives")
        
        if not pos_list and "analysis" in data and isinstance(data["analysis"], dict):
            pos_list = data["analysis"].get("positives")
            
        if not neg_list and "analysis" in data and isinstance(data["analysis"], dict):
            neg_list = data["analysis"].get("negatives")
            
        if isinstance(pos_list, list):
            out["Positives"] = ", ".join(str(x) for x in pos_list)
        elif isinstance(pos_list, str):
            out["Positives"] = pos_list

        if isinstance(neg_list, list):
            out["Negatives"] = ", ".join(str(x) for x in neg_list)
        elif isinstance(neg_list, str):
            out["Negatives"] = neg_list
        
        return out
        
    except json.JSONDecodeError:
        pass
    
    # Fall back to plain text parsing
    lines = text.split('\n')
    for line in lines:
        line_lower = line.lower()
        
        if 'address' in line_lower and ':' in line:
            parts = line.split(':', 1)
            if len(parts) > 1:
                out["Address"] = parts[1].strip()
        elif 'units' in line_lower and ':' in line:
            parts = line.split(':', 1)
            if len(parts) > 1:
                try:
                    out["Units"] = int(''.join(filter(str.isdigit, parts[1])))
                except:
                    out["Units"] = 1
        elif 'price' in line_lower and ':' in line:
            parts = line.split(':', 1)
            if len(parts) > 1:
                price_str = parts[1].replace('$', '').replace(',', '').strip()
                try:
                    out["Price"] = float(price_str)
                except:
                    pass
        elif 'rent' in line_lower and ':' in line:
            parts = line.split(':', 1)
            if len(parts) > 1:
                rent_str = parts[1].replace('$', '').replace(',', '').strip()
                try:
                    out["Rent"] = float(rent_str)
                except:
                    pass
        elif 'status' in line_lower and ':' in line:
            parts = line.split(':', 1)
            if len(parts) > 1:
                out["Status"] = parts[1].strip()
        elif 'positives' in line_lower and ':' in line:
            parts = line.split(':', 1)
            if len(parts) > 1:
                out["Positives"] = parts[1].strip()
        elif 'negatives' in line_lower and ':' in line:
            parts = line.split(':', 1)
            if len(parts) > 1:
                out["Negatives"] = parts[1].strip()

    return out


# ---------- Persistence helpers ----------
def load_persisted_properties():
    if DATA_FILE.exists():
        try:
            with DATA_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def commit_pipeline_to_github(token: str, owner: str, repo: str, path: str = "pipeline.json", message: str = "Update pipeline.json from app") -> bool:
    try:
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
        api_base = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        content = DATA_FILE.read_bytes()
        b64 = base64.b64encode(content).decode()

        r = requests.get(api_base, headers=headers, timeout=5)
        if r.status_code == 200:
            sha = r.json().get('sha')
            payload = {"message": message, "content": b64, "sha": sha}
            put = requests.put(api_base, headers=headers, json=payload, timeout=10)
            return put.status_code in (200, 201)
        elif r.status_code == 404:
            payload = {"message": message, "content": b64}
            put = requests.put(api_base, headers=headers, json=payload, timeout=10)
            return put.status_code in (200, 201)
        else:
            return False
    except Exception:
        return False


def save_persisted_properties(props, auto_commit=False, gh_owner=None, gh_repo=None):
    try:
        with DATA_FILE.open("w", encoding="utf-8") as f:
            json.dump(props, f, indent=2)
    except Exception:
        return False

    if auto_commit:
        token = None
        try:
            token = st.secrets.get("GITHUB_PAT")
        except Exception:
            token = None
        if not token:
            token = os.environ.get("GITHUB_PAT")
        if token and gh_owner and gh_repo:
            return commit_pipeline_to_github(token, gh_owner, gh_repo)
    return True


# ---------- Small helpers ----------
def fmt_currency(x):
    try:
        return f"${x:,.0f}"
    except Exception:
        return "-"


def make_slug(address: str) -> str:
    if not address:
        return ""
    s = address.lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s


@st.cache_data
def zillow_resolve(address: str) -> str:
    if not address:
        return ""
    slug = make_slug(address)
    homedetails = f"https://www.zillow.com/homedetails/{slug}_rb/"
    search = f"https://www.zillow.com/homes/{urllib.parse.quote_plus(address)}_rb/"
    try:
        r = requests.get(homedetails, allow_redirects=True, timeout=5)
        if r.status_code == 200 and "homedetails" in r.url:
            return r.url
        return search
    except Exception:
        return search


def redfin_link(address: str) -> str:
    if not address:
        return ""
    return f"https://www.redfin.com/search?q={urllib.parse.quote_plus(address)}"


def realtor_link(address: str) -> str:
    if not address:
        return ""
    return f"https://www.realtor.com/realestateandhomes-search/{urllib.parse.quote_plus(address)}"


# 1. SIDEBAR: Global Financial Variables & Deal Input
st.sidebar.header("⚙️ Global Deal Mechanics")
interest_rate = st.sidebar.slider("Interest Rate (%)", 5.0, 8.5, 6.5, 0.1) / 100
down_payment_pct = st.sidebar.slider("Down Payment (%)", 3.5, 20.0, 5.0, 0.5) / 100
op_expense_pct = st.sidebar.slider("Operating Expenses (% of Rent)", 35, 55, 45, 5) / 100

st.sidebar.markdown("---")
st.sidebar.header("🔒 Persistence & GitHub")
auto_commit = st.sidebar.checkbox("Auto-commit pipeline.json to GitHub on changes", value=False)
gh_owner = st.sidebar.text_input("GitHub owner (org/user)", value="brettpolsky-maker") if auto_commit else None
gh_repo = st.sidebar.text_input("GitHub repo", value="hartford-house-hack") if auto_commit else None

st.sidebar.markdown("---")
st.sidebar.header("➕ Add / Update Property")
with st.sidebar.form("property_form", clear_on_submit=True):
    address = st.text_input("Property Address")
    units = st.number_input("Number of Units", min_value=1, max_value=10, value=3)
    price = st.number_input("Purchase Price ($)", min_value=0, value=400000, step=5000)
    rent = st.number_input("Est. Gross Monthly Rent ($)", min_value=0, value=4500, step=100)
    status = st.selectbox("Pipeline Status", ["Monitoring", "Screened", "Underwriting", "Offer Made", "Dead Deal"])
    positives = st.text_area("Positives (comma separated)")
    negatives = st.text_area("Negatives (comma separated)")
    submit = st.form_submit_button("Sync to Pipeline")

st.sidebar.markdown("---")
st.sidebar.header("🔁 Import from Gemini")
gemini_text = st.sidebar.text_area("Paste Gemini output here", height=150)
import_clicked = st.sidebar.button("Parse & Prepare Import")

st.sidebar.markdown("---")
st.sidebar.header("🐛 Parser Debug Panel")
show_debug = st.sidebar.checkbox("Show parsed data (for debugging)")

if show_debug and gemini_text and gemini_text.strip():
    parsed_data = parse_gemini_text(gemini_text)
    st.sidebar.markdown("**Raw parsed output:**")
    st.sidebar.json(parsed_data)

# Initialize Session State Data if it doesn't exist
if 'properties' not in st.session_state:
    st.session_state.properties = [
        {"Address": "6-Family Hartford", "Units": 6, "Price": 830000, "Rent": 7200, "Status": "Underwriting", "Positives": "Max scale with 5 income streams, Commercial financing eligibility, High upside", "Negatives": "Older building, Multi-unit complexity", "Favorite": False},
        {"Address": "40 Allen Place", "Units": 3, "Price": 420000, "Rent": 4500, "Status": "Underwriting", "Positives": "Turnkey condition requires low cap-ex, Leaves budget breathing room, Better schools", "Negatives": "Market softening concerns", "Favorite": False},
        {"Address": "19-21 Mill St", "Units": 2, "Price": 340000, "Rent": 3100, "Status": "Screened", "Positives": "Separate utilities/mechanicals, Lowest purchase price and risk, Light management", "Negatives": "Smaller revenue base", "Favorite": False},
        {"Address": "285 Zion St", "Units": 4, "Price": 490000, "Rent": 5200, "Status": "Monitoring", "Positives": "Good unit mix, Emerging location", "Negatives": "Awaiting rent roll verification", "Favorite": False},
        {"Address": "98-100 Capen St", "Units": 3, "Price": 380000, "Rent": 3900, "Status": "Monitoring", "Positives": "Low entry price, Strong initial cap rate", "Negatives": "Drive by required, Needs inspection", "Favorite": False},
    ]
    persisted = load_persisted_properties()
    if persisted:
        existing_addresses = {p['Address'] for p in st.session_state.properties}
        for pp in persisted:
            if pp.get('Address') and pp['Address'] not in existing_addresses:
                if 'Favorite' not in pp:
                    pp['Favorite'] = False
                st.session_state.properties.append(pp)

if submit and address:
    new_prop = {
        "Address": address, "Units": int(units), "Price": float(price), "Rent": float(rent), "Status": status,
        "Positives": positives, "Negatives": negatives, "Favorite": False
    }
    st.session_state.properties = [p for p in st.session_state.properties if p["Address"] != address]
    st.session_state.properties.append(new_prop)
    save_persisted_properties(st.session_state.properties, auto_commit=auto_commit, gh_owner=gh_owner, gh_repo=gh_repo)

if import_clicked and gemini_text and gemini_text.strip():
    st.session_state['gemini_parsed'] = parse_gemini_text(gemini_text)

parsed = st.session_state.get('gemini_parsed')
if parsed:
    st.sidebar.markdown("**Parsed result — edit values and confirm import**")
    with st.sidebar.form("gemini_confirm_form", clear_on_submit=False):
    addr2 = st.text_input("Address", parsed.get("Address", ""))
    units2 = st.number_input("Units", min_value=1, max_value=100, value=int(parsed.get("Units", 1)))
    price2 = st.number_input("Price ($)", min_value=0.0, value=float(parsed.get("Price", 0.0)))
    rent2 = st.number_input("Rent ($)", min_value=0.0, value=float(parsed.get("Rent", 0.0)))
    status_options = ["Monitoring", "Screened", "Underwriting", "Offer Made", "Dead Deal"]
    status_index = status_options.index(parsed.get("Status", "Monitoring")) if parsed.get("Status") in status_options else 0
    status2 = st.selectbox("Status", status_options, index=status_index)
    positives2 = st.text_area("Positives", parsed.get("Positives", ""), height=100)
    negatives2 = st.text_area("Negatives", parsed.get("Negatives", ""), height=100)
    confirm_import = st.form_submit_button("Confirm Import to Pipeline")

