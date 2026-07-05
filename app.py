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
    """Parse Gemini content - handles both JSON and plain text formats."""
    out = {"Address": "", "Units": 1, "Price": 0.0, "Rent": 0.0, "Status": "Monitoring", "Positives": "", "Negatives": ""}
    if not text:
        return out

    # Try JSON first
    try:
        data = json.loads(text)
        
        # Extract address
        address_parts = []
        if data.get("address"):
            address_parts.append(data["address"])
        if data.get("city"):
            address_parts.append(data["city"])
        if data.get("state"):
            address_parts.append(data["state"])
        if address_parts:
            out["Address"] = ", ".join(address_parts)
        
        # Extract units count
        if "units" in data and isinstance(data["units"], list):
            out["Units"] = len(data["units"])
            # Sum up rent from all units
            total_rent = sum(unit.get("estRent", 0) for unit in data["units"])
            out["Rent"] = float(total_rent) if total_rent else 0.0
        
        # Extract price
        if "financials" in data and data["financials"].get("listPrice"):
            out["Price"] = float(data["financials"]["listPrice"])
        
        # Extract status
        if data.get("status"):
            out["Status"] = data["status"]
        
        # Extract positives and negatives
        if "analysis" in data:
            if data["analysis"].get("positives"):
                out["Positives"] = ", ".join(data["analysis"]["positives"])
            if data["analysis"].get("negatives"):
                out["Negatives"] = ", ".join(data["analysis"]["negatives"])
        
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


# GitHub commit helper
def commit_pipeline_to_github(token: str, owner: str, repo: str, path: str = "pipeline.json", message: str = "Update pipeline.json from app") -> bool:
    """Create or update pipeline.json in the given GitHub repo using the provided PAT."""
    try:
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
        api_base = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        # Read local file
        content = DATA_FILE.read_bytes()
        b64 = base64.b64encode(content).decode()

        # Check if file exists to get sha
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

    # Optionally commit to GitHub if token available and user enabled
    if auto_commit:
        token = None
        # Prefer Streamlit secrets, fallback to environment variable
        try:
            token = st.secrets.get("GITHUB_PAT")
        except Exception:
            token = None
        if not token:
            token = os.environ.get("GITHUB_PAT")
        if token and gh_owner and gh_repo:
            success = commit_pipeline_to_github(token, gh_owner, gh_repo)
            return success
    return True


# ---------- Small helpers ----------
def fmt_currency(x):
    try:
        return f"${x:,.0f}"
    except Exception:
        return "-"


def fmt_pct(x):
    try:
        return f"{x*100:.2f}%"
    except Exception:
        return "-"


def make_slug(address: str) -> str:
    """Create a simple slug from the address for best-effort Zillow permalink attempts."""
    if not address:
        return ""
    s = address.lower()
    # remove characters that are not alphanumeric or spaces
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s


# Cache decorator helper (st.cache_data if available)
try:
    cache = st.cache_data
except Exception:
    cache = st.cache


@cache
def zillow_resolve(address: str) -> str:
    """Try to resolve an address to a Zillow homedetails permalink; fall back to a Zillow search URL.
    We perform a best-effort HTTP request to detect if the homedetails slug redirects to a real page. This is heuristic.
    """
    if not address:
        return ""
    slug = make_slug(address)
    homedetails = f"https://www.zillow.com/homedetails/{slug}_rb/"
    search = f"https://www.zillow.com/homes/{urllib.parse.quote_plus(address)}_rb/"

    try:
        r = requests.get(homedetails, allow_redirects=True, timeout=5)
        final = r.url
        if r.status_code == 200 and "homedetails" in final:
            return final
        else:
            return search
    except Exception:
        return search


def redfin_link(address: str) -> str:
    if not address:
        return ""
    q = urllib.parse.quote_plus(address)
    return f"https://www.redfin.com/search?q={q}"


def realtor_link(address: str) -> str:
    if not address:
        return ""
    q = urllib.parse.quote_plus(address)
    return f"https://www.realtor.com/realestateandhomes-search/{q}"


