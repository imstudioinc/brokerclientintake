"""Commercial clients: every question on WellCare's Commercial Insurance Application, what each business needs
attached, and the email facts.

The first sections follow the application page by page (so the Commercial details page, the filled application and
the Tracker all hold the same answers); "Other questions the markets ask" keeps what the carriers' own forms add
(vehicle supplement, restaurant questionnaire ...). See commercial_app.py for how the answers are written onto the
application PDF.

**Liability only**: the application has a "Liability Only" box; ticking it drops the location, construction,
protection and property-coverage pages and keeps only the cover page, the liability page and the liability
schedule. Sections marked `property` below are hidden / skipped / not required when `liability_only` is "Yes".

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
CLEANING = ["Monthly", "Quarterly", "Semi-annual", "Annual", "Not cleaned"]
RADIUS = ["Within 40 km", "41-80 km", "81-160 km", "161-400 km", "Over 400 km"]

# the boxes printed on the application (the wording of the form)
OCCUPANCY = ["Retail strip plaza", "Industrial plaza", "Enclosed mall"]      # "Other" is typed in (occupancy_other)
EXPOSURE_TYPES = ["Licensed restaurants / bars / clubs", "Manufacturing"]
RATING = ["Excellent", "Good", "Very good", "Average", "Fair", "Poor"]
AREA_UNIT = ["Ft²", "m²"]
WALLS = ["Poured concrete", "HCB - hollow concrete block", "Frame and all other", "Frame with brick veneer",
         "Frame metal clad", "Solid brick", "Concrete panels on steel structure", "Steel on steel",
         "Metallic panels on steel structure", "Wood", "Fire resistive", "Non-combustible with masonry walls",
         "Non-combustible with non-masonry walls", "Masonry", "Masonry veneer", "Not applicable"]
FLOORS = ["Poured concrete or fire resistive material", "Frame and all other", "Masonry",
          "Concrete panels on steel structure", "Masonry on wood structure or other combustible material",
          "Heavy beam or \"Mill\"", "Non-combustible with masonry", "Non-combustible without masonry", "Wood",
          "Steel", "Brick or stone"]
BASEMENT = ["Poured concrete", "HCB - hollow concrete block", "No basement", "Fire resistive",
            "Non-combustible with masonry", "Non-combustible without masonry", "Masonry with combustible ceiling",
            "Masonry veneer", "Frame and all other", "Not applicable", "Unfinished (crawl space)"]
ROOF = ["Frame on steel joists", "Frame on wood joists", "Heavy beam or 'mill'", "Poured concrete", "Steel beam",
        "Steel deck"]
ROOF_COVER = ["Asphalt shingles", "Steel deck", "Tar and gravel", "Concrete on steel structure", "Concrete tiles",
              "Metal"]
ELECTRICAL = ["Breakers", "Fuses", "Breakers & fuses"]
PLUMBING = ["Copper", "Lead", "Plastic (PVC or CVC)", "Galvanized", "Stainless steel", "Steel"]
HEATING = ["None", "Boiler", "Radiant", "Electric", "Wood furnace", "Geothermal", "Fireplace insert",
           "Masonry fireplace", "Furnace (central)", "Roof mounted HVAC", "Suspended heaters"]
FUEL = ["Natural gas", "Oil", "Electric", "Electric / oil", "Propane"]
EXTENT = ["Complete", "Partial"]
HYDRANT = ["Unprotected", "Within 150 m", "Within 300 m", "Over 300 m"]
FIRE_HALL = ["Within 5 km", "Within 8 km", "Within 13 km", "Over 13 km"]
EXTINGUISHING = ["Portable extinguisher(s)", "Sprinkler", "None", "Comb. portable & sprinkler", "Other"]
AGENT = ["Water", "Wet chemical", "Carbon dioxide", "Foam", "Halon", "Dry chemical"]
FIRE_ALARM = ["Central station", "Monitoring station (full service)", "Monitoring station (shared service)",
              "Local alarm"]
BURGLAR_ALARM = FIRE_ALARM + ["Visually disabling (e.g. Smokecloak)", "Unknown", "None / not applicable", "Other"]
CRIME_TYPES = ["Doors - deadbolt", "Breakage resistant glass", "Windows - barred", "Windows - wire mesh",
               "Steel bars on openings", "Surveillance cameras", "Watchmen / security guards", "Fence",
               "Guard dog", "Windows - ULC security film", "Additional combination lock", "Additional key",
               "Alarm 'fine wire' protecting openings", "Camera with concealed VCR recording on film",
               "Common tenant walls reinforced with steel mesh", "Electronic lock",
               "Entrance visible from street", "Exterior doors of sturdy construction, inside hinges",
               "Exterior lighting", "Hold-up buttons", "Metal loading doors, secured internally",
               "Motion sensitive lighting", "Multiple lock styles", "Perimeter fence and lockable gate",
               "Property / lot illuminated at night", "Skylight / roof AC openings blocked off",
               "Steel post (front & rear) to prevent vehicle entry", "Stock secured - separate enclosure",
               "Stockroom ceiling entirely covered by motion sensor", "Warehouse area alarmed separately from office",
               "Warning signs", "Windows - glass breakage detectors", "Other"]
SAFE_TYPE = ["Fire", "Burglary", "Vault", "None"]
SAFE_CLASS = ["1", "2", "3", "4", "5", "Other"]
CLAIM_STATUS = ["Open", "Close"]

# ---- the schedule of coverages: (row key, label, basis, group); basis = bn (Broad / Named), robbery, text
SCHEDULE = [
    ("bes", "Building, equipment and stock", "bn", "Property"),
    ("bldg_rc", "Building - replacement cost", "text", "Property"),
    ("equip_rc", "Equipment - replacement cost", "text", "Property"),
    ("stock", "Stock", "text", "Property"),
    ("leasehold", "Leasehold improvements", "text", "Property"),
    ("office", "Office contents (Broad)", "text", "Property"),
    ("edp", "Electronic data processing systems (Broad)", "text", "Property"),
    ("papers", "Valuable papers & records (Broad)", "text", "Property"),
    ("receivable", "Accounts receivable (Broad)", "text", "Property"),
    ("res_condo", "Residential condominiums (Broad)", "text", "Property"),
    ("com_condo", "Commercial condominiums (Broad)", "text", "Property"),
    ("contractors", "Contractor's equipment", "bn", "Property"),
    ("tool", "Tool floater", "bn", "Property"),
    ("transport", "Transportation floater", "bn", "Property"),
    ("cargo_owner", "Motor truck cargo - owner's", "bn", "Property"),
    ("cargo_truckmen", "Motor truck cargo - truckmen's", "bn", "Property"),
    ("builders", "Builders risk", "text", "Property"),
    ("install", "Installation floater", "bn", "Property"),
    ("bailees", "Bailees' customers", "bn", "Property"),
    ("warehouse", "Warehouseman's legal liability", "bn", "Property"),
    ("signs", "Signs floater (Broad)", "text", "Property"),
    ("consequential", "Consequential loss", "text", "Property"),
    ("sewer", "Sewer back up", "text", "Property"),
    ("flood", "Flood", "text", "Property"),
    ("quake", "Earthquake", "text", "Property"),
    ("custom1", "Other (write it in)", "text", "Property"),
    ("custom2", "Other (write it in)", "text", "Property"),
    ("custom3", "Other (write it in)", "text", "Property"),
    ("bi_profits", "Profits (Broad / Named)", "bn", "Business interruption"),
    ("bi_rentals", "Gross rentals", "bn", "Business interruption"),
    ("bi_extra", "Extra expense", "bn", "Business interruption"),
    ("bi_als", "ALS (actual loss sustained)", "bn", "Business interruption"),
    ("machinery", "Machinery breakdown", "text", "Machinery breakdown"),
    ("crime_3d", "Comprehensive 3 D", "text", "Crime"),
    ("crime_dishonesty", "Employee dishonesty (individual)", "text", "Crime"),
    ("crime_money", "Money & securities", "robbery", "Crime"),
    ("crime_orders", "Money orders & counterfeit paper currency", "text", "Crime"),
    ("crime_forgery", "Depositors forgery", "text", "Crime"),
    ("gl", "Commercial general liability (occurrence form)", "text", "Liability"),
    ("tll", "Tenants' legal liability", "bn", "Liability"),
    ("nonowned_spf6", "Non-owned automobile liability (SPF 6)", "text", "Liability"),
    ("emp_benefits", "Employee benefits liability", "text", "Liability"),
    ("emp_bi", "Employers' bodily injury liability", "text", "Liability"),
    ("nonowned_auto", "Non-owned auto", "text", "Liability"),
    ("pollution", "Pollution liability", "text", "Liability"),
    ("tll2", "Tenants legal liability (second line)", "text", "Liability"),
]
SCHEDULE_ROWS = {r[0]: r for r in SCHEDULE}
BASIS_CHOICES = {"bn": ["Broad", "Named"], "robbery": ["Broad", "Robbery"]}
LIABILITY_GROUPS = ["Liability"]


def schedule_keys(row):
    """Cell keys of one schedule row: include, basis, deductible, limit (+ the written-in name of the 'Other' rows)."""
    base = f"sch_{row}"
    keys = {"inc": base, "basis": base + "_basis", "ded": base + "_ded", "limit": base + "_limit"}
    if row.startswith("custom"):
        keys["desc"] = base + "_desc"
    return keys


def F(key, label, kind="text", options=None, hint=""):
    """(key, label, kind, options, uses, hint)   kind: text num year yn choice multi date money long."""
    return (key, label, kind, options, "", hint)


def table(prefix, title, rows, cols, hint=""):
    """A grid of small boxes. rows = [(row key, row label)]; cols = [(suffix, header, kind, options, width)].
    The answer for a cell is saved as <prefix><row key>_<suffix> (for example contact1_last)."""
    return {"table": prefix, "title": title, "rows": rows, "cols": cols, "hint": hint}


def schedule_table(group, title):
    return {"schedule": group, "title": title}


def location_fields(n):
    """The General + Construction questions of one location. Location 1 keeps the plain key names; 2 and 3 get l2_ / l3_."""
    p = "" if n == 1 else f"l{n}_"
    return [
        F(p + "loc_number", "Location number"),
        F(p + "loc_visited", "Location visited by producer", "yn"),
        F(p + "loc_visit_date", "Date visited by producer", "date"),
        F(p + "loc_address", "Address", "text", None, "Left empty = the business address is used" if n == 1 else ""),
        F(p + "loc_city", "City"), F(p + "loc_province", "Province"), F(p + "loc_country", "Country"),
        F(p + "loc_postal", "Postal code"),
        F(p + "loc_not_inspected", "This risk was not inspected", "yn"),
        F(p + "loc_inspect_date", "Date risk was inspected", "date"),
        F(p + "loc_inspector", "Inspected by"),
        F(p + "loc_rating", "This risk is", "choice", RATING),
        F(p + "storeys", "Stories", "num"),
        F(p + "year_built", "Year built", "year"),
        F(p + "sq_ft", "Total area", "num"),
        F(p + "area_unit", "Area is in", "choice", AREA_UNIT),
        F(p + "walls", "Walls", "multi", WALLS),
        F(p + "floors", "Floors", "multi", FLOORS),
        F(p + "basement", "Basement", "multi", BASEMENT),
        F(p + "roof", "Roof", "multi", ROOF),
        F(p + "roof_cover", "Roof covering", "multi", ROOF_COVER),
        F(p + "electrical", "Electrical", "choice", ELECTRICAL),
        F(p + "plumbing", "Plumbing", "multi", PLUMBING),
        F(p + "heating", "Heating", "multi", HEATING),
        F(p + "fuel", "Fuel", "multi", FUEL),
    ]


# (key, title, items, flags)    items: field tuples, table(...) or schedule_table(...);   flags: {"property": True}
SECTIONS = [
    ("about", "Client information", [
        F("dwelling", "Type of business", "choice", BUSINESS),
        F("broker_name", "Broker name"),
        F("branch", "Branch number", "text", None, "For example B01"),
        F("pb_code", "Power Broker client code", "text", None, "Built from the business operating name"),
        F("pb_binder", "PowerBroker binder number", "text", None, "Goes in the submission subject line"),
        F("effective_date", "Effective date of coverage", "date", None, "Binding can never be back-dated"),
        F("legal_name", "Registered name of the business", "text", None, "Must match the PowerBroker customer name and the policyholder"),
        F("trade_name", "Trade / operating name"),
        F("address", "Postal address", "text", None, "Street address"),
        F("city", "City"), F("province", "Province"), F("country", "Country"), F("postal", "Postal code"),
        F("phone", "Phone", "text"), F("email", "E-mail", "text"), F("website", "Website", "text"),
        F("entity", "Client is", "choice", ENTITY, "Corporation: articles of incorporation"),
        F("description", "Description of business operations", "long", None,
          "Be descriptive. If you own the building: who the tenants are and what they do"),
        F("known_month", "Broker has known the client since - month"),
        F("known_year", "Broker has known the client since - year", "year"),
        F("supporting_business", "Supporting business"),
    ], {}),
    ("contacts", "Client contacts (decision makers / owners)", [
        table("contact", "Client contacts", [(str(i), f"Contact {i}") for i in range(1, 5)], [
            ("last", "Last name", "text", None, 120), ("first", "First name", "text", None, 120),
            ("title", "Mr./Ms.", "text", None, 70), ("position", "Position", "text", None, 120),
            ("phone", "Phone", "text", None, 120), ("email", "E-mail", "text", None, 170),
            ("other", "Other", "text", None, 100)]),
    ], {}),
    ("business", "Liability information - business, revenue and liquor", [
        F("in_business_since", "In business since", "text", None, "A year, for example 2015"),
        F("employees_ft", "Employees (full time)", "num"),
        F("employees_pt", "Employees (part time)", "num"),
        F("wcb", "Covered by WCB", "yn"),
        F("years_experience", "Related prior experience (years)", "num", None,
          "Contractors / trades: 3 years minimum for most markets"),
        F("receipts", "Annual gross receipts ($)", "money"),
        F("pct_internet", "Internet sales (%)", "num"),
        F("pct_subtrades", "Subtrades (%)", "num"),
        F("pct_canada", "Canadian (%)", "num", None, "Canadian + US + foreign = 100"),
        F("pct_us", "US (%)", "num", None, "US sales can limit the markets"),
        F("pct_foreign", "Foreign (%)", "num"),
        F("payroll", "Annual payroll ($)", "money"),
        F("liquor", "Is there any liquor liability", "yn"),
        F("liquor_plan", "Are there plans to be liquor licensed", "yn"),
        F("receipts_liquor", "Receipt splits - liquor ($)", "money", None, "Over 60 % of revenue is declined by some markets"),
        F("receipts_food", "Receipt splits - food ($)", "money"),
        F("receipts_other", "Receipt splits - other ($)", "money"),
    ], {}),
    ("claims", "Claims and previous policy", [
        F("no_claims", "No losses or claims in the last 5 years", "yn"),
        F("claims_unknown", "Prior claims unknown", "yn"),
        table("claim", "Claims information (dates as mm/dd/yyyy)", [(str(i), f"Claim {i}") for i in range(1, 6)], [
            ("date", "Loss date", "text", None, 130), ("type", "Type", "text", None, 120),
            ("description", "Description", "text", None, 260), ("paid", "Amt paid", "money", None, 80),
            ("reserve", "Reserve", "money", None, 80), ("status", "Status", "choice", CLAIM_STATUS, 90)]),
        F("claims_notes", "Claims notes", "long"),
        F("no_prev_policies", "No previous policies", "yn"),
        F("prior_carrier_unknown", "Prior carrier unknown", "yn"),
        F("prior_type", "Previous policy - type"),
        F("prior_insurer", "Previous policy - insurer"),
        F("prior_effective", "Previous policy - effective", "date"),
        F("prior_expiry", "Previous policy - expiry", "date"),
        F("prior_terminated", "Reason terminated"),
        F("prior_cancelled", "Reason cancelled"),
        F("prior_policy", "Previous policy number"),
        F("mortgagee", "Mortgage information (bank and address)", "long", None, "Name and address; Intact Edge takes at most two"),
    ], {}),
    ("occupancy", "Occupancy and exposures", [
        F("occupancy", "Occupancy", "multi", OCCUPANCY, "Description of the space the insured occupies"),
        F("occupancy_other", "Occupancy - other"),
        F("exposure_types", "Exposures", "multi", EXPOSURE_TYPES),
        table("exposure_", "Neighbouring buildings", [("left", "Left of insured"), ("right", "Right of insured"),
                                                       ("behind", "Behind insured"), ("front", "Front of insured")], [
            ("distance", "Distance (meters)", "text", None, 110), ("occupancy", "Occupancy", "text", None, 330)]),
        F("exposure_notes", "Other neighbouring-business notes", "long", None,
          "Restaurants, bars, clubs and manufacturing next door matter"),
    ], {}),
    ("liability_cov", "Liability coverage", [schedule_table("Liability", "Liability schedule")], {}),
    ("loc1", "Location 1 - general and construction", location_fields(1), {"property": True}),
    ("renovations", "Renovations", [
        F("reno_none", "None known", "yn"),
        F("wiring_year", "Electrical - year", "year"), F("wiring_extent", "Electrical - complete / partial", "choice", EXTENT),
        F("plumbing_year", "Plumbing - year", "year"), F("plumbing_extent", "Plumbing - complete / partial", "choice", EXTENT),
        F("heating_year", "Heating - year", "year"), F("heating_extent", "Heating - complete / partial", "choice", EXTENT),
        F("roof_year", "Roof - year", "year"), F("roof_extent", "Roof - complete / partial", "choice", EXTENT),
    ], {"property": True}),
    ("fire", "Fire protection", [
        F("hydrant", "Hydrants", "choice", HYDRANT),
        F("fire_hall", "Fire department", "choice", FIRE_HALL),
        F("extinguishing", "Extinguishing system type", "choice", EXTINGUISHING),
        F("extinguishing_other", "Extinguishing system - other (describe)"),
        F("agent", "Extinguishing agent type", "multi", AGENT),
        F("fire_alarm", "Fire alarm", "choice", FIRE_ALARM),
    ], {"property": True}),
    ("crime", "Crime protection", [
        F("crime_types", "Protection types", "multi", CRIME_TYPES),
        F("crime_other", "Protection - other (describe)"),
        F("burglar_alarm", "Burglar alarm", "choice", BURGLAR_ALARM),
        F("safe_type", "Safe type", "multi", SAFE_TYPE),
        F("safe_class", "Safe class", "choice", SAFE_CLASS),
        F("safe_class_other", "Safe class - other (describe)"),
    ], {"property": True}),
    ("property_cov", "Property coverage", [
        schedule_table("Property", "Property"),
        schedule_table("Business interruption", "Business interruption"),
        schedule_table("Machinery breakdown", "Machinery breakdown"),
        schedule_table("Crime", "Crime"),
    ], {"property": True}),
    ("misc", "Fine arts / miscellaneous property / tool floater / other", [
        table("misc", "Items", [(str(i), f"Item {i}") for i in range(1, 17)], [
            ("item", "Item #", "text", None, 60), ("desc", "Description of item", "text", None, 380),
            ("limit", "Limit", "money", None, 100)]),
    ], {"property": True}),
    ("wrapup", "Broker notes", [
        F("broker_notes", "Broker notes", "long"),
        F("app_date", "Date of application", "date"),
    ], {}),
    ("other", "Other questions the markets ask", [
        F("own_or_rent", "Owns or rents the premises", "choice", OWN_OR_RENT),
        F("years_location", "Years at this location", "num"),
        F("work_away", "Work done away from the premises", "yn"),
        F("snow_removal", "Snow removal for others", "yn"),
        F("subcontractors", "Uses subcontractors", "yn", None, "Proof of their insurance is needed"),
        F("deep_fryers", "Deep fryers or other cooking with grease", "yn", None,
          "Wet-chemical suppression system needed; dry chemical is declined by Echelon"),
        F("suppression", "Approved wet-chemical suppression system and hood", "yn", None, "UL300 / ULC 1254.6 and NFPA 96"),
        F("duct_cleaning", "Hood / duct cleaning", "choice", CLEANING, "Report must be attached"),
        F("live_entertainment", "Dancing, DJ or live entertainment", "yn", None, "Nightclubs are declined by most markets"),
        F("hookah", "Hookah / shisha", "yn", None, "Declined by most markets"),
        F("delivery", "Food delivery", "yn"),
        F("ulc_cert", "ULC alarm certificate available", "yn", None, "Credit is only given once it is in"),
        F("cash", "Cash kept on the premises", "yn"),
        F("has_vehicles", "The business has vehicles to insure", "yn", None, "Needs the Commercial Vehicle Supplement"),
        F("vehicle_count", "Number of vehicles", "num", None, "5 or more: fleet supplement"),
        F("vehicle_use", "Main business use of the vehicles", "text", None, "For example: plumber visits job sites"),
        F("commodities", "What is carried (tools, goods, passengers)"),
        F("radius", "Usual operating distance", "choice", RADIUS, "Over 80 km: refer to the underwriter"),
        F("usa_exposure", "Drives into the USA", "yn", None, "Most markets decline US exposure"),
        F("hauls_others", "Carries goods for others", "yn", None, "Not written by IRCA (Echelon)"),
        F("heavy", "Vehicles over 4,500 kg (heavy)", "yn", None, "CVOR certificate and a $2,500 minimum deductible"),
        F("cvor", "CVOR number", "text", None, "Trucking and heavy vehicles"),
        F("dangerous", "Dangerous goods, fuel, cement, scrap or alcohol / cannabis", "yn", None, "Mostly not written"),
        F("young_driver", "Any driver under 25 or licensed under 3 years", "yn", None, "Referred by most markets"),
    ], {}),
]
# Locations 2 and 3 are optional extra pages (the application adds a "location" page for each)
for _n in (2, 3):
    SECTIONS.insert(next(i for i, s in enumerate(SECTIONS) if s[0] == "renovations"),
                    (f"loc{_n}", f"Location {_n} - general and construction (only if there is one)",
                     location_fields(_n), {"property": True, "extra": True}))


def _flat():
    """{key: field tuple} for every answer the page can hold, tables and schedule cells included."""
    out = {"liability_only": F("liability_only", "Liability only", "yn")}
    for _key, _title, items, _flags in SECTIONS:
        for item in items:
            if isinstance(item, tuple):
                out[item[0]] = item
            elif "table" in item:
                for rk, rlabel in item["rows"]:
                    for suffix, header, kind, options, _w in item["cols"]:
                        k = f"{item['table']}{rk}_{suffix}"
                        out[k] = (k, f"{rlabel} - {header}", kind, options, "", "")
            else:
                for row, label, basis, group in SCHEDULE:
                    if group != item["schedule"]:
                        continue
                    keys = schedule_keys(row)
                    out[keys["inc"]] = (keys["inc"], label, "yn", None, "", "")
                    out[keys["basis"]] = (keys["basis"], f"{label} - basis", "text", None, "", "")
                    out[keys["ded"]] = (keys["ded"], f"{label} - deductible", "text", None, "", "")
                    out[keys["limit"]] = (keys["limit"], f"{label} - limit", "text", None, "", "")
                    if "desc" in keys:
                        out[keys["desc"]] = (keys["desc"], f"{label} - what", "text", None, "", "")
    return out


FIELDS = _flat()
LABELS = {k: f[1] for k, f in FIELDS.items()}
DWELLING = BUSINESS                     # the page's "pick one" list
PICK_LABEL = "Type of business"
REQUIRED = ["dwelling", "legal_name", "description", "effective_date", "address", "in_business_since", "receipts"]
REQUIRED_PROPERTY = ["year_built", "sq_ft"]            # not asked of a liability-only application
MULTI_SEP = "; "


def is_liability_only(values):
    return (values or {}).get("liability_only") == "Yes"


def section_visible(flags, values):
    """A section is hidden while 'Liability only' is on, if it belongs to the property side of the application."""
    return not (flags.get("property") and is_liability_only(values))


def visible_sections(values):
    return [s for s in SECTIONS if section_visible(s[3], values)]


def section_keys(items):
    """The answer keys behind a section's items (a schedule row counts once, by its 'include' key)."""
    keys = []
    for item in items:
        if isinstance(item, tuple):
            keys.append(item[0])
        elif "table" in item:
            keys += [f"{item['table']}{rk}_{c[0]}" for rk, _l in item["rows"] for c in item["cols"]]
        else:
            keys += [schedule_keys(r[0])["inc"] for r in SCHEDULE if r[3] == item["schedule"]]
    return keys


