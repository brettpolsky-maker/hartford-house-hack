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

    if confirm_import and addr2:
        new_prop = {
            "Address": addr2, "Units": int(units2), "Price": float(price2), "Rent": float(rent2), "Status": status2,
            "Positives": positives2, "Negatives": negatives2, "Favorite": False
        }
        st.session_state.properties = [p for p in st.session_state.properties if p["Address"] != addr2]
        st.session_state.properties.append(new_prop)
        save_persisted_properties(st.session_state.properties, auto_commit=auto_commit, gh_owner=gh_owner, gh_repo=gh_repo)
        del st.session_state['gemini_parsed']
        st.rerun()

# 2. FINANCIAL CALCULATION ENGINE
processed_deals = []
for p in st.session_state.properties:
    try:
        units = int(p.get("Units", 1) or 1)
        price = float(p.get("Price", 0) or 0)
        rent_total = float(p.get("Rent", 0) or 0)
    except (ValueError, TypeError):
        units, price, rent_total = 1, 0.0, 0.0

    # Mortgage Calculation
    loan_amount = price * (1 - down_payment_pct)
    term_years = 30
    n = term_years * 12
    monthly_rate = interest_rate / 12 if interest_rate > 0 else 0
    if loan_amount > 0 and monthly_rate > 0:
        mortgage = (loan_amount * monthly_rate) / (1 - (1 + monthly_rate) ** (-n))
    else:
        mortgage = loan_amount / n if loan_amount > 0 else 0.0

    # Operating expenses and NOI (Whole Building Basis)
    total_operating_expenses = rent_total * op_expense_pct
    monthly_noi = rent_total - total_operating_expenses

    # House-hack adjustment (living in one unit)
    user_rent_share = rent_total / units if units > 0 else 0
    remaining_rent = rent_total - user_rent_share
    
    # House-hack Cash Flow = Cash incoming from other units minus 100% of P&I and whole building OPEX
    house_hack_cash_flow = remaining_rent - total_operating_expenses - mortgage

    annual_noi = monthly_noi * 12
    cap_rate = (annual_noi / price) if price > 0 else 0
    annual_cash_flow = house_hack_cash_flow * 12
    down_payment_amount = price * down_payment_pct if price > 0 else 0
    cash_on_cash = (annual_cash_flow / down_payment_amount) if down_payment_amount > 0 else None

    processed_deals.append({
        **p,
        "Est. Mortgage": round(mortgage, 2),
        "Monthly NOI": round(monthly_noi, 2),
        "Annual NOI": round(annual_noi, 2),
        "Cap Rate": round(cap_rate, 4),
        "Net Cash Flow": round(house_hack_cash_flow, 2),
        "Annual Cash Flow": round(annual_cash_flow, 2),
        "Cash on Cash": round(cash_on_cash, 4) if cash_on_cash is not None else None,
        "Favorite": bool(p.get('Favorite', False))
    })

df = pd.DataFrame(processed_deals)

# 3. EXECUTIVE METRICS BAR
col1, col2, col3, col4 = st.columns(4)
col1.metric("🛡️ Pre-Approval Cap", "$725,000", "Expires Sept 2026")
col2.metric("🚀 Total Deals Tracked", len(df))
under_review = len(df[df['Status'] == 'Underwriting']) if not df.empty else 0
col3.metric("🧙‍♂️ Deals in Underwriting", under_review)

best_deal = "None"
if not df.empty and "Net Cash Flow" in df.columns:
    if df["Net Cash Flow"].notna().any():
        best_idx = df["Net Cash Flow"].idxmax()
        if pd.notna(best_idx):
            best_deal = df.loc[best_idx, "Address"]
col4.metric("💪 Top Cash-Flowing Option", best_deal)

st.markdown("---")

# 4. MASTER DEAL PIPELINE TABLE
st.subheader("📊 Master Pipeline Overview")
display_cols = ["Address", "Units", "Price", "Rent", "Status", "Est. Mortgage", "Monthly NOI", "Annual NOI", "Cap Rate", "Net Cash Flow", "Annual Cash Flow", "Cash on Cash", "Favorite"]

