"""Build real-data microbiome reference ranges from the IBDMDB HMP2 metagenomics cohort.

Writes artifacts/microbiome_reference.json (read by the web app) and
artifacts/microbiome_realdata_report.md. Downloads go to the git-ignored data/ibdmdb/.
The risk model is not touched: these ranges are for display only and feed no prediction.

Run from the repository root:  python scripts/build_microbiome_reference.py
"""
import gzip
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from features import GROUPS, load_raw  # noqa: E402

DATA_DIR = ROOT / "data" / "ibdmdb"
OUT_JSON = ROOT / "artifacts" / "microbiome_reference.json"
OUT_REPORT = ROOT / "artifacts" / "microbiome_realdata_report.md"

GLOBUS = "https://g-227ca.190ebd.75bc.data.globus.org/ibdmdb"
SOURCES = {
    "taxonomy": ("taxonomic_profiles.tsv.gz", f"{GLOBUS}/products/HMP2/MGX/2018-05-04/taxonomic_profiles.tsv.gz",
                 "Bacteria abundances for each stool sample (MetaPhlAn2, the published analysis version)"),
    "metadata": ("hmp2_metadata_2018-08-20.csv", f"{GLOBUS}/metadata/hmp2_metadata_2018-08-20.csv",
                 "Sample, person and diagnosis records"),
    "dysbiosis": ("dysbiosis_scores.tsv", "https://forum.biobakery.org/uploads/short-url/umwfR0kDJ6s5RXHwtIMgLaOEoOI.tsv",
                  "Dysbiosis score per sample; reported as context, never compared with a patient"),
    "provenance": ("anadama_run.log.gz", f"{GLOBUS}/metadata/anadama_run.log.gz",
                   "Processing log; recorded as a source and not parsed"),
}

EXPECTED_PEOPLE = {"nonIBD": 27, "CD": 65, "UC": 38}
GROUP_LABELS = {"nonIBD": "Non-IBD controls", "CD": "Crohn's disease", "UC": "Ulcerative colitis"}
PERCENTILES = (5, 25, 50, 75, 95)
# Our own working definition, not a published list. Eubacterium is a mixed genus.
BUTYRATE_GENERA = ("Faecalibacterium", "Roseburia", "Eubacterium", "Coprococcus", "Butyricicoccus",
                   "Anaerostipes", "Subdoligranulum")
MICROBIOME = GROUPS["Microbiome diversity"]
UNITS = {f: "%" for f in MICROBIOME}
UNITS.update({"alpha_diversity_Shannon": "index", "Firmicutes_Bacteroidetes_ratio": "ratio"})


def fetch(key):
    name, url, _ = SOURCES[key]
    path = DATA_DIR / name
    if not path.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "IBD-Care-reference-build/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response:
            path.write_bytes(response.read())
    return path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clade(table, name):
    rows = table[table.index.str.endswith(f"|{name}")]
    if len(rows) != 1:
        raise SystemExit(f"Expected exactly one row for {name}, found {len(rows)}.")
    return rows.iloc[0]


def sample_values(table):
    """The 7 model microbiome inputs for each sample, on the same scale as the app's inputs."""
    phyla = table[table.index.str.match(r"^k__Bacteria\|p__[^|]+$")].sum()
    scale_check = float(phyla.median())
    if 90 <= scale_check <= 101:
        to_percent = 1.0
    elif 0.9 <= scale_check <= 1.01:
        to_percent = 100.0
    else:
        raise SystemExit(f"Unexpected abundance scale: median bacterial total {scale_check}.")
    species = table[table.index.str.contains(r"\|s__") & ~table.index.str.contains(r"\|t__")].T
    totals = species.sum(axis=1)
    usable = totals[totals > 0].index
    shares = species.loc[usable].div(totals[usable], axis=0)
    firmicutes, bacteroidetes = clade(table, "p__Firmicutes"), clade(table, "p__Bacteroidetes")
    values = pd.DataFrame({
        "alpha_diversity_Shannon": -(shares * np.log(shares.where(shares > 0))).sum(axis=1),
        "butyrate_producer_abundance_pct": sum(clade(table, f"g__{g}") for g in BUTYRATE_GENERA) * to_percent,
        "Faecalibacterium_abundance_pct": clade(table, "g__Faecalibacterium") * to_percent,
        "Roseburia_abundance_pct": clade(table, "g__Roseburia") * to_percent,
        "Bacteroides_abundance_pct": clade(table, "g__Bacteroides") * to_percent,
        "Proteobacteria_abundance_pct": clade(table, "p__Proteobacteria") * to_percent,
        "Firmicutes_Bacteroidetes_ratio": firmicutes / bacteroidetes.where(bacteroidetes > 0),
    })
    return values.loc[usable, MICROBIOME], scale_check, len(table.columns) - len(usable)