def is_answered(values, key):
    """A question has an answer; a schedule line has one when it is ticked or has a basis / deductible / limit."""
    if key.startswith("sch_") and key in _SCHEDULE_INC:
        return any(values.get(k) for k in _SCHEDULE_INC[key])
    return bool(values.get(key))


_SCHEDULE_INC = {schedule_keys(r[0])["inc"]: list(schedule_keys(r[0]).values()) for r in SCHEDULE}


def use_of(values):
    return "commercial"


def fields_for(use=None):
    return [(key, title, [i for i in items if isinstance(i, tuple)]) for key, title, items, _flags in SECTIONS]


def multi_values(value):
    """'Wood; Steel' -> ['Wood', 'Steel']."""
    return [v.strip() for v in str(value or "").split(MULTI_SEP.strip()) if v.strip()]


def _yes(values, key):
    return values.get(key) == "Yes"


def _num(v):
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None


def completeness(values):
    """(filled, total, [labels still missing]). A liability-only application skips the property questions."""
    need = list(REQUIRED) + ([] if is_liability_only(values) else REQUIRED_PROPERTY)
    missing = [LABELS[k] for k in need if values.get(k) in (None, "")]
    total = len(need) + 2
    if not (values.get("no_claims") == "Yes" or values.get("claims_unknown") == "Yes" or values.get("claim1_date")
            or values.get("claim1_description")):
        missing.append("Claims (or tick 'no losses')")
    if not (values.get("prior_insurer") or values.get("no_prev_policies") == "Yes"
            or values.get("prior_carrier_unknown") == "Yes"):
        missing.append("Previous policy (or tick 'no previous policies')")
    return total - len(missing), total, missing