# 1. SIDEBAR: Global Financial Variables & Deal Input
st.sidebar.header("⚙️ Global Deal Mechanics")
interest_rate = st.sidebar.slider("Interest Rate (%)", 5.0, 8.5, 6.5, 0.1) / 100
down_payment_pct = st.sidebar.slider("Down Payment (%)", 3.5, 20.0, 5.0, 0.5) / 100
op_expense_pct = st.sidebar.slider("Operating Expenses (% of Rent)", 35, 55, 45, 5) / 100

# GitHub auto-commit controls in sidebar
st.sidebar.markdown("---")
st.sidebar.header("🔒 Persistence & GitHub")
auto_commit = st.sidebar.checkbox("Auto-commit pipeline.json to GitHub on changes", value=False)
gh_owner = st.sidebar.text_input("GitHub owner (org/user)", value="brettpolsky-maker") if auto_commit else None
gh_repo = st.sidebar.text_input("GitHub repo", value="hartford-house-hack") if auto_commit else None
if auto_commit:
    st.sidebar.caption("Store a GitHub Personal Access Token named GITHUB_PAT in Streamlit secrets or as an env var for commits to work.")

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

# Import from Gemini (Option A)
st.sidebar.markdown("---")
st.sidebar.header("🔁 Import from Gemini")
gemini_text = st.sidebar.text_area("Paste Gemini output here")
import_clicked = st.sidebar.button("Parse & Prepare Import")

# Management tools: delete & compare
st.sidebar.markdown("---")
st.sidebar.header("🛠️ Manage Listings")

# Initialize Session State Data if it doesn't exist
if 'properties' not in st.session_state:
    # Start from the built-in defaults, then merge persisted ones
    st.session_state.properties = [
        {"Address": "6-Family Hartford", "Units": 6, "Price": 830000, "Rent": 7200, "Status": "Underwriting", "Positives": "Max scale with 5 income streams, Commercial financing eligibility, High upside", "Negatives": "Older building, Multi-unit complexity", "Favorite": False},
        {"Address": "40 Allen Place", "Units": 3, "Price": 420000, "Rent": 4500, "Status": "Underwriting", "Positives": "Turnkey condition requires low cap-ex, Leaves budget breathing room, Better schools", "Negatives": "Market softening concerns", "Favorite": False},
        {"Address": "19-21 Mill St", "Units": 2, "Price": 340000, "Rent": 3100, "Status": "Screened", "Positives": "Separate utilities/mechanicals, Lowest purchase price and risk, Light management", "Negatives": "Smaller revenue base", "Favorite": False},
        {"Address": "285 Zion St", "Units": 4, "Price": 490000, "Rent": 5200, "Status": "Monitoring", "Positives": "Good unit mix, Emerging location", "Negatives": "Awaiting rent roll verification", "Favorite": False},
        {"Address": "98-100 Capen St", "Units": 3, "Price": 380000, "Rent": 3900, "Status": "Monitoring", "Positives": "Low entry price, Strong initial cap rate", "Negatives": "Drive by required, Needs inspection", "Favorite": False},
    ]
    # Merge persisted properties (avoid duplicates by Address)
    persisted = load_persisted_properties()
    if persisted:
        existing_addresses = {p['Address'] for p in st.session_state.properties}
        for pp in persisted:
            if pp.get('Address') and pp['Address'] not in existing_addresses:
                # ensure Favorite defaults to False if missing
                if 'Favorite' not in pp:
                    pp['Favorite'] = False
                st.session_state.properties.append(pp)

# Append new property entry if form submitted
if submit and address:
    new_prop = {
        "Address": address, "Units": units, "Price": price, "Rent": rent, "Status": status,
        "Positives": positives, "Negatives": negatives, "Favorite": False
    }
    # Overwrite if address matches, else append
    st.session_state.properties = [p for p in st.session_state.properties if p["Address"] != address]
    st.session_state.properties.append(new_prop)
    # Persist to local file (and optionally commit)
    save_persisted_properties(st.session_state.properties, auto_commit=auto_commit, gh_owner=gh_owner, gh_repo=gh_repo)