def percentile_table(people):
    """Percentiles for each input and group, from one median value per person."""
    features = {}
    for feature in MICROBIOME:
        groups = {}
        for group in GROUP_LABELS:
            values = people.loc[people.diagnosis == group, feature].dropna()
            points = [round(float(v), 3) for v in np.percentile(values, PERCENTILES)]
            if points != sorted(points):
                raise SystemExit(f"Percentiles out of order for {feature} / {group}.")
            groups[group] = {"people": int(len(values)), **{f"p{p}": v for p, v in zip(PERCENTILES, points)}}
        features[feature] = {"unit": UNITS[feature], "groups": groups}
    return features


def dysbiosis_summary(path, samples):
    scores = pd.read_csv(path, sep="\t", header=None, names=["sample", "score", "flag"]).set_index("sample")
    if scores.index.has_duplicates:
        raise SystemExit("Duplicate samples in the dysbiosis file.")
    joined = scores.join(samples[["Participant ID", "diagnosis"]], how="inner")
    summary = {}
    for group in GROUP_LABELS:
        rows = joined[joined.diagnosis == group]
        summary[group] = {"samples": int(len(rows)), "people": int(rows["Participant ID"].nunique()),
                          "median_score": round(float(rows.score.median()), 3),
                          "flagged_pct": round(100 * float(rows.flag.mean()), 1)}
    return summary, int(len(scores)), int(len(joined))


def log_inputs(frame):
    logged = frame.copy()
    for column in logged.columns:
        if column != "alpha_diversity_Shannon":
            logged[column] = np.log10(logged[column] + 1e-4)
    return logged


def logistic():
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, class_weight="balanced"))


def forest():
    return RandomForestClassifier(500, min_samples_leaf=3, class_weight="balanced", n_jobs=-1, random_state=42)


def grouped_auc(model, features, target, people):
    splitter = StratifiedGroupKFold(5, shuffle=True, random_state=42)
    predicted = cross_val_predict(model, features, target, cv=splitter, groups=people, method="predict_proba")[:, 1]
    return float(roc_auc_score(target, predicted))


def signal_checks(values, samples, metadata, species):
    """How much the 7 inputs can tell, with each person kept on one side of every split."""
    complete = values.join(samples[["Participant ID", "diagnosis", "week_num", "consent_age"]], how="inner")
    complete["Firmicutes_Bacteroidetes_ratio"] = complete["Firmicutes_Bacteroidetes_ratio"].fillna(
        complete["Firmicutes_Bacteroidetes_ratio"].max())
    target = (complete.diagnosis != "nonIBD").astype(int).values
    people = complete["Participant ID"].values
    logged = log_inputs(complete[MICROBIOME])
    checks = {
        "samples": len(complete), "ibd_sample_share": float(target.mean()),
        "logistic_auc": grouped_auc(logistic(), logged, target, people),
        "forest_auc": grouped_auc(forest(), complete[MICROBIOME], target, people),
    }
    prevalent = np.log10(species.reindex(complete.index).loc[:, (species > 0).mean() > 0.1] + 1e-5)
    careless = cross_val_predict(forest(), prevalent, target, method="predict_proba",
                                 cv=StratifiedKFold(5, shuffle=True, random_state=42))[:, 1]
    checks["careless_species_auc"] = float(roc_auc_score(target, careless))
    checks["grouped_species_auc"] = grouped_auc(forest(), prevalent, target, people)

    age = complete.consent_age.between(15, 30).values
    checks["age_15_30_nonibd_people"] = int(complete.loc[age & (target == 0), "Participant ID"].nunique())
    checks["age_15_30_auc"] = grouped_auc(logistic(), logged[age], target[age], people[age])

    visits = metadata[["Participant ID", "week_num", "diagnosis", "hbi", "sccai"]].dropna(subset=["week_num"]).copy()
    visits["active"] = np.nan
    crohns, colitis = (visits.diagnosis == "CD") & visits.hbi.notna(), (visits.diagnosis == "UC") & visits.sccai.notna()
    visits.loc[crohns, "active"] = (visits.loc[crohns, "hbi"] >= 5).astype(float)
    visits.loc[colitis, "active"] = (visits.loc[colitis, "sccai"] >= 3).astype(float)
    per_visit = (visits.dropna(subset=["active"]).groupby(["Participant ID", "week_num"]).active.max()
                 .reset_index().sort_values(["Participant ID", "week_num"]))
    per_visit["next_active"] = per_visit.groupby("Participant ID").active.shift(-1)
    pairs = complete.reset_index().merge(per_visit, on=["Participant ID", "week_num"]).dropna(subset=["next_active"])
    pairs = pairs[pairs.active == 0]
    checks["next_visit_samples"] = len(pairs)
    checks["next_visit_people"] = int(pairs["Participant ID"].nunique())
    checks["next_visit_events"] = int(pairs.next_active.sum())
    checks["next_visit_auc"] = grouped_auc(logistic(), log_inputs(pairs[MICROBIOME]), pairs.next_active.astype(int).values,
                                           pairs["Participant ID"].values)
    return checks