def kind_of_business(values):
    return values.get("dwelling", "")


def _alarmed(value):
    return bool(value) and value not in ("None / not applicable", "Unknown", "Other") and \
        value.split()[0] in ("Central", "Monitoring", "Local", "Visually")


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
    if business == "Restaurant / food service" or _yes(values, "deep_fryers"):
        need["Restaurant questionnaire"] = "every restaurant: fire suppression and duct cleaning reports attached"
    if business == "Health / wellness / beauty":
        need["Industry application"] = "health care, spa or cosmetology: the insurer's own application (for example Forward)"
    if not is_liability_only(values) and (_alarmed(values.get("burglar_alarm")) or _alarmed(values.get("fire_alarm"))
                                          or _yes(values, "ulc_cert")):
        need["Alarm certificate (ULC)"] = "alarm credit is only applied once the certificate is in"
    if _yes(values, "subcontractors"):
        need["Subcontractor insurance"] = "certificates of insurance for every subcontractor"
    if values.get("mortgagee"):
        need["Mortgage information"] = "mortgagee / loss payee name and address"
    if not is_liability_only(values) and (values.get("own_or_rent") or values.get("loc_address") or values.get("address")):
        need["Photos of the location"] = "photos of the outside and the inside of the premises"
    return need


def load(folder):
    data = records.load(folder).get(KEY)
    return dict(data) if isinstance(data, dict) else {}


def save(folder, values):
    """Save the answers (atomic, re-reads the file so other changes are kept).

    A schedule line that has a basis, deductible, limit or name gets its 'include' box ticked."""
    clean = {k: str(v).strip() for k, v in values.items() if k in FIELDS and str(v).strip()}
    for row in SCHEDULE_ROWS:
        keys = schedule_keys(row)
        if any(clean.get(keys[k]) for k in keys if k != "inc"):
            clean[keys["inc"]] = "Yes"
    data = records.load(folder)
    data[KEY] = clean
    records._write(folder, data)
    return clean


def save_contact(folder, name):
    """Put a person's name in the first empty contact row (used when a commercial client is created with an owner)."""
    name = " ".join(str(name or "").split())
    if not name:
        return
    values = load(folder)
    if any(values.get(f"contact{i}_first") or values.get(f"contact{i}_last") for i in range(1, 5)):
        return
    first, _, last = name.rpartition(" ")
    values["contact1_first"], values["contact1_last"] = (first, last) if first else ("", last)
    save(folder, values)


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
