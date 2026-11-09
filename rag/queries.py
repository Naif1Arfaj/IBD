"""Human-readable label, unit and literature search query for every model input."""

# feature: (label, unit, research query)
FEATURE_INFO = {
    # Demographic data
    "age_years": ("Age", "years", "age at onset of inflammatory bowel disease adolescents young adults"),
    "sex": ("Sex", "", "sex differences incidence Crohn's disease ulcerative colitis"),
    "BMI_kg_m2": ("BMI", "kg/m²", "body mass index obesity risk of inflammatory bowel disease"),
    # Signs and symptoms
    "diarrhea": ("Diarrhoea", "", "chronic diarrhoea presenting symptom inflammatory bowel disease"),
    "constipation": ("Constipation", "", "constipation symptoms inflammatory bowel disease irritable bowel syndrome"),
    "alternating_diarrhea_constipation": ("Alternating diarrhoea and constipation", "", "alternating bowel habit irritable bowel syndrome versus inflammatory bowel disease"),
    "bowel_movements_per_day": ("Bowel movements per day", "per day", "stool frequency disease activity ulcerative colitis Crohn's disease"),
    "increased_bowel_frequency": ("Increased bowel frequency", "", "increased stool frequency symptom inflammatory bowel disease"),
    "stool_consistency_bristol": ("Stool consistency (Bristol scale)", "type 1–7", "Bristol stool form scale loose stools inflammatory bowel disease"),
    "blood_in_stool": ("Blood in stool", "", "blood in stool red flag symptom inflammatory bowel disease"),
    "visible_rectal_bleeding": ("Visible rectal bleeding", "", "rectal bleeding ulcerative colitis diagnosis"),
    "mucus_in_stool": ("Mucus in stool", "", "mucus in stool symptom colitis"),
    "nocturnal_bowel_movements": ("Night-time bowel movements", "", "nocturnal diarrhoea organic disease inflammatory bowel disease"),
    "urgency_defecation": ("Urgency to defecate", "", "bowel urgency ulcerative colitis symptom"),
    "tenesmus": ("Tenesmus", "", "tenesmus proctitis ulcerative colitis"),
    "change_in_bowel_habits": ("Change in bowel habits", "", "change in bowel habit symptoms inflammatory bowel disease"),
    "abdominal_pain": ("Abdominal pain", "", "abdominal pain presenting symptom Crohn's disease"),
    "abdominal_pain_severity_0_10": ("Abdominal pain severity", "0–10", "abdominal pain severity inflammatory bowel disease activity"),
    "abdominal_pain_location": ("Abdominal pain location", "", "right lower quadrant abdominal pain Crohn's disease ileitis"),
    "abdominal_cramping": ("Abdominal cramping", "", "abdominal cramping symptom inflammatory bowel disease"),
    "abdominal_bloating": ("Abdominal bloating", "", "bloating symptoms inflammatory bowel disease"),
    "excessive_gas_flatulence": ("Excessive gas / flatulence", "", "flatulence gas symptoms inflammatory bowel disease"),
    "nausea": ("Nausea", "", "nausea symptom Crohn's disease"),
    "vomiting": ("Vomiting", "", "vomiting stricturing Crohn's disease"),
    "loss_of_appetite": ("Loss of appetite", "", "loss of appetite anorexia inflammatory bowel disease"),
    "unintentional_weight_loss": ("Unintentional weight loss", "", "unintentional weight loss Crohn's disease diagnosis"),
    "symptom_duration_weeks": ("Symptom duration", "weeks", "symptom duration diagnostic delay inflammatory bowel disease"),
    "symptom_frequency": ("Symptom frequency", "", "persistent symptoms diagnostic delay inflammatory bowel disease"),
    "fatigue": ("Fatigue", "", "fatigue inflammatory bowel disease"),
    "persistent_tiredness": ("Persistent tiredness", "", "chronic tiredness fatigue inflammatory bowel disease"),
    "fever": ("Fever", "", "fever systemic symptoms Crohn's disease"),
    "night_sweats": ("Night sweats", "", "night sweats systemic symptoms inflammatory bowel disease"),
    "unexplained_weight_loss": ("Unexplained weight loss", "", "unexplained weight loss red flag inflammatory bowel disease"),
    "reduced_energy_levels": ("Reduced energy levels", "", "low energy fatigue inflammatory bowel disease"),
    # Family history
    "family_history_IBD": ("Family history of IBD", "", "family history first-degree relatives risk of inflammatory bowel disease"),
    "family_history_autoimmune": ("Family history of autoimmune disease", "", "autoimmune disease association inflammatory bowel disease"),
    # Diet
    "fiber_g_day": ("Dietary fiber", "g/day", "dietary fiber intake risk of Crohn's disease"),
    "fast_food_times_week": ("Fast food", "times/week", "fast food western diet risk inflammatory bowel disease"),
    "ultra_processed_food_times_week": ("Ultra-processed food", "times/week", "ultra-processed food consumption risk of inflammatory bowel disease"),
    "fruit_vegetable_servings_day": ("Fruit & vegetables", "servings/day", "fruit and vegetable intake risk inflammatory bowel disease"),
    "sugary_drinks_times_week": ("Sugary drinks", "times/week", "sugar-sweetened beverages soft drinks risk inflammatory bowel disease"),
    "red_processed_meat_times_week": ("Red / processed meat", "times/week", "red meat processed meat intake inflammatory bowel disease risk"),
    "fermented_food_times_week": ("Fermented food", "times/week", "fermented foods probiotics gut microbiota inflammation"),
    "fish_times_week": ("Fish", "times/week", "fish omega-3 fatty acids intake inflammatory bowel disease risk"),
    "dates_times_week": ("Dates", "times/week", "polyphenol fruit fiber gut microbiota short chain fatty acids"),
    "fried_food_times_week": ("Fried food", "times/week", "fried food dietary fat intake inflammatory bowel disease"),
    # Lifestyle
    "physical_activity_min_week": ("Physical activity", "min/week", "physical activity exercise risk of inflammatory bowel disease"),
    "sedentary_hours_day": ("Sedentary time", "h/day", "sedentary behavior risk of inflammatory bowel disease"),
    "sleep_hours": ("Sleep duration", "h/night", "sleep duration and inflammatory bowel disease"),
    "sleep_quality": ("Sleep quality", "", "poor sleep quality inflammatory bowel disease activity"),
    "stress_level": ("Stress level", "", "psychological stress inflammatory bowel disease onset and flares"),
    "smoking": ("Smoking", "", "smoking tobacco risk of Crohn's disease"),
    "vaping": ("Vaping", "", "tobacco smoke exposure e-cigarette inflammatory bowel disease"),
    # Medication and antibiotics
    "antibiotic_courses_year": ("Antibiotic courses", "per year", "antibiotic exposure number of courses risk of inflammatory bowel disease"),
    "antibiotic_use_past_3_months": ("Antibiotics in past 3 months", "", "recent antibiotic use risk of inflammatory bowel disease"),
    "broad_spectrum_antibiotic": ("Broad-spectrum antibiotic", "", "broad-spectrum antibiotics dysbiosis inflammatory bowel disease risk"),
    "NSAID_use_times_month": ("NSAID use", "times/month", "NSAID use risk of inflammatory bowel disease"),
    "PPI_use": ("Proton-pump inhibitor use", "", "proton pump inhibitor use gut microbiome inflammatory bowel disease"),
    "childhood_antibiotic_exposure": ("Childhood antibiotic exposure", "", "childhood exposure to antibiotics and risk of inflammatory bowel disease"),
    # Birth mode and early life
    "birth_mode": ("Birth mode", "", "cesarean section delivery risk of inflammatory bowel disease"),
    "breastfeeding_months": ("Breastfeeding", "months", "breastfeeding duration protective inflammatory bowel disease"),
    "childhood_GI_infection": ("Childhood GI infection", "", "gastrointestinal infection gastroenteritis risk inflammatory bowel disease"),
    "childhood_infection_count": ("Childhood infections", "count", "childhood infections hospitalisation risk inflammatory bowel disease"),
    # Microbiome diversity
    "alpha_diversity_Shannon": ("Microbial diversity (Shannon)", "", "reduced gut microbial alpha diversity inflammatory bowel disease"),
    "butyrate_producer_abundance_pct": ("Butyrate producers", "%", "butyrate-producing bacteria depletion inflammatory bowel disease"),
    "Faecalibacterium_abundance_pct": ("Faecalibacterium", "%", "Faecalibacterium prausnitzii reduced in Crohn's disease"),
    "Roseburia_abundance_pct": ("Roseburia", "%", "Roseburia abundance inflammatory bowel disease"),
    "Bacteroides_abundance_pct": ("Bacteroides", "%", "Bacteroides abundance inflammatory bowel disease microbiome"),
    "Proteobacteria_abundance_pct": ("Proteobacteria", "%", "Proteobacteria Enterobacteriaceae expansion dysbiosis inflammatory bowel disease"),
    "Firmicutes_Bacteroidetes_ratio": ("Firmicutes/Bacteroidetes ratio", "", "Firmicutes Bacteroidetes ratio inflammatory bowel disease"),
    # Inflammatory biomarkers
    "fecal_calprotectin_ug_g": ("Fecal calprotectin", "µg/g", "fecal calprotectin diagnostic accuracy inflammatory bowel disease"),
    "CRP_mg_L": ("CRP", "mg/L", "C-reactive protein serum biomarker inflammatory bowel disease"),
    "vitamin_D_ng_mL": ("Vitamin D", "ng/mL", "vitamin D deficiency risk of inflammatory bowel disease"),
    "anemia_status": ("Anaemia", "", "anaemia iron deficiency inflammatory bowel disease"),
    "hemoglobin_g_dL": ("Haemoglobin level", "g/dL", "haemoglobin anaemia inflammatory bowel disease diagnosis"),
    "WBC_10e9_L": ("WBC (white blood cell count)", "×10⁹/L", "white blood cell count leukocytosis inflammatory bowel disease"),
    "platelet_count_10e9_L": ("Platelet count", "×10⁹/L", "thrombocytosis platelet count inflammatory bowel disease activity"),
    "MCV_fL": ("MCV (mean corpuscular volume)", "fL", "mean corpuscular volume microcytosis iron deficiency inflammatory bowel disease"),
    "ESR_mm_h": ("ESR (erythrocyte sedimentation rate)", "mm/h", "erythrocyte sedimentation rate inflammatory markers inflammatory bowel disease"),
    # Metabolism related biomarkers
    "serum_butyrate_umol_L": ("Serum butyrate", "µmol/L", "butyrate short chain fatty acids reduced in inflammatory bowel disease"),
    "fecal_butyrate_umol_g": ("Fecal butyrate", "µmol/g", "faecal short chain fatty acids butyrate inflammatory bowel disease metabolomics"),
    "primary_to_secondary_bile_acid_ratio": ("Primary:secondary bile acids", "ratio", "primary secondary bile acids ratio inflammatory bowel disease"),
    "tryptophan_ug_mL": ("Tryptophan", "µg/mL", "tryptophan metabolism reduced inflammatory bowel disease"),
    "indole_3_acetic_acid_ug_mL": ("Indole-3-acetic acid", "µg/mL", "indole tryptophan metabolites microbiota inflammatory bowel disease"),
    "palmitic_acid_ug_mL": ("Palmitic acid", "µg/mL", "palmitic acid fatty acids inflammatory bowel disease"),
    "myristic_acid_ug_mL": ("Myristic acid", "µg/mL", "myristic acid fatty acid metabolomics Crohn's disease"),
    "arachidonic_acid_ug_mL": ("Arachidonic acid", "µg/mL", "arachidonic acid metabolomics inflammatory bowel disease"),
    "histidine_ug_mL": ("Histidine", "µg/mL", "histidine amino acid metabolomics inflammatory bowel disease"),
    "total_triglycerides_mg_dL": ("Triglycerides", "mg/dL", "serum lipids triglycerides inflammatory bowel disease"),
    # Red flags
    "perianal_fistula_history": ("Perianal fistula / abscess", "", "perianal fistula first manifestation of Crohn's disease"),
    "recurrent_aphthous_ulcers": ("Recurrent mouth ulcers", "", "oral aphthous ulcers extraintestinal manifestation inflammatory bowel disease"),
    "erythema_nodosum_history": ("Erythema nodosum", "", "erythema nodosum extraintestinal manifestation inflammatory bowel disease"),
    "pyoderma_gangrenosum_history": ("Pyoderma gangrenosum", "", "pyoderma gangrenosum presenting symptom inflammatory bowel disease"),
    "hidradenitis_suppurativa_history": ("Hidradenitis suppurativa", "", "hidradenitis suppurativa association Crohn's disease"),
    "PSC_or_elevated_LFTs": ("PSC / elevated liver enzymes", "", "primary sclerosing cholangitis inflammatory bowel disease"),
    "unprovoked_VTE_history": ("Unprovoked VTE", "", "venous thromboembolism inflammatory bowel disease"),
    "appendectomy_history": ("Appendectomy", "", "appendectomy and risk of inflammatory bowel disease"),
    "tonsillectomy_history": ("Tonsillectomy", "", "tonsillectomy risk inflammatory bowel disease"),
}

GROUP_LABELS = {
    "Demographic data": "Demographics",
    "Signs and symptoms": "Signs and symptoms",
    "Family history": "Family history of IBD",
    "Diet": "Dietary pattern",
    "Lifestyle": "Lifestyle",
    "Medication and antibiotics": "Antibiotic & medication exposure",
    "Birth mode and early life": "Birth mode & early life",
    "Microbiome diversity": "Gut dysbiosis profile",
    "Inflammatory biomarkers": "Inflammatory biomarkers",
    "Metabolism related biomarkers": "Metabolic biomarkers",
    "Red flags": "Extra-intestinal red flags",
}


def label(feature):
    return FEATURE_INFO.get(feature, (feature,))[0]


def unit(feature):
    return FEATURE_INFO.get(feature, ("", "", ""))[1]


def query(feature):
    return FEATURE_INFO.get(feature, ("", "", f"{feature} inflammatory bowel disease"))[2]