def synthetic_comparison(features):
    """How the synthetic training data sits against the real ranges, per input."""
    raw = load_raw()
    for feature, entry in features.items():
        low = min(g["p5"] for g in entry["groups"].values())
        high = max(g["p95"] for g in entry["groups"].values())
        values = raw[feature].dropna()
        entry["synthetic_median"] = round(float(values.median()), 3)
        entry["synthetic_outside_pct"] = round(100 * float(((values < low) | (values > high)).mean()), 1)


def write_report(reference):
    checks = reference["signal"]
    people = reference["cohort"]["people"]
    total = sum(people.values())
    ibd = people["CD"] + people["UC"]
    age = reference["cohort"]["age_range"]
    range_rows = []
    for feature, entry in reference["features"].items():
        cells = [f"{entry['groups'][g]['p50']} ({entry['groups'][g]['p5']}–{entry['groups'][g]['p95']})"
                 for g in GROUP_LABELS]
        range_rows.append(f"| `{feature}` | {' | '.join(cells)} | {entry['synthetic_median']:.2f} | {entry['synthetic_outside_pct']:.0f}% |")
    dysbiosis_rows = [f"| {GROUP_LABELS[g]} | {d['samples']} | {d['people']} | {d['median_score']} | {d['flagged_pct']}% |"
                      for g, d in reference["dysbiosis"]["groups"].items()]
    source_rows = [f"| {s['role']} | {s['url']} | `{s['sha256'][:16]}…` |" for s in reference["sources"]]
    text = f"""# IBDMDB real-data microbiome report

Generated by `scripts/build_microbiome_reference.py`. Every number below is computed from the source files.

## What this is for

The app shows these ranges next to a patient's microbiome inputs, for context only. They do not change the risk
estimate. The 61-input model is not retrained on this data.

## Cohort

HMP2 metagenomics: {reference['cohort']['samples']} stool samples from {total} people
({people['nonIBD']} non-IBD, {people['CD']} Crohn's disease, {people['UC']} ulcerative colitis).
By person, {100 * ibd / total:.0f}% have IBD; by sample, {100 * checks['ibd_sample_share']:.0f}%.
Earlier notes gave "74% IBD" for the 130 people: that was the share of samples, not people.

## Reference ranges

Median (5th–95th percentile), calculated from one median value per person so that people who gave more samples do not
count more. The last two columns compare the synthetic training data: its median, and the share of synthetic patients
outside the 5th–95th range of all three real groups.

| Input | Non-IBD | Crohn's disease | Ulcerative colitis | Synthetic median | Synthetic outside |
|---|---|---|---|---|---|
{chr(10).join(range_rows)}

The synthetic data does not match this real cohort on several inputs. The model was trained on the synthetic scale, so
a value it treats as ordinary may look unusual here, and the reverse. This is a known limit of the demonstration, and
the model has not been changed.

## How much the 7 inputs can tell

All results keep each person on one side of every split, unless stated.

| Question | Result |
|---|---|
| IBD vs non-IBD, 7 inputs, logistic regression | AUC {checks['logistic_auc']:.2f} |
| IBD vs non-IBD, 7 inputs, random forest | AUC {checks['forest_auc']:.2f} |
| IBD vs non-IBD, ages 15–30, 7 inputs, logistic regression | AUC {checks['age_15_30_auc']:.2f} (only {checks['age_15_30_nonibd_people']} non-IBD people) |
| Active disease at next visit, from a remission-visit sample | AUC {checks['next_visit_auc']:.2f} ({checks['next_visit_events']} events, {checks['next_visit_samples']} samples, {checks['next_visit_people']} people) |
| IBD vs non-IBD, all common species, people kept separate | AUC {checks['grouped_species_auc']:.2f} |
| **Careless:** same model, samples split at random | AUC {checks['careless_species_auc']:.3f} |

The careless result is false. The same person's samples land in both training and test data, so the model recognises
people instead of disease. It must never be quoted as performance. Active disease means HBI ≥ 5 (Crohn's) or
SCCAI ≥ 3 (ulcerative colitis). These are single first-pass cross-validation runs, without confidence intervals.

## Dysbiosis scores

Context only. Patients have no comparable score, so the app never places a patient on this scale.
The file has no header; the third column is read as a dysbiosis flag.

| Group | Samples | People | Median score | Flagged samples |
|---|---|---|---|---|
{chr(10).join(dysbiosis_rows)}

## Limitations

- **Small control group:** only {people['nonIBD']} non-IBD people, so each 5th or 95th percentile rests on one or two people.
- **Not clinical reference ranges:** these describe one research cohort. They do not define normal.
- **Population:** a US cohort aged {age[0]:.0f}–{age[1]:.0f} at consent, not Saudi patients.
- **"Non-IBD" controls:** these people had a colonoscopy for screening or non-specific symptoms and were not diagnosed
  with IBD. They are not a general healthy population.
- **Different origin:** patient values in this app are synthetic and may not be on the same scale as these measurements.
  Shannon diversity depends on the method; here it is calculated from MetaPhlAn2 species.
- **Butyrate producers:** the genus list ({', '.join(BUTYRATE_GENERA)}) is our own working definition.
  *Eubacterium* is a mixed genus, so this total is approximate.
- **Treatment and timing:** a person's median combines every visit, including flares and antibiotic use.
- **No progression data:** each person has one diagnosis throughout, so the cohort cannot show anyone moving from
  pre-IBD to IBD.
- **Data use:** the IBDMDB results and downloads pages state no terms. The repository holds derived percentiles only,
  not the downloaded files. Confirm the terms before any publication.

## Sources

Lloyd-Price J, et al. Multi-omics of the gut microbial ecosystem in inflammatory bowel diseases. *Nature* 2019;569:655–662.

| File | URL | SHA-256 |
|---|---|---|
{chr(10).join(source_rows)}
"""
    OUT_REPORT.write_text(text, encoding="utf-8")


