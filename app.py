import streamlit as st
import pandas as pd
import json
import re
from pathlib import Path

# Path for optional local persistence
DATA_FILE = Path(__file__).parent / "pipeline.json"

# Set up page config for a premium, wide-screen dashboard look
st.set_page_config(page_title="Hartford House-Hacking Command Center", layout="wide", initial_sidebar_state="expanded")

st.title("🚀 Hartford House-Hacking Command Center")
st.markdown("---")

# ---------- Helper: Gemini text parser ----------
def parse_gemini_text(text: str) -> dict:
    """Best-effort parsing for pasted Gemini content.
    Looks for lines like `Address: ...`, `Units: 3`, `Price: $400,000`, `Rent: $4,500`,
    `Status: Underwriting`, `Positives: ...`, `Negatives: ...`.
    Falls back to heuristics when explicit labels aren't present.
    """
    out = {"Address": "", "Units": 1, "Price": 0.0, "Rent": 0.0, "Status": "Monitoring", "Positives": "", "Negatives": ""}
    if not text:
        return out

    # Normalize newlines and trim
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    joined = "\n".join(lines)

    # Label-based extraction
    def find_label(label):
        m = re.search(rf"{label}\s*[:\-]\s*(.+?)(?:\n|$)", joined, re.IGNORECASE)
        return m.group(1).strip() if m else None

    address = find_label("Address") or find_label("Property")
    units = find_label("Units")
    price = find_label("Price")
    rent = find_label("Rent") or find_label("Est\. Gross Monthly Rent")
    status = find_label("Status")
    positives = find_label("Positives")
    negatives = find_label("Negatives")

    # Try dollar-based finds if labeled values not found
    if not price:
        m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", joined)
        if m:
            price = m.group(1)
    if not rent:
        # look for a second dollar amount or patterns like 'monthly rent' nearby
        dollars = re.findall(r"\$\s*([\d,]+(?:\.\d+)?)", joined)
        if len(dollars) >= 2:
            rent = dollars[1]
        elif dollars:
            # single dollar found: decide if it's rent or price based on context
            context_idx = joined.lower().find(dollars[0])
            prev = joined[max(0, context_idx-50):context_idx].lower()
            if "rent" in prev or "monthly" in prev:
                rent = dollars[0]
            else:
                price = dollars[0]

    # Numeric cleanup helpers
    def to_float(s):
        if s is None:
            return 0.0
        s = str(s).replace('$','').replace(',','').strip()
        try:
            return float(s)
        except Exception:
            return 0.0

    # Assign parsed values
    if address:
        out["Address"] = address
    if units:
        try:
            out["Units"] = int(re.search(r"(\d+)", units).group(1))
        except Exception:
            out["Units"] = 1
    if price:
        out["Price"] = to_float(price)
    if rent:
        out["Rent"] = to_float(rent)
    if status:
        out["Status"] = status
    if positives:
        out["Positives"] = positives
    if negatives:
        out["Negatives"] = negatives

    # Heuristic: if a line looks like an address (contains numbers and a street name), pick the first such line
    if not out["Address"]:
        for l in lines:
            if re.search(r"\d+\s+\w+", l):
                out["Address"] = l
                break

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


def save_persisted_properties(props):
    try:
        with DATA_FILE.open("w", encoding="utf-8") as f:
            json.dump(props, f, indent=2)
        return True
    except Exception:
        return False


# 1. SIDEBAR: Global Financial Variables & Deal Input
st.sidebar.header("⚙️ Global Deal Mechanics")
interest_rate = st.sidebar.slider("Interest Rate (%)", 5.0, 8.5, 6.5, 0.1) / 100
down_payment_pct = st.sidebar.slider("Down Payment (%)", 3.5, 20.0, 5.0, 0.5) / 100
op_expense_pct = st.sidebar.slider("Operating Expenses (% of Rent)", 35, 55, 45, 5) / 100

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

