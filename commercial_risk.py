"""Commercial clients: the application questions, what each business needs attached, and the email facts.

Built from WellCare's Commercial Application / Commercial Property Quote Application / Commercial Auto Quote Form,
the CSIO Commercial Vehicle Supplement, the Fleet supplement and the restaurant questionnaire (note 40 in the
Underwriting Knowledge folder). Same shape as property_risk, so the Property details page draws it too.

The answers live in tracking.json under "commercial_intake". No carrier rules here (those stay in the notes folder).
"""
import records

KEY = "commercial_intake"
YN = ["Yes", "No"]

BUSINESS = ["Office / professional services", "Retail shop", "Restaurant / food service", "Contractor / trades",
            "Building owner (realty)", "Warehouse / wholesale", "Manufacturer", "Health / wellness / beauty",
            "Auto-related (garage, dealer, car wash)", "Trucking / delivery", "Other"]
ENTITY = ["Corporation", "Sole proprietor", "Partnership"]
OWN_OR_RENT = ["Owns the building", "Rents the premises"]
STOREYS = ["1", "2", "3", "4 or more"]
WALLS = ["Frame", "Frame with brick veneer", "Solid brick / masonry", "Concrete block", "Poured concrete",
         "Steel / metal clad", "Other"]
ELECTRICAL = ["Breakers", "Fuses", "Breakers and fuses"]
PLUMBING = ["Copper", "Plastic (PVC / CPVC)", "Galvanized", "Lead", "Steel", "Other"]
HEATING = ["Furnace (central)", "Boiler", "Electric", "Radiant", "Roof-mounted unit", "Suspended heaters",
           "Wood / solid fuel", "None"]
HYDRANT = ["Within 150 m", "Within 300 m", "Over 300 m", "Unprotected (none)"]
FIRE_HALL = ["Within 5 km", "Within 8 km", "Within 13 km", "Over 13 km"]
ALARM = ["Central station (full service)", "Monitored (shared service)", "Local alarm only", "None"]
CLEANING = ["Monthly", "Quarterly", "Semi-annual", "Annual", "Not cleaned"]
CGL = ["$1,000,000", "$2,000,000", "$5,000,000"]
RADIUS = ["Within 40 km", "41-80 km", "81-160 km", "161-400 km", "Over 400 km"]

