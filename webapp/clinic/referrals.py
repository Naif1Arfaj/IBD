"""Referral prioritization rules. Transparent rules only: no ML, no probabilities, no Django.

DRAFT: pending review by a clinician. IBDMDB's non-IBD group has no recorded alternative diagnoses, so there
is no data to train on. Every rule cites its source; a rule whose source could not be found was left out.
Sources were checked from abstracts, guideline summaries and local NHS pathways, so reviewers should confirm
them against full texts and adapt them to Saudi pathways. Changing any rule must bump RULES_VERSION.
"""
RULES_VERSION = "referrals-draft-1"

PRIORITY_ORDER = ["routine", "soon", "urgent", "emergency"]
PRIORITY_LABELS = {"routine": "Routine", "soon": "Soon", "urgent": "Urgent", "emergency": "Emergency"}

SOURCES = {
    "truelove": ("Truelove & Witts severity criteria for acute severe ulcerative colitis, including the CRP > 30 mg/L "
                 "modification endorsed by BSG/ECCO. Defined for known UC; cut-offs vary slightly between sources."),
    "ng12": "NICE NG12 suspected cancer guidance, as summarised by the Macmillan Rapid Referral Guidelines.",
    "fc_pathway": ("Nottinghamshire primary care faecal calprotectin guide: under 100 µg/g IBD unlikely; 100-250 repeat, "
                   "then routine referral; above 250 urgent referral. A local UK pathway, not a national standard."),
    "perianal": ("Research library: Munster et al., Techniques in Coloproctology 2025: perianal disease is the first "
                 "manifestation in about one third of patients with Crohn's-related perianal disease."),
    "celiac": "ACG 2023 celiac guideline (Rubio-Tapia et al.): tTG-IgA with total IgA first; confirm with duodenal biopsies.",
    "infection": "2019 ECCO-ESGAR guideline, as summarised by BMJ Best Practice: stool culture and C. difficile testing.",
    "nsaid": ("Research library: Environmental Risk Factors for IBD (2010): NSAIDs can damage small-bowel and colonic "
              "mucosa. Listed as a mimic in the Detailed Project Report, section 4.3."),
    "ibs": "BJGP 2025 IBS algorithm (full blood count, CRP, coeliac serology), with the calprotectin pathway above.",
    "blood_tests": "BNSSG (Bristol) suspected-IBD pathway: full blood count, ferritin, CRP and tTG antibodies.",
    "model": "IBD Care product rule on the prototype estimate; not a validated referral criterion.",
}

# Shown on the About page so a clinician can review and sign off every rule.
RULE_TABLE = [
    ("E1", "Emergency", "6 or more bloody stools a day plus temperature above 37.5 C, pulse above 90, "
                        "haemoglobin below 10.5 g/dL or CRP above 30 mg/L", SOURCES["truelove"]),
    ("U1", "Urgent", "Abdominal or rectal mass", SOURCES["ng12"]),
    ("U2", "Urgent", "Under 50 with rectal bleeding plus abdominal pain, altered bowel habit, weight loss "
                     "or iron deficiency", SOURCES["ng12"]),
    ("U3", "Urgent", "Symptoms with calprotectin above 250 µg/g", SOURCES["fc_pathway"]),
    ("S1", "Soon", "Perianal fistula or abscess recorded", SOURCES["perianal"]),
    ("S2", "Soon", "Positive celiac serology", SOURCES["celiac"]),
    ("S3", "Soon", "Positive stool infection test", SOURCES["infection"]),
    ("S4", "Soon", "High prototype risk level", SOURCES["model"]),
    ("R1", "Routine", "Symptoms with calprotectin 100-250 µg/g", SOURCES["fc_pathway"]),
    ("M1", "Consider", "Recent gastroenteritis or travel: consider infection", SOURCES["infection"]),
    ("M2", "Consider", "NSAID use recorded: consider NSAID-related injury", SOURCES["nsaid"]),
    ("M3", "Consider", "Symptoms, no alarm features, calprotectin below 100 µg/g: consider IBS", SOURCES["ibs"]),
]

GASTRO = "Gastroenterology"
PRIMARY = "Primary care follow-up"


def _number(value):
    try:
        return None if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        return None


def _flag(value):
    return value in (1, 1.0, "1", "1.0", "Yes", "yes")