# --- GEMINI import flow using session_state so form survives reruns ---
# When Parse is clicked, store parsed payload in session_state
if import_clicked and gemini_text and gemini_text.strip():
    parsed_data = parse_gemini_text(gemini_text)
    st.session_state['gemini_parsed'] = parsed_data
    # Debug: Show what was parsed
    if parsed_data.get("Address"):
        st.sidebar.success(f"✓ Parsed: {parsed_data['Address']}")
    else:
        st.sidebar.warning("⚠ No address found. Check format.")

# If we have a parsed payload stored, render the confirmation form
parsed = st.session_state.get('gemini_parsed')
if parsed:
    st.sidebar.markdown("**Parsed result — edit values and confirm import**")
    with st.sidebar.form("gemini_confirm_form", clear_on_submit=False):
        addr2 = st.text_input("Address", parsed.get("Address", ""))
        units2 = st.number_input("Units", min_value=1, max_value=100, value=int(parsed.get("Units", 1)))
        price2 = st.number_input("Price ($)", min_value=0.0, value=float(parsed.get("Price", 0.0)))
        rent2 = st.number_input("Rent ($)", min_value=0.0, value=float(parsed.get("Rent", 0.0)))
        status_options = ["Monitoring", "Screened", "Underwriting", "Offer Made", "Dead Deal"]
        try:
            status_index = status_options.index(parsed.get("Status", "Monitoring"))
        except ValueError:
            status_index = 0
        status2 = st.selectbox("Status", status_options, index=status_index)
        positives2 = st.text_area("Positives", parsed.get("Positives", ""))
        negatives2 = st.text_area("Negatives", parsed.get("Negatives", ""))
        confirm_import = st.form_submit_button("Confirm Import to Pipeline")

    if confirm_import and addr2:
        new_prop = {
            "Address": addr2, "Units": units2, "Price": price2, "Rent": rent2, "Status": status2,
            "Positives": positives2, "Negatives": negatives2, "Favorite": False
        }
        # Overwrite if address matches, else append
        st.session_state.properties = [p for p in st.session_state.properties if p["Address"] != addr2]
        st.session_state.properties.append(new_prop)
        saved = save_persisted_properties(st.session_state.properties, auto_commit=auto_commit, gh_owner=gh_owner, gh_repo=gh_repo)
        if saved:
            st.sidebar.success("Imported and saved to pipeline.json")
        else:
            st.sidebar.warning("Imported to session, but failed to save pipeline.json or commit to GitHub")
        # clear parsed state so the form goes away on next rerun
        del st.session_state['gemini_parsed']

# 2. FINANCIAL CALCULATION ENGINE
processed_deals = []
for p in st.session_state.properties:
    # Defensive defaults
    units = p.get("Units", 1) or 1
    price = p.get("Price", 0) or 0
    rent_total = p.get("Rent", 0) or 0

    # Mortgage Calculation (monthly P&I)
    loan_amount = price * (1 - down_payment_pct)
    term_years = 30
    n = term_years * 12
    monthly_rate = interest_rate / 12 if interest_rate > 0 else 0
    if loan_amount > 0 and monthly_rate > 0:
        mortgage = (loan_amount * monthly_rate) / (1 - (1 + monthly_rate) ** (-n))
    elif loan_amount > 0 and monthly_rate == 0:
        mortgage = loan_amount / n
    else:
        mortgage = 0.0

    # Operating expenses and NOI
    total_operating_expenses = rent_total * op_expense_pct
    monthly_noi = rent_total - total_operating_expenses

    # House-hack logic (owner occupies one unit)
    user_rent_share = rent_total / units if units > 0 else 0
    remaining_rent = rent_total - user_rent_share

    op_expenses_on_remaining = 0.0
    if rent_total > 0:
        op_expenses_on_remaining = total_operating_expenses * (remaining_rent / rent_total)

    house_hack_cash_flow = remaining_rent - op_expenses_on_remaining - mortgage

    # Additional metrics
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
        "Favorite": p.get('Favorite', False)
    })