# (key, label, kind, options, uses, hint)   kind: text num year yn choice date money long   (uses: unused here)
SECTIONS = [
    ("about", "The business", [
        ("dwelling", "Type of business", "choice", BUSINESS, "", ""),
        ("legal_name", "Registered / legal name", "text", None, "",
         "Must match the PowerBroker customer name and the policyholder"),
        ("trade_name", "Trade / operating name", "text", None, "", ""),
        ("entity", "Sole proprietor or corporation", "choice", ENTITY, "", "Corporation: articles of incorporation"),
        ("description", "What the business does (be descriptive)", "long", None, "",
         "If you own the building: who the tenants are and what they do"),
        ("years_business", "Years in business", "num", None, "", ""),
        ("years_experience", "Owner's related experience (years)", "num", None, "", "Contractors / trades: 3 years minimum for most markets"),
        ("years_location", "Years at this location", "num", None, "", ""),
        ("known_since", "Broker has known the client since", "text", None, "", "Month and year"),
        ("effective_date", "Coverage wanted from", "date", None, "", "Binding can never be back-dated"),
        ("pb_code", "PowerBroker customer code", "text", None, "", "Built from the business operating name"),
        ("pb_binder", "PowerBroker binder number", "text", None, "", "Goes in the submission subject line"),
        ("branch", "Branch number", "text", None, "", "For example B01"),
    ]),
    ("operations", "Operations and revenue", [
        ("receipts", "Annual gross receipts ($)", "money", None, "", ""),
        ("payroll", "Annual payroll ($)", "money", None, "", ""),
        ("employees_ft", "Employees (full time)", "num", None, "", ""),
        ("employees_pt", "Employees (part time)", "num", None, "", ""),
        ("wcb", "Covered by WCB", "yn", None, "", ""),
        ("pct_canada", "Sales in Canada (%)", "num", None, "", "Canada + US + foreign = 100"),
        ("pct_us", "Sales in the US (%)", "num", None, "", "US sales can limit the markets"),
        ("pct_foreign", "Sales elsewhere (%)", "num", None, "", ""),
        ("pct_internet", "Internet sales (%)", "num", None, "", ""),
        ("work_away", "Work done away from the premises", "yn", None, "", ""),
        ("snow_removal", "Snow removal for others", "yn", None, "", ""),
        ("subcontractors", "Uses subcontractors", "yn", None, "", "Proof of their insurance is needed"),
        ("pct_subtrades", "Subtrades (% of work)", "num", None, "", ""),
    ]),
    ("liquor", "Food, liquor and cooking", [
        ("liquor", "Liquor sold or served", "yn", None, "", ""),
        ("liquor_plan", "Plans to get a liquor licence", "yn", None, "", ""),
        ("receipts_liquor", "Receipts from liquor ($)", "money", None, "", "Over 60 % of revenue is declined by some markets"),
        ("receipts_food", "Receipts from food ($)", "money", None, "", ""),
        ("deep_fryers", "Deep fryers or other cooking with grease", "yn", None, "",
         "Wet-chemical suppression system needed; dry chemical is declined by Echelon"),
        ("suppression", "Approved wet-chemical suppression system and hood", "yn", None, "", "UL300 / ULC 1254.6 and NFPA 96"),
        ("duct_cleaning", "Hood / duct cleaning", "choice", CLEANING, "", "Report must be attached"),
        ("live_entertainment", "Dancing, DJ or live entertainment", "yn", None, "", "Nightclubs are declined by most markets"),
        ("hookah", "Hookah / shisha", "yn", None, "", "Declined by most markets"),
        ("delivery", "Food delivery", "yn", None, "", ""),
    ]),
    ("building", "The location", [
        ("address", "Risk address", "text", None, "", ""),
        ("postal", "Postal code", "text", None, "", ""),
        ("own_or_rent", "Owns or rents the premises", "choice", OWN_OR_RENT, "", ""),
        ("year_built", "Year built", "year", None, "", ""),
        ("sq_ft", "Total area (sq ft)", "num", None, "", ""),
        ("storeys", "Storeys", "choice", STOREYS, "", ""),
        ("basement", "Basement", "yn", None, "", ""),
        ("walls", "Walls", "choice", WALLS, "", "Frame / unprotected risks are hard to place"),
        ("electrical", "Electrical", "choice", ELECTRICAL, "", ""),
        ("plumbing", "Plumbing", "choice", PLUMBING, "", ""),
        ("heating", "Heating", "choice", HEATING, "", ""),
        ("heating_year", "Heating updated (year)", "year", None, "", "Old buildings: all four updates are asked"),
        ("wiring_year", "Wiring updated (year)", "year", None, "", ""),
        ("plumbing_year", "Plumbing updated (year)", "year", None, "", ""),
        ("roof_year", "Roof updated (year)", "year", None, "", ""),
        ("mortgagee", "Mortgagee / loss payee", "text", None, "", "Name and address; Intact Edge takes at most two"),
    ]),
    ("protection", "Fire and theft protection", [
        ("hydrant", "Distance to hydrant", "choice", HYDRANT, "", ""),
        ("fire_hall", "Distance to fire hall", "choice", FIRE_HALL, "", ""),
        ("sprinklers", "Sprinklers", "yn", None, "", ""),
        ("fire_alarm", "Fire alarm", "choice", ALARM, "", ""),
        ("burglar_alarm", "Burglar alarm", "choice", ALARM, "", ""),
        ("ulc_cert", "ULC alarm certificate available", "yn", None, "", "Credit is only given once it is in"),
        ("cameras", "Surveillance cameras", "yn", None, "", ""),
        ("safe", "Safe on the premises", "yn", None, "", ""),
        ("cash", "Cash kept on the premises", "yn", None, "", ""),
        ("exposure_notes", "Neighbouring businesses (left / right / behind / front)", "long", None, "",
         "Restaurants, bars, clubs and manufacturing next door matter"),
    ]),
    ("vehicles", "Vehicles", [
        ("has_vehicles", "The business has vehicles to insure", "yn", None, "", "Needs the Commercial Vehicle Supplement"),
        ("vehicle_count", "Number of vehicles", "num", None, "", "5 or more: fleet supplement"),
        ("vehicle_use", "Main business use of the vehicles", "text", None, "", "For example: plumber visits job sites"),
        ("commodities", "What is carried (tools, goods, passengers)", "text", None, "", "List tools and equipment"),
        ("radius", "Usual operating distance", "choice", RADIUS, "", "Over 80 km: refer to the underwriter"),
        ("usa_exposure", "Drives into the USA", "yn", None, "", "Most markets decline US exposure"),
        ("hauls_others", "Carries goods for others", "yn", None, "", "Not written by IRCA (Echelon)"),
        ("heavy", "Vehicles over 4,500 kg (heavy)", "yn", None, "", "CVOR certificate and a $2,500 minimum deductible"),
        ("cvor", "CVOR number", "text", None, "", "Trucking and heavy vehicles"),
        ("dangerous", "Dangerous goods, fuel, cement, scrap or alcohol / cannabis", "yn", None, "", "Mostly not written"),
        ("young_driver", "Any driver under 25 or licensed under 3 years", "yn", None, "", "Referred by most markets"),
    ]),
    ("history", "Insurance history and claims", [
        ("prior_insurer", "Current / previous insurer", "text", None, "", ""),
        ("prior_policy", "Previous policy number", "text", None, "", ""),
        ("prior_expiry", "Previous policy expiry", "date", None, "", ""),
        ("cancelled", "Declined, cancelled or non-renewed", "yn", None, "", "Explain in the claim details"),
        ("claims_5y", "Claims in the last 5 years (how many)", "num", None, "", "Loss runs help"),
        ("claims_notes", "Claim details (date, what, paid, open)", "long", None, "", ""),
    ]),
    ("coverage", "Coverage wanted", [
        ("cov_building", "Building ($)", "money", None, "", ""),
        ("cov_equipment", "Equipment / contents ($)", "money", None, "", ""),
        ("cov_stock", "Stock ($)", "money", None, "", ""),
        ("cov_improvements", "Leasehold improvements ($)", "money", None, "", ""),
        ("cov_bi", "Business interruption ($)", "money", None, "", ""),
        ("cov_cgl", "Liability (CGL) limit", "choice", CGL, "", ""),
        ("cov_crime", "Crime", "yn", None, "", ""),
        ("cov_eb", "Equipment breakdown", "yn", None, "", ""),
        ("cov_sewer", "Sewer backup", "yn", None, "", ""),
        ("cov_flood", "Flood or earthquake", "yn", None, "", ""),
        ("cov_nonowned", "Non-owned auto (SPF 6)", "yn", None, "", ""),
        ("cov_notes", "Anything else wanted", "long", None, "", ""),
    ]),
]