if not df.empty:
    display_df = df[display_cols].copy()
    display_df['Zillow'] = display_df['Address'].apply(zillow_resolve)
    display_df['Redfin'] = display_df['Address'].apply(redfin_link)
    display_df['Realtor'] = display_df['Address'].apply(realtor_link)

    compare_df = display_df.copy()
    for c in ["Price", "Rent", "Est. Mortgage", "Monthly NOI", "Annual NOI", "Net Cash Flow", "Annual Cash Flow", "Cash on Cash"]:
        compare_df[c] = compare_df[c].astype(float)

    for c in ["Price", "Rent", "Est. Mortgage", "Monthly NOI", "Annual NOI", "Net Cash Flow", "Annual Cash Flow"]:
        display_df[c] = display_df[c].apply(lambda x: fmt_currency(x) if pd.notna(x) else "-")

    display_df['Cap Rate'] = display_df['Cap Rate'].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "-")
    display_df['Cash on Cash'] = display_df['Cash on Cash'].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "-")
    display_df['Favorite'] = display_df['Favorite'].apply(lambda v: '⭐' if v else '')

    st.dataframe(display_df, use_container_width=True)

    # Quick links
    st.markdown("---")
    st.subheader("🔗 Quick Property Links")
    rows = []
    for idx, row in display_df.iterrows():
        rows.append(f"<tr><td><b>{row['Address']}</b></td><td><a href='{row['Zillow']}' target='_blank'>🏠 Zillow</a></td><td><a href='{row['Redfin']}' target='_blank'>🔎 Redfin</a></td><td><a href='{row['Realtor']}' target='_blank'>📋 Realtor</a></td></tr>")
    st.markdown("<table>" + "".join(rows) + "</table>", unsafe_allow_html=True)

    # Copy Field
    st.markdown("**Quick Copy Address**")
    copy_choice = st.selectbox("Choose address to copy", display_df['Address'].tolist())
    if st.button("Copy address to field"):
        st.session_state['copied_address'] = copy_choice
    st.text_input("Address (copy from here)", value=st.session_state.get('copied_address', ''), key="copy_field")

    # Side by side comparison
    st.markdown("---")
    st.subheader("⚖️ Compare Listings")
    addresses = df['Address'].tolist()
    selected_for_compare = st.multiselect("Select listings to compare (max 4)", addresses, max_selections=4)
    if selected_for_compare:
        to_compare = compare_df[compare_df['Address'].isin(selected_for_compare)].set_index('Address')
        st.write(to_compare[['Units','Price','Rent','Est. Mortgage','Monthly NOI','Annual NOI','Cap Rate','Net Cash Flow','Annual Cash Flow','Cash on Cash']].transpose())

    # Delete listings
    st.markdown("---")
    st.subheader("🗑️ Manage & Delete Listings")
    selected_for_delete = st.multiselect("Select listings to delete", addresses)
    if st.button("Delete selected listings", key="delete_selected"):
        if selected_for_delete:
            st.session_state.properties = [p for p in st.session_state.properties if p['Address'] not in selected_for_delete]
            save_persisted_properties(st.session_state.properties, auto_commit=auto_commit, gh_owner=gh_owner, gh_repo=gh_repo)
            st.success(f"Deleted {len(selected_for_delete)} listings")
            st.rerun()
else:
    st.info("No properties currently tracked in the pipeline.")
    addresses = []

if st.button("Clear all listings", key="clear_all_confirm"):
    st.session_state.properties = []
    save_persisted_properties(st.session_state.properties, auto_commit=auto_commit, gh_owner=gh_owner, gh_repo=gh_repo)
    st.success("Cleared all listings")
    st.rerun()

# 5. DYNAMIC PROPERTY CARD DEEP-DIVES
st.markdown("---")
st.subheader("🔎 Deep-Dive Property Vetting")
selected_address = st.selectbox("Select a property to view detailed pros/cons:", addresses)

if selected_address and not df.empty:
    deal = df[df['Address'] == selected_address].iloc[0]

    if deal.get('Favorite'):
        st.markdown(f"### {deal['Address']} ⭐ — Favorite Listing")
    else:
        st.markdown(f"### {deal['Address']}")

    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Price", fmt_currency(deal['Price']))
    m_col1.metric("Units", int(deal['Units']))
    m_col2.metric("Monthly NOI", fmt_currency(deal['Monthly NOI']))
    m_col2.metric("Annual NOI", fmt_currency(deal['Annual NOI']))
    m_col3.metric("Cap Rate", f"{deal['Cap Rate']*100:.2f}%" if pd.notna(deal['Cap Rate']) else "-")
    m_col3.metric("Annual Cash Flow", fmt_currency(deal['Annual Cash Flow']))

    st.markdown("---")
    card_col1, card_col2 = st.columns(2)
    with card_col1:
        st.success("### 👍 Top Positives / Upsides")
        for pos in str(deal.get("Positives", "")).split(","):
            if pos.strip():
                st.markdown(f"* **{pos.strip()}**")
    with card_col2:
        st.error("### 👎 Top Negatives / Risks")
        for neg in str(deal.get("Negatives", "")).split(","):
            if neg.strip():
                st.markdown(f"* **{neg.strip()}**")

    st.markdown("---")
    action_col1, action_col2, action_col3 = st.columns(3)
    with action_col1:
        if st.button("🗑️ Delete this listing"):
            st.session_state.properties = [p for p in st.session_state.properties if p['Address'] != selected_address]
            save_persisted_properties(st.session_state.properties, auto_commit=auto_commit, gh_owner=gh_owner, gh_repo=gh_repo)
            st.rerun()
    with action_col2:
        if st.button("⭐ Toggle Favorite"):
            for p in st.session_state.properties:
                if p['Address'] == selected_address:
                    p['Favorite'] = not p.get('Favorite', False)
            save_persisted_properties(st.session_state.properties, auto_commit=auto_commit, gh_owner=gh_owner, gh_repo=gh_repo)
            st.rerun()
    with action_col3:
        if st.button("🔁 Refresh Metrics"):
            st.rerun()