def prioritize(inputs, assessment):
    """Return priority, department, reasons, conditions to consider, missing tests and unrecorded items.

    `inputs` holds the review form values ("yes" / "no" / "unknown", test results, numbers or None).
    `assessment` needs .tier and .inputs. Unknown never counts as absent: it is listed under not_recorded.
    """
    def yes(key):
        return inputs.get(key) == "yes"

    model = assessment.inputs
    age = _number(model.get("age_years"))
    calprotectin = _number(model.get("fecal_calprotectin_ug_g"))
    crp = _number(model.get("CRP_mg_L"))
    nsaid = _number(model.get("NSAID_use_times_month"))
    perianal = _flag(model.get("perianal_fistula_history"))

    bloody = _number(inputs.get("bloody_stools_per_day"))
    temperature = _number(inputs.get("temperature_c"))
    pulse = _number(inputs.get("pulse_bpm"))
    haemoglobin = _number(inputs.get("haemoglobin_g_dl"))
    diarrhoea_weeks = _number(inputs.get("diarrhoea_weeks"))
    has_diarrhoea = diarrhoea_weeks is not None and diarrhoea_weeks > 0
    stool = inputs.get("stool_infection_test", "not_done")
    celiac = inputs.get("celiac_serology", "not_done")

    has_symptoms = (has_diarrhoea or yes("rectal_bleeding") or yes("abdominal_pain") or yes("nocturnal_symptoms")
                    or yes("weight_loss") or (bloody is not None and bloody > 0))

    reasons, consider, missing = [], [], []

    def act(rule_id, priority, department, text, source):
        reasons.append({"rule_id": rule_id, "priority": priority, "department": department,
                        "text": text, "source": SOURCES[source]})

    # Emergency rules are checked first and always win.
    systemic = ((temperature is not None and temperature > 37.5) or (pulse is not None and pulse > 90)
                or (haemoglobin is not None and haemoglobin < 10.5) or (crp is not None and crp > 30))
    if bloody is not None and bloody >= 6 and systemic:
        act("E1", "emergency", "Emergency department / on-call gastroenterology",
            "Six or more bloody stools a day with systemic upset: possible acute severe colitis.", "truelove")

    if yes("abdominal_or_rectal_mass"):
        act("U1", "urgent", GASTRO + " / colorectal surgery", "Abdominal or rectal mass recorded.", "ng12")
    if (yes("rectal_bleeding") and age is not None and age < 50
            and (yes("abdominal_pain") or has_diarrhoea or yes("weight_loss") or yes("iron_deficiency"))):
        act("U2", "urgent", GASTRO,
            "Rectal bleeding under 50 with pain, altered bowel habit, weight loss or iron deficiency.", "ng12")

    # Calprotectin pathways are written for symptomatic patients, so they are not applied without symptoms.
    if has_symptoms and calprotectin is not None:
        if calprotectin > 250:
            act("U3", "urgent", GASTRO, f"Symptoms with calprotectin {calprotectin:g} µg/g (above 250).", "fc_pathway")
        elif calprotectin >= 100:
            act("R1", "routine", GASTRO,
                f"Symptoms with calprotectin {calprotectin:g} µg/g (100-250): repeat, then refer if still raised.",
                "fc_pathway")

    if perianal:
        act("S1", "soon", GASTRO + " / colorectal surgery",
            "Perianal fistula or abscess recorded: can be the first sign of Crohn's disease.", "perianal")
    if celiac == "positive":
        act("S2", "soon", GASTRO, "Positive celiac serology: confirm with duodenal biopsies.", "celiac")
        consider.append({"condition": "Celiac disease", "why": "Positive serology.", "source": SOURCES["celiac"]})
    if stool == "positive":
        act("S3", "soon", "Primary care / infectious diseases",
            "Positive stool infection test: assess the infection before attributing symptoms to IBD.", "infection")
        consider.append({"condition": "Gastrointestinal infection", "why": "Positive stool test.",
                         "source": SOURCES["infection"]})
    elif yes("recent_gastroenteritis_or_travel"):
        consider.append({"condition": "Gastrointestinal infection", "why": "Recent gastroenteritis or travel.",
                         "source": SOURCES["infection"]})
    if assessment.tier == "High":
        act("S4", "soon", GASTRO,
            "High prototype risk level. This estimate comes from synthetic data and is not a referral criterion.",
            "model")

    if nsaid is not None and nsaid > 0:
        consider.append({"condition": "NSAID-related intestinal injury",
                         "why": f"NSAID use recorded ({nsaid:g} {'time' if nsaid == 1 else 'times'} a month). Review the medication.",
                         "source": SOURCES["nsaid"]})

    # IBS is only suggested when every alarm feature is recorded as absent; unknown does not count.
    alarm_keys = ("rectal_bleeding", "weight_loss", "nocturnal_symptoms", "iron_deficiency", "abdominal_or_rectal_mass")
    alarms_absent = all(inputs.get(k) == "no" for k in alarm_keys) and not perianal
    if (has_symptoms and alarms_absent and calprotectin is not None and calprotectin < 100
            and celiac != "positive" and stool != "positive"):
        consider.append({"condition": "Irritable bowel syndrome",
                         "why": "Symptoms without recorded alarm features, and calprotectin below 100 µg/g.",
                         "source": SOURCES["ibs"]})

    if has_diarrhoea or yes("recent_gastroenteritis_or_travel"):
        if stool not in ("positive", "negative"):
            missing.append("Stool culture and C. difficile test")
    if has_symptoms:
        if celiac not in ("positive", "negative"):
            missing.append("Celiac serology (tTG-IgA with total IgA)")
        if haemoglobin is None or inputs.get("iron_deficiency", "unknown") == "unknown":
            missing.append("Full blood count and ferritin")

    labels = {"rectal_bleeding": "Rectal bleeding", "abdominal_pain": "Abdominal pain",
              "nocturnal_symptoms": "Nocturnal symptoms", "weight_loss": "Unintentional weight loss",
              "iron_deficiency": "Iron deficiency", "abdominal_or_rectal_mass": "Abdominal or rectal mass",
              "recent_gastroenteritis_or_travel": "Recent gastroenteritis or travel"}
    not_recorded = [text for key, text in labels.items() if inputs.get(key, "unknown") == "unknown"]

    if reasons:
        top = max(reasons, key=lambda r: PRIORITY_ORDER.index(r["priority"]))
        priority, department = top["priority"], top["department"]
    else:
        priority, department = "routine", PRIMARY
    reasons.sort(key=lambda r: -PRIORITY_ORDER.index(r["priority"]))

    return {
        "priority": priority, "priority_label": PRIORITY_LABELS[priority], "department": department,
        "reasons": reasons, "consider": consider, "missing_tests": missing, "not_recorded": not_recorded,
        "has_symptoms": has_symptoms, "rules_version": RULES_VERSION,
    }