FIELDS = {f[0]: f for _, _, fields in SECTIONS for f in fields}
LABELS = {k: f[1] for k, f in FIELDS.items()}
DWELLING = BUSINESS                     # the page's "pick one" list (Property details page reuses this module's shape)
PICK_LABEL = "Type of business"
REQUIRED = ["dwelling", "legal_name", "description", "years_business", "effective_date", "address", "year_built",
            "sq_ft", "receipts", "prior_insurer", "claims_5y"]


def use_of(values):
    return "commercial"


def fields_for(use=None):
    return [(key, title, list(fields)) for key, title, fields in SECTIONS]


def _yes(values, key):
    return values.get(key) == "Yes"


def _num(v):
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None


def completeness(values):
    """(filled, total, [labels still missing])."""
    missing = [LABELS[k] for k in REQUIRED if values.get(k) in (None, "")]
    return len(REQUIRED) - len(missing), len(REQUIRED), missing


def kind_of_business(values):
    return values.get("dwelling", "")


def docs_needed(values):
    """{document label: why} for what this business has to hand in with the application."""
    need = {}
    business = kind_of_business(values)
    if _yes(values, "has_vehicles") or business == "Trucking / delivery":
        need["Vehicle supplement"] = "Commercial Vehicle Supplement - every field, signed (all markets ask for it)"
        count = _num(values.get("vehicle_count"))
        if count and count >= 5:
            need["Fleet supplement"] = "5 or more vehicles: fleet supplement (hiring, safety, maintenance, telematics)"
        if _yes(values, "heavy") or business == "Trucking / delivery" or values.get("cvor"):
            need["CVOR certificate"] = "heavy / trucking vehicles: a satisfactory CVOR (level II) report"
    if business == "Auto-related (garage, dealer, car wash)":
        need["Garage form"] = "Automobile Garage Form for garage, dealer and service-station risks"
    if values.get("entity") == "Corporation":
        need["Articles of incorporation"] = "business-name policies: articles of incorporation or master business licence"
    if (business == "Restaurant / food service" or _yes(values, "deep_fryers")) :
        need["Restaurant questionnaire"] = "every restaurant: fire suppression and duct cleaning reports attached"
    if business == "Health / wellness / beauty":
        need["Industry application"] = "health care, spa or cosmetology: the insurer's own application (for example Forward)"
    if values.get("burglar_alarm") in ALARM[:3] or values.get("fire_alarm") in ALARM[:3] or _yes(values, "ulc_cert"):
        need["Alarm certificate (ULC)"] = "alarm credit is only applied once the certificate is in"
    if _yes(values, "subcontractors"):
        need["Subcontractor insurance"] = "certificates of insurance for every subcontractor"
    if values.get("mortgagee"):
        need["Mortgage information"] = "mortgagee / loss payee name and address"
    if values.get("own_or_rent") or values.get("address"):
        need["Photos of the location"] = "photos of the outside and the inside of the premises"
    return need