# Build dataframe
df = pd.DataFrame(processed_deals)

# 3. EXECUTIVE METRICS BAR
col1, col2, col3, col4 = st.columns(4)
col1.metric("🛡️ Pre-Approval Cap", "$725,000", "Expires Sept 2026")
col2.metric("🚀 Total Deals Tracked", len(df))
under_review = len(df[df['Status'] == 'Underwriting']) if not df.empty else 0
col3.metric("🧙‍♂️ Deals in Underwriting", under_review)

# Safely determine best deal
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
# Add columns for display including favorites, annuals and cap/coc
display_cols = ["Address", "Units", "Price", "Rent", "Status", "Est. Mortgage", "Monthly NOI", "Annual NOI", "Cap Rate", "Net Cash Flow", "Annual Cash Flow", "Cash on Cash", "Favorite"]
display_df = df[display_cols].copy()

# Add other marketplace links
display_df['Zillow'] = display_df['Address'].apply(lambda a: zillow_resolve(a))
display_df['Redfin'] = display_df['Address'].apply(lambda a: redfin_link(a))
display_df['Realtor'] = display_df['Address'].apply(lambda a: realtor_link(a))

# Keep a numeric copy for comparisons
compare_df = display_df.copy()
# Convert display numeric strings to floats for compare_df where needed
for c in ["Price", "Rent", "Est. Mortgage", "Monthly NOI", "Annual NOI", "Net Cash Flow", "Annual Cash Flow", "Cash on Cash"]:
    if c in compare_df.columns:
        compare_df[c] = compare_df[c].astype(float)

# Format numeric columns for display
for c in ["Price", "Rent", "Est. Mortgage", "Monthly NOI", "Annual NOI", "Net Cash Flow", "Annual Cash Flow"]:
    if c in display_df.columns:
        display_df[c] = display_df[c].apply(lambda x: fmt_currency(x) if pd.notna(x) else "-")

# Format Cap Rate and Cash on Cash
if 'Cap Rate' in display_df.columns:
    display_df['Cap Rate'] = display_df['Cap Rate'].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "-")
if 'Cash on Cash' in display_df.columns:
    display_df['Cash on Cash'] = display_df['Cash on Cash'].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "-")

# Favorite column as star
display_df['Favorite'] = display_df['Favorite'].apply(lambda v: '⭐' if v else '')

# Show the numeric table
st.dataframe(display_df, use_container_width=True)

# Quick links area (icons table)
st.markdown("---")
st.subheader("🔗 Quick Property Links")
if not display_df.empty:
    # Build a small HTML table with icons to allow clickable links inside the app
    rows = []
    for idx, row in display_df.iterrows():
        addr = row['Address']
        z = row['Zillow']
        r = row['Redfin']
        re_l = row['Realtor']
        z_icon = f"<a href=\"{z}\" target=\"_blank\">🏠 Zillow</a>"
        r_icon = f"<a href=\"{r}\" target=\"_blank\">🔎 Redfin</a>"
        re_icon = f"<a href=\"{re_l}\" target=\"_blank\">📋 Realtor</a>"
        rows.append(f"<tr><td><b>{addr}</b></td><td>{z_icon}</td><td>{r_icon}</td><td>{re_icon}</td></tr>")
    table_html = "<table>" + "".join(rows) + "</table>"
    st.markdown(table_html, unsafe_allow_html=True)

    # Quick copy utility: select an address and copy into a text box for easy manual clipboard copy
    st.markdown("**Quick Copy Address**")
    copy_choice = st.selectbox("Choose address to copy", display_df['Address'].tolist())
    if st.button("Copy address to field"):
        st.session_state['copied_address'] = copy_choice
    copied = st.session_state.get('copied_address', '')
    st.text_input("Address (copy from here)", value=copied, key="copy_field")