# Initialize Session State Data if it doesn't exist
if 'properties' not in st.session_state:
    # Start from the built-in defaults, then merge persisted ones
    st.session_state.properties = [
        {"Address": "6-Family Hartford", "Units": 6, "Price": 830000, "Rent": 7200, "Status": "Underwriting", "Positives": "Max scale with 5 income streams, Commercial financing eligibility, High cash flow cushion", "Negatives": "Exceeds $725k pre-approval, High management intensity, Maintenance volatility"},
        {"Address": "40 Allen Place", "Units": 3, "Price": 420000, "Rent": 4500, "Status": "Underwriting", "Positives": "Turnkey condition requires low cap-ex, Leaves budget breathing room, Better lifestyle balance/privacy", "Negatives": "Lower absolute cash-flow ceiling, 33% vacancy risk, Highly competitive market"},
        {"Address": "19-21 Mill St", "Units": 2, "Price": 340000, "Rent": 3100, "Status": "Screened", "Positives": "Separate utilities/mechanicals, Lowest purchase price and risk, Light management load", "Negatives": "Only subsidies mortgage, Zero immediate scale, 50% vacancy risk exposure"},
        {"Address": "285 Zion St", "Units": 4, "Price": 490000, "Rent": 5200, "Status": "Monitoring", "Positives": "Good unit mix, Emerging location", "Negatives": "Awaiting rent roll verification"},
        {"Address": "98-100 Capen St", "Units": 3, "Price": 380000, "Rent": 3900, "Status": "Monitoring", "Positives": "Low entry price, Strong initial cap rate", "Negatives": "Drive by required to assess block"}
    ]
    # Merge persisted properties (avoid duplicates by Address)
    persisted = load_persisted_properties()
    if persisted:
        existing_addresses = {p['Address'] for p in st.session_state.properties}
        for pp in persisted:
            if pp.get('Address') and pp['Address'] not in existing_addresses:
                st.session_state.properties.append(pp)

# Append new property entry if form submitted
if submit and address:
    new_prop = {
        "Address": address, "Units": units, "Price": price, "Rent": rent, "Status": status,
        "Positives": positives, "Negatives": negatives
    }
    # Overwrite if address matches, else append
    st.session_state.properties = [p for p in st.session_state.properties if p["Address"] != address]
    st.session_state.properties.append(new_prop)
    # Persist to local file
    save_persisted_properties(st.session_state.properties)

# --- FIXED: Gemini import flow using session_state so form survives reruns ---
# When Parse is clicked, store parsed payload in session_state
if import_clicked and gemini_text and gemini_text.strip():
    st.session_state['gemini_parsed'] = parse_gemini_text(gemini_text)

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
            "Positives": positives2, "Negatives": negatives2
        }
        # Overwrite if address matches, else append
        st.session_state.properties = [p for p in st.session_state.properties if p["Address"] != addr2]
        st.session_state.properties.append(new_prop)
        saved = save_persisted_properties(st.session_state.properties)
        if saved:
            st.sidebar.success("Imported and saved to pipeline.json")
        else:
            st.sidebar.warning("Imported to session, but failed to save pipeline.json")
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

    processed_deals.append({
        **p,
        "Est. Mortgage": round(mortgage, 2),
        "Monthly NOI": round(monthly_noi, 2),
        "Net Cash Flow": round(house_hack_cash_flow, 2)
    })


# Build dataframe
df = pd.DataFrame(processed_deals)

# 3. EXECUTIVE METRICS BAR
col1, col2, col3, col4 = st.columns(4)
col1.metric("Pre-Approval Cap", "$725,000", "Expires Sept 2026")
col2.metric("Total Deals Tracked", len(df))
under_review = len(df[df['Status'] == 'Underwriting']) if not df.empty else 0
col3.metric("Deals in Underwriting", under_review)

# Safely determine best deal
best_deal = "None"
if not df.empty and "Net Cash Flow" in df.columns:
    if df["Net Cash Flow"].notna().any():
        best_idx = df["Net Cash Flow"].idxmax()
        if pd.notna(best_idx):
            best_deal = df.loc[best_idx, "Address"]
col4.metric("Top Cash-Flowing Option", best_deal)

st.markdown("---")

# 4. MASTER DEAL PIPELINE TABLE
st.subheader("📊 Master Pipeline Overview")
display_df = df[["Address", "Units", "Price", "Rent", "Status", "Est. Mortgage", "Monthly NOI", "Net Cash Flow"]].copy()

# Format numeric columns for display
currency_cols = ["Price", "Rent", "Est. Mortgage", "Monthly NOI", "Net Cash Flow"]
for c in currency_cols:
    if c in display_df.columns:
        display_df[c] = display_df[c].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "-")

st.dataframe(display_df, use_container_width=True)

st.markdown("---")

# 5. DYNAMIC PROPERTY CARD DEEP-DIVES
st.subheader("🔎 Deep-Dive Property Vetting")
addresses = df["Address"].unique().tolist() if not df.empty else []
selected_address = st.selectbox("Select a property to view detailed pros/cons:", addresses)

if selected_address:
    deal = df[df["Address"] == selected_address].iloc[0]

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