def load(folder):
    data = records.load(folder).get(KEY)
    return dict(data) if isinstance(data, dict) else {}


def save(folder, values):
    """Save the answers (atomic, re-reads the file so other changes are kept)."""
    clean = {k: str(v).strip() for k, v in values.items() if k in FIELDS and str(v).strip()}
    data = records.load(folder)
    data[KEY] = clean
    records._write(folder, data)
    return clean


def subject_line(values, kind_text=None):
    """The submission subject the in-house commercial team wants: B01 – Code XXXXXX – Binder1234 – CGL (Bubble Tea Shop)."""
    parts = [values.get("branch", ""), f"Code {values['pb_code']}" if values.get("pb_code") else "",
             f"Binder{values['pb_binder']}" if values.get("pb_binder") else ""]
    what = kind_text or "Commercial"
    name = values.get("trade_name") or values.get("legal_name") or ""
    parts.append(f"{what} ({name})" if name else what)
    return " – ".join(p for p in parts if p)


def email_values(folder):
    """Blanks for the commercial emails: {key: value} from the saved answers."""
    v = load(folder)
    out = {}
    if v.get("branch"):
        out["branch"] = v["branch"]
    if v.get("pb_code"):
        out["pb_code"] = v["pb_code"]
    if v.get("pb_binder"):
        out["pb_binder"] = v["pb_binder"]
    if v.get("trade_name") or v.get("legal_name"):
        out["business_name"] = v.get("trade_name") or v["legal_name"]
    if v.get("effective_date"):
        day = records.parse_date(v["effective_date"])
        if day:
            out["effective_date"] = day.strftime("%B %d, %Y").replace(" 0", " ")
    return out