# 4b. Compare listings
st.markdown("---")
st.subheader("⚖️ Compare Listings")
addresses = df['Address'].tolist() if not df.empty else []
selected_for_compare = st.multiselect("Select listings to compare (max 4)", addresses, max_selections=4)
if selected_for_compare:
    to_compare = compare_df[compare_df['Address'].isin(selected_for_compare)].set_index('Address')
    # Show side-by-side numeric comparison
    st.write(to_compare[['Units','Price','Rent','Est. Mortgage','Monthly NOI','Annual NOI','Cap Rate','Net Cash Flow','Annual Cash Flow','Cash on Cash']].transpose())

# 4c. Delete / manage listings
st.markdown("---")
st.subheader("🗑️ Manage & Delete Listings")
selected_for_delete = st.multiselect("Select listings to delete", addresses)
if st.button("Delete selected listings", key="delete_selected"):
    if selected_for_delete:
        st.session_state.properties = [p for p in st.session_state.properties if p['Address'] not in selected_for_delete]
        save_persisted_properties(st.session_state.properties, auto_commit=auto_commit, gh_owner=gh_owner, gh_repo=gh_repo)
        st.success(f"Deleted {len(selected_for_delete)} listings")
    else:
        st.info("No listings selected to delete")

if st.button("Clear all listings", key="clear_all_confirm"):
    st.session_state.properties = []
    save_persisted_properties(st.session_state.properties, auto_commit=auto_commit, gh_owner=gh_owner, gh_repo=gh_repo)
    st.success("Cleared all listings")

st.markdown("---")

# 5. DYNAMIC PROPERTY CARD DEEP-DIVES + per-item delete
st.subheader("🔎 Deep-Dive Property Vetting")
selected_address = st.selectbox("Select a property to view detailed pros/cons:", addresses)

if selected_address:
    deal = df[df['Address'] == selected_address].iloc[0]

    # Show hero banner depending on favorite
    if deal.get('Favorite'):
        st.markdown(f"### {deal['Address']} ⭐ — Favorite Listing")
    else:
        st.markdown(f"### {deal['Address']}")

    # Metrics
    metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
    metrics_col1.metric("Price", fmt_currency(deal['Price']))
    metrics_col1.metric("Units", int(deal['Units']))
    metrics_col2.metric("Monthly NOI", fmt_currency(deal['Monthly NOI']))
    metrics_col2.metric("Annual NOI", fmt_currency(deal['Annual NOI']))
    metrics_col3.metric("Cap Rate", f"{deal['Cap Rate']*100:.2f}%" if pd.notna(deal['Cap Rate']) else "-")
    metrics_col3.metric("Annual Cash Flow", fmt_currency(deal['Annual Cash Flow']))

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

    # Links (Zillow preferred permalink + Redfin/Realtor search)
    zillow_url = zillow_resolve(selected_address)
    redfin_url = redfin_link(selected_address)
    realtor_url = realtor_link(selected_address)
    st.markdown(f"[Open on Zillow]({zillow_url})")
    st.markdown(f"[Open on Redfin]({redfin_url})")
    st.markdown(f"[Open on Realtor.com]({realtor_url})")

    # quick actions for this deal
    action_col1, action_col2, action_col3 = st.columns(3)
    with action_col1:
        if st.button("🗑️ Delete this listing"):
            st.session_state.properties = [p for p in st.session_state.properties if p['Address'] != selected_address]
            save_persisted_properties(st.session_state.properties, auto_commit=auto_commit, gh_owner=gh_owner, gh_repo=gh_repo)
            st.experimental_rerun()
    with action_col2:
        # Toggle favorite state
        cur_fav = bool(deal.get('Favorite'))
        if st.button("⭐ Toggle Favorite"):
            # update underlying session state
            for p in st.session_state.properties:
                if p['Address'] == selected_address:
                    p['Favorite'] = not p.get('Favorite', False)
            save_persisted_properties(st.session_state.properties, auto_commit=auto_commit, gh_owner=gh_owner, gh_repo=gh_repo)
            st.experimental_rerun()
    with action_col3:
        if st.button("🔁 Refresh Metrics"):
            st.experimental_rerun()

st.markdown("---")

# Footer: fun tips
st.markdown("Need more power? I can also add extra analytics, filters, or automatic ranking by Cap Rate or Cash-on-Cash.")
