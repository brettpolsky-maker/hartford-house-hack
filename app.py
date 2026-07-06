# =========================
# 🚀 RENT COMP ESTIMATOR (CT MARKET MODEL)
# =========================
def estimate_market_rent(city: str, units: int = 1, beds: int = 2):
    city = (city or "").lower()

    if "hartford" in city:
        base_2br = 1450
        base_3br = 1750
    elif "new britain" in city:
        base_2br = 1400
        base_3br = 1700
    elif "waterbury" in city:
        base_2br = 1350
        base_3br = 1650
    else:
        base_2br = 1400
        base_3br = 1700

    if beds <= 1:
        base = base_2br - 250
    elif beds == 2:
        base = base_2br
    else:
        base = base_3br

    return round(base * units * 0.98, 0)


# =========================
# 🧠 GEMINI PARSER (ROBUST + PHONE-SAFE)
# =========================
def parse_gemini_text(text: str) -> dict:
    if not text:
        return {}

    out = {
        "Address": "",
        "City": "",
        "State": "",
        "Units": 1,
        "Beds": 2,
        "Baths": 1,
        "Price": 0.0,
        "Rent": 0.0,
        "Status": "Monitoring",
        "Positives": [],
        "Negatives": [],
        "Favorite": False
    }

    # -------- JSON MODE --------
    try:
        data = json.loads(text)

        out["Address"] = data.get("address", "") or ""
        out["City"] = data.get("city", "") or ""
        out["State"] = data.get("state", "") or ""
        out["Status"] = data.get("status", "Monitoring")

        fin = data.get("financials", {})
        out["Price"] = float(fin.get("listPrice", 0) or 0)

        units = data.get("units", [])
        if isinstance(units, list) and len(units) > 0:
            out["Units"] = len(units)

            total_rent = 0
            for u in units:
                total_rent += float(u.get("estRent", 0) or 0)

            out["Rent"] = total_rent

            out["Beds"] = units[0].get("beds", 2)
            out["Baths"] = units[0].get("baths", 1)

        analysis = data.get("analysis", {})
        out["Positives"] = analysis.get("positives", [])
        out["Negatives"] = analysis.get("negatives", [])

        return out

    except Exception:
        pass

    # -------- TEXT MODE FALLBACK --------
    for line in text.split("\n"):
        l = line.lower()

        if "address" in l and ":" in line:
            out["Address"] = line.split(":", 1)[1].strip()

        elif "city" in l and ":" in line:
            out["City"] = line.split(":", 1)[1].strip()

        elif "units" in l and ":" in line:
            try:
                out["Units"] = int("".join(filter(str.isdigit, line)))
            except:
                pass

        elif "beds" in l and ":" in line:
            try:
                out["Beds"] = int("".join(filter(str.isdigit, line)))
            except:
                pass

        elif "price" in l and ":" in line:
            try:
                out["Price"] = float("".join(c for c in line if c.isdigit() or c == "."))
            except:
                pass

        elif "rent" in l and ":" in line:
            try:
                out["Rent"] = float("".join(c for c in line if c.isdigit() or c == "."))
            except:
                pass

        elif "positives" in l and ":" in line:
            out["Positives"].append(line.split(":", 1)[1].strip())

        elif "negatives" in l and ":" in line:
            out["Negatives"].append(line.split(":", 1)[1].strip())

    return out


# =========================
# 🧼 PIPELINE NORMALIZER (CLEAN EXPORT FORMAT)
# =========================
def normalize_for_pipeline(p):
    return {
        "Address": p.get("Address", ""),
        "City": p.get("City", ""),
        "Units": int(p.get("Units", 1) or 1),
        "Beds": int(p.get("Beds", 2) or 2),
        "Baths": int(p.get("Baths", 1) or 1),
        "Price": float(p.get("Price", 0) or 0),
        "Rent": float(p.get("Rent", 0) or 0),
        "Status": p.get("Status", "Monitoring"),
        "Positives": p.get("Positives", []),
        "Negatives": p.get("Negatives", []),
        "Favorite": bool(p.get("Favorite", False))
    }
