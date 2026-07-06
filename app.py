import json
import re

# =========================
# 🚀 RENT COMP ESTIMATOR (CT MARKET MODEL)
# =========================
def estimate_market_rent(city: str, units: int = 1, beds: int = 2) -> float:
    city = (city or "").lower()

    # Matrix lookup is cleaner and easier to scale than nested if/elifs
    market_matrix = {
        "hartford": {"base_2br": 1450, "base_3br": 1750},
        "new britain": {"base_2br": 1400, "base_3br": 1700},
        "waterbury": {"base_2br": 1350, "base_3br": 1650},
        "default": {"base_2br": 1400, "base_3br": 1700}
    }
    
    # Find matching city or default
    tier = next((v for k, v in market_matrix.items() if k in city), market_matrix["default"])

    if beds <= 1:
        base = tier["base_2br"] - 250
    elif beds == 2:
        base = tier["base_2br"]
    else:
        base = tier["base_3br"]

    # NOTE: This assumes all units have the same bedroom count. 
    # For true accuracy, calculate rent per unit dynamically.
    return round(base * units * 0.98, 0)


# =========================
# 🧠 GEMINI PARSER (ROBUST + PHONE-SAFE)
# =========================
def parse_gemini_text(text: str) -> dict:
    out = {
        "Address": "", "City": "", "State": "", "Units": 1, "Beds": 2,
        "Baths": 1, "Price": 0.0, "Rent": 0.0, "Status": "Monitoring",
        "Positives": [], "Negatives": [], "Favorite": False
    }
    
    if not text:
        return out

    # -------- JSON MODE --------
    try:
        data = json.loads(text)
        out["Address"] = data.get("address") or ""
        out["City"] = data.get("city") or ""
        out["State"] = data.get("state") or ""
        out["Status"] = data.get("status") or "Monitoring"
        
        fin = data.get("financials") or {}
        # Safer conversion using a helper or try/except block
        try:
            out["Price"] = float(fin.get("listPrice") or 0)
        except (ValueError, TypeError):
            out["Price"] = 0.0

        units = data.get("units")
        if isinstance(units, list) and units:
            out["Units"] = len(units)
            
            # Sum up rents safely
            total_rent = 0.0
            for u in units:
                try:
                    total_rent += float(u.get("estRent") or 0)
                except (ValueError, TypeError):
                    pass
            out["Rent"] = total_rent

            # Average or use first unit's specs
            out["Beds"] = int(units[0].get("beds") or 2)
            out["Baths"] = int(units[0].get("baths") or 1)

        analysis = data.get("analysis") or {}
        out["Positives"] = analysis.get("positives") or []
        out["Negatives"] = analysis.get("negatives") or []
        return out

    except Exception:
        pass # Fallback to text parsing

    # -------- TEXT MODE FALLBACK --------
    for line in text.split("\n"):
        if ":" not in line:
            continue
            
        key, val = [part.strip() for part in line.split(":", 1)]
        k_low = key.lower()

        if "address" in k_low:
            out["Address"] = val
        elif "city" in k_low:
            out["City"] = val
        elif "units" in k_low:
            # Matches the first integer found
            match = re.search(r'\d+', val)
            out["Units"] = int(match.group()) if match else out["Units"]
        elif "beds" in k_low:
            match = re.search(r'\d+', val)
            out["Beds"] = int(match.group()) if match else out["Beds"]
        elif "price" in k_low:
            # Matches first float/integer pattern, ignoring commas or dollar signs
            match = re.search(r'\d[\d,]*\.?\d*', val)
            if match:
                out["Price"] = float(match.group().replace(",", ""))
        elif "rent" in k_low:
            match = re.search(r'\d[\d,]*\.?\d*', val)
            if match:
                out["Rent"] = float(match.group().replace(",", ""))
        elif "positives" in k_low:
            out["Positives"].append(val)
        elif "negatives" in k_low:
            out["Negatives"].append(val)

    return out


# =========================
# 🧼 PIPELINE NORMALIZER
# =========================
def normalize_for_pipeline(p: dict) -> dict:
    # Keeps your clean casting dictionary, guarantees no None types slip through
    return {
        "Address": str(p.get("Address") or ""),
        "City": str(p.get("City") or ""),
        "Units": int(p.get("Units") or 1),
        "Beds": int(p.get("Beds") or 2),
        "Baths": int(p.get("Baths") or 1),
        "Price": float(p.get("Price") or 0.0),
        "Rent": float(p.get("Rent") or 0.0),
        "Status": str(p.get("Status") or "Monitoring"),
        "Positives": list(p.get("Positives") or []),
        "Negatives": list(p.get("Negatives") or []),
        "Favorite": bool(p.get("Favorite") or False)
    }