def main():
    paths = {key: fetch(key) for key in SOURCES}
    metadata = pd.read_csv(paths["metadata"], low_memory=False)
    with gzip.open(paths["taxonomy"], "rt") as handle:
        table = pd.read_csv(handle, sep="\t", index_col=0)

    samples = metadata[metadata.data_type == "metagenomics"].drop_duplicates("External ID").set_index("External ID")
    values, scale_check, empty_samples = sample_values(table)
    joined = values.join(samples[["Participant ID", "diagnosis"]], how="inner")
    if joined.groupby("Participant ID").diagnosis.nunique().max() != 1:
        raise SystemExit("A person has more than one diagnosis.")

    person_medians = joined.groupby("Participant ID")[MICROBIOME].median()
    person_medians["diagnosis"] = joined.groupby("Participant ID").diagnosis.first()
    counts = {g: int((person_medians.diagnosis == g).sum()) for g in GROUP_LABELS}
    if counts != EXPECTED_PEOPLE:
        raise SystemExit(f"Cohort does not match the metadata: {counts} vs {EXPECTED_PEOPLE}.")

    joined_age = samples.loc[joined.index, "consent_age"].dropna()
    summary, dysbiosis_rows, dysbiosis_matched = dysbiosis_summary(paths["dysbiosis"], samples)
    reference = {
        "source": "IBDMDB HMP2 metagenomics (Lloyd-Price et al., Nature 2019)",
        "group_labels": GROUP_LABELS,
        "percentiles": list(PERCENTILES),
        "cohort": {"samples": len(joined), "people": counts, "samples_without_species_data": empty_samples,
                   "abundance_scale_check": round(scale_check, 3),
                   "age_range": [float(joined_age.min()), float(joined_age.max())],
                   "samples_without_ratio": int(joined["Firmicutes_Bacteroidetes_ratio"].isna().sum())},
        "butyrate_genera": list(BUTYRATE_GENERA),
        "features": percentile_table(person_medians),
        "dysbiosis": {"rows": dysbiosis_rows, "matched_to_metadata": dysbiosis_matched, "groups": summary},
        "sources": [{"role": role, "file": name, "url": url, "sha256": sha256(paths[key])}
                    for key, (name, url, role) in SOURCES.items()],
    }
    synthetic_comparison(reference["features"])
    species = table[table.index.str.contains(r"\|s__") & ~table.index.str.contains(r"\|t__")].T
    checks = signal_checks(values, samples, metadata, species)
    reference["signal"] = {k: round(v, 3) if isinstance(v, float) else v for k, v in checks.items()}
    OUT_JSON.write_text(json.dumps(reference, indent=1) + "\n", encoding="utf-8")
    write_report(reference)
    print(json.dumps({"cohort": reference["cohort"], "signal": reference["signal"]}, indent=1))
    print(f"Wrote {OUT_JSON.relative_to(ROOT)} and {OUT_REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
