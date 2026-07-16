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

st.set_page_config(page_title="Hartford House-Hacking Command Center", layout="wide", initial_sidebar_state="expanded")

st.title("🚀 Hartford House-Hacking Command Center")
st.markdown("---")

# ---------- FIXED PARSER ----------
def parse_gemini_text(text: str) -> dict:
    """Tries JSON first, then falls back to aggressive Regex parsing."""
    out = {"Address": "Unknown Address", "Units": 1, "Price": 0.0, "Rent": 0.0, "Status": "Monitoring", "Positives": "", "Negatives": ""}
    
    cleaned_text = text.strip()
    # Remove markdown code blocks if present
    cleaned_text = re.sub(r'```json|```', '', cleaned_text).strip()

    # Strategy 1: JSON Parsing
    try:
        data = json.loads(cleaned_text)
        # Handle nested schema
        ident = data.get("property_identifiers", {})
        addr = ident.get("address", data.get("address", ""))
        city = ident.get("city", data.get("city", "Hartford"))
        if addr:
            out["Address"] = f"{addr.title()}, {city.title()}"
        
        tech = data.get("technical_specifications", {})
        out["Units"] = int(tech.get("total_units", data.get("units", 1)))
        
        fin = data.get("financial_metrics", data.get("financials", {}))
        out["Price"] = float(fin.get("listing_price", data.get("price", 0)))
        out["Rent"] = float(fin.get("gross_potential_monthly_income", data.get("rent", 0)))
        
        risk = data.get("risk_assessment", data.get("analysis", {}))
        pos = risk.get("positives", data.get("positives", []))
        neg = risk.get("negatives", data.get("negatives", []))
        
        out["Positives"] = ", ".join(pos) if isinstance(pos, list) else str(pos)
        out["Negatives"] = ", ".join(neg) if isinstance(neg, list) else str(neg)
        
        if out["Address"] != "Unknown Address":
            return out
    except:
        pass # Fall through to regex if JSON fails

    # Strategy 2: Regex Fallback (The logic you wrote, now reachable)
    text_lower = text.lower()
    price_match = re.search(r'(?:price|asking|list|\$)\s*(?::|is)?\s*\$?\s*([0-9,]{4,})', text_lower)
    if price_match:
        out["Price"] = float(price_match.group(1).replace(',', ''))

    rent_match = re.search(r'(?:rent|gross|monthly|\$)\s*(?::|is)?\s*\$?\s*([0-9,]{3,4})\b', text_lower)
    if rent_match:
        out["Rent"] = float(rent_match.group(1).replace(',', ''))

    units_match = re.search(r'([1-9]|10)\s*(?:unit|family|plex|door)', text_lower)
    if units_match:
        out["Units"] = int(units_match.group(1))

    # Address line detection
    for line in text.split('\n'):
        if re.search(r'^\d+\s+[A-Za-z0-9\s.,]+(?:st|ave|pl|rd|ln|dr|ct|hartford)', line.lower()):
            out["Address"] = line.strip("-*• ").strip()
            break

    return out

# ---------- IMPROVED LINK GENERATION ----------
def get_zillow_url(address: str) -> str:
    """Standardized search URL to avoid bot-blocking on direct detail pages."""
    return f"https://www.zillow.com/homes/{urllib.parse.quote_plus(address)}_rb/"

def redfin_link(address: str) -> str:
    return f"https://www.redfin.com/search?q={urllib.parse.quote_plus(address)}"

# ---------- DATA PERSISTENCE ----------
def load_data():
    if DATA_FILE.exists():
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return [] # Return empty if no file exists

def save_data(props):
    with open(DATA_FILE, "w") as f:
        json.dump(props, f, indent=2)

# ---------- SESSION STATE ----------
if 'properties' not in st.session_state:
    persisted = load_data()
    if not persisted:
        # ONLY load defaults if file is empty/missing
        st.session_state.properties = [
            {"Address": "40 Allen Place, Hartford", "Units": 3, "Price": 420000, "Rent": 4500, "Status": "Underwriting", "Positives": "Turnkey", "Negatives": "Market softening", "Favorite": False}
        ]
    else:
        st.session_state.properties = persisted

# [Rest of your UI/Sidebar logic goes here...]
# Ensure you call save_data(st.session_state.properties) after any add/delete/favorite action.
