<div align="center">

IBD Care

Inflammatory Bowel Disease Risk Assessment & Clinical Decision Support

A nurse-focused clinical decision-support prototype that combines interpretable machine learning, patient-level explanations, and evidence-grounded research retrieval in one clinical workflow.

<br>





<br>

Hackathon ID: NH-74   |   Demo User: nurse   |   Password: nurse-demo26

</div>

Project at a Glance





Project Type

Clinical decision-support prototype

Primary User

Nurses / clinical care teams

Clinical Focus

Early IBD risk assessment

Dataset

2,500 synthetic patient records

Model Inputs

61 structured clinical, lifestyle, microbiome and biomarker features

Selected Model

Sparse Logistic Regression (L1)

Explainability

Patient-level SHAP explanations

Evidence Engine

Hybrid RAG using BGE embeddings + BM25 + RRF

Research Corpus

67 papers / 2,280 indexed passages

Web App

Django

Deployment

Render

Quick Access











Why IBD Care?

IBD risk assessment may involve information from several domains at once: demographics, family history, lifestyle, medication exposure, inflammatory markers, microbiome characteristics, metabolic biomarkers and clinical red flags.

IBD Care brings these signals together into one nurse-focused workflow that helps answer:

Clinical Question

IBD Care Response

What is the patient's estimated IBD risk?

ML-generated probability and Low / Moderate / High risk level

Why did the model estimate this risk?

Patient-specific contributing factors

What changed from the previous assessment?

Risk-over-time comparison

What evidence supports the finding?

Retrieved literature linked to relevant findings

What should be reviewed next?

Clinical next-step guidance and report-ready assessment

Clinical Safety Notice
IBD Care is a demonstration prototype using synthetic data. It is not validated for clinical use, does not provide a diagnosis, and must not be used independently to guide treatment.

System Architecture

%%{init: {
  "theme": "base",
  "themeVariables": {
    "primaryColor": "#E8F1F3",
    "primaryTextColor": "#183747",
    "primaryBorderColor": "#72AEB8",
    "lineColor": "#796382",
    "secondaryColor": "#F1EDF3",
    "tertiaryColor": "#EBF2ED",
    "fontFamily": "Segoe UI, Arial, sans-serif"
  }
}}%%
flowchart LR
    USER["Nurse / Clinical User"] --> WEB["Django Clinical Workspace"]

    subgraph CLINICAL["Clinical Application"]
        WEB --> PATIENT["Patient Record"]
        PATIENT --> ASSESS["61-Input Assessment"]
        WEB --> HISTORY["Assessment History"]
        WEB --> EVIDENCE["Evidence Library"]
    end

    subgraph MODEL["Risk Estimation"]
        ASSESS --> ENCODE["Validation + Encoding"]
        ENCODE --> LR["Sparse Logistic Regression (L1)"]
        LR --> RISK["Risk Probability + Tier"]
        LR --> EXPLAIN["SHAP Explanation"]
        EXPLAIN --> FACTORS["Top Contributing Factors"]
    end

    subgraph RAG["Evidence Pipeline"]
        EVIDENCE --> QUERY["Clinical Query"]
        QUERY --> DENSE["BGE Dense Retrieval"]
        QUERY --> SPARSE["BM25 Retrieval"]
        DENSE --> FUSION["RRF Fusion"]
        SPARSE --> FUSION
        FUSION --> PASSAGES["Research Passages + Metadata"]
        PASSAGES --> MODE{"Claude API available?"}
        MODE -->|Yes| CLAUDE["Grounded Summary + Citations"]
        MODE -->|No| OFFLINE["Retrieval-Only Evidence"]
    end

    subgraph STORAGE["Data & Artifacts"]
        DB[("SQLite / Django ORM")]
        MODELFILE["model.joblib"]
        PAPERS["67 Research Papers"]
        INDEX["2,280 Indexed Passages"]
    end

    PATIENT <--> DB
    HISTORY <--> DB
    LR <--> MODELFILE
    PAPERS --> INDEX
    INDEX --> DENSE
    INDEX --> SPARSE

    RISK --> REPORT["Unified Clinical Assessment"]
    FACTORS --> REPORT
    CLAUDE --> REPORT
    OFFLINE --> REPORT
    REPORT --> USER

    classDef clinical fill:#E8F1F3,stroke:#72AEB8,color:#183747,stroke-width:1.5px;
    classDef model fill:#EBF2ED,stroke:#456C5B,color:#183747,stroke-width:1.5px;
    classDef rag fill:#F1EDF3,stroke:#796382,color:#183747,stroke-width:1.5px;
    classDef result fill:#F7EAE6,stroke:#A14337,color:#183747,stroke-width:1.5px;

    class WEB,PATIENT,ASSESS,HISTORY clinical;
    class ENCODE,LR,RISK,EXPLAIN,FACTORS model;
    class EVIDENCE,QUERY,DENSE,SPARSE,FUSION,PASSAGES,MODE,CLAUDE,OFFLINE rag;
    class REPORT result;

Clinical Workflow

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#E8F1F3","primaryBorderColor":"#72AEB8","lineColor":"#796382","primaryTextColor":"#183747"}}}%%
flowchart LR
    A["Open Patient Record"] --> B["Review Clinical Snapshot"]
    B --> C["Run IBD Risk Assessment"]
    C --> D["Review Estimated Risk"]
    D --> E["Review Contributing Factors"]
    E --> F["Open Supporting Evidence"]
    F --> G["Clinical Review"]
    G --> H["Print / Save Assessment"]

The system intentionally places clinical review after model output. The AI supports decision-making; it does not replace clinical judgment.

Machine Learning

<details open>
<summary><b>Dataset & Feature Design</b></summary>

<br>

The prototype uses Saudi_IBD_Synthetic.xlsx.

Dataset Property

Value

Patient records

2,500

Model inputs

61

Feature groups

10

Synthetic IBD prevalence

24.7%

Train / test split

80 / 20

Held-out test set

500 records

Random seed

42

Feature Groups

Group

Examples

Demographics

Age, sex, BMI

Family history

First-degree IBD history

Diet

Fiber intake, fast food, ultra-processed food

Lifestyle

Stress, sleep, physical activity, smoking

Medication

Antibiotics, PPI, NSAIDs

Early life

Birth mode, breastfeeding

Microbiome

Shannon diversity, Faecalibacterium, Proteobacteria

Inflammatory biomarkers

Fecal calprotectin, CRP, vitamin D

Metabolic biomarkers

Butyrate, tryptophan-related markers

Red flags

Clinical and surgical flags

Leakage Prevention

The model excludes identifiers and synthetic composite scores that could leak the target, including:

patient ID;

target label;

synthetic risk probability;

composite dysbiosis score;

microbial risk score;

metabolomic risk score.

</details>

<details>
<summary><b>Model Selection</b></summary>

<br>

Candidate models evaluated:

Model

Role

Logistic Regression (L2)

Linear baseline

Sparse Logistic Regression (L1)

Selected final model

Logistic Regression + splines

Non-linear linear-model variant

Random Forest

Tree ensemble

HistGradientBoosting

Gradient boosting

Ensemble

Combined candidate

Model selection uses nested 5-fold cross-validation with PR-AUC as the primary tuning metric.

Selected Model

Sparse Logistic Regression (L1)

C = 0.3

It was selected because it combined strong predictive performance with transparency and sparse feature weighting, making it suitable for a clinical decision-support prototype.

</details>

<details>
<summary><b>Risk Decision Logic</b></summary>

<br>

Classification threshold = 0.454

Risk tiers:

Risk Level

Probability

Low

< 0.20

Moderate

0.20 – < 0.50

High

≥ 0.50

The interface presents these values as estimated risk, not diagnosis.

</details>

Model Evaluation

These results measure recovery of patterns in the synthetic dataset. They must not be interpreted as validated clinical diagnostic performance.

Metric

Held-Out Result

ROC-AUC

0.972

PR-AUC

0.925

Precision

0.800

Recall / Sensitivity

0.806

Specificity

0.934

Accuracy

0.902

F1

0.803

NPV

0.936

Brier Score

0.059

Explainability



The selected linear model is paired with patient-level explanation logic.

Instead of exposing raw SHAP values to nurses, the interface translates model contributions into two clinically readable groups:

Direction

Interface Meaning

Increasing estimated risk

Recorded factors that pushed the model estimate upward

Reducing estimated risk

Recorded factors that pushed the model estimate downward

Examples of high-impact model features in the synthetic prototype include:

fecal calprotectin · fecal butyrate · Shannon diversity · antibiotic courses · fiber intake · Proteobacteria abundance · fast-food frequency

These values explain model behavior, not biological causality.

Evidence-Grounded RAG

<details open>
<summary><b>Research Retrieval Architecture</b></summary>

<br>

%%{init: {"theme":"base","themeVariables":{"primaryColor":"#F1EDF3","primaryBorderColor":"#796382","lineColor":"#72AEB8","primaryTextColor":"#183747"}}}%%
flowchart LR
    PDF["67 Full-Text Papers"] --> EXTRACT["PyMuPDF Extraction"]
    EXTRACT --> CHUNKS["2,280 Passages"]
    CHUNKS --> EMBED["BGE-small Embeddings"]
    CHUNKS --> BM["BM25 Index"]
    EMBED --> RRF["Reciprocal Rank Fusion"]
    BM --> RRF
    RRF --> TOP["Top Evidence Passages"]
    TOP --> C{"Claude configured?"}
    C -->|Yes| SUM["Grounded Summary + Citations"]
    C -->|No| RET["Retrieval-Only Evidence"]

Chunking

Setting

Value

Chunk size

300 words

Overlap

60 words

Minimum chunk

40 words

Metadata retained

paper title · year · DOI · page number · PDF filename

</details>

<details>
<summary><b>Hybrid Retrieval</b></summary>

<br>

Dense retrieval



Used for semantic similarity.

Sparse retrieval



Used for exact biomedical terminology and biomarker names.

Fusion



Dense and sparse rankings are merged using Reciprocal Rank Fusion.

</details>

<details>
<summary><b>Claude Integration</b></summary>

<br>

When ANTHROPIC_API_KEY is configured, the top retrieved passages are sent to Claude for grounded evidence summaries.

Claude is instructed to:

answer only from retrieved literature;

cite factual claims;

avoid diagnosis;

distinguish research evidence from synthetic model output;

state when evidence is weak or mixed;

write for nurses and clinicians.

Without an API key, the Evidence Library automatically falls back to retrieval-only mode.

</details>

Clinical Application

Screen

Purpose

Overview

Patient count, assessment count, risk distribution and priority review

Patients

Search, filter, add and open patient records

Patient Record

Clinical snapshot, risk history, biomarkers and flags

Assessment

Structured 61-input assessment divided into nurse-friendly sections

Assessment Result

Unified report with risk scale, contributing factors, comparison and evidence

Evidence Library

Search the research corpus

About

Intended use, safety, validation status and transparency

Assessment Form Sections

Patient profile · Clinical history · Lifestyle / diet · Biomarkers · Microbiome · Red flags / surgical history

Human-Centered AI

IBD Care is designed around Human-Centered AI (HCAI) principles.

Principle

Implementation

Human control

Nurses and clinicians retain final judgment

Explainability

Patient-specific contributing factors are visible

Progressive disclosure

Technical detail appears only when needed

Uncertainty awareness

Results are framed as estimated risk

Evidence access

Findings can be linked to supporting literature

Automation-bias reduction

Model estimate, explanation, evidence and clinical interpretation are separated

Safety transparency

Synthetic-data and validation limits remain accessible

Technology Stack

<div align="center">










</div>

Layer

Technology

Language

Python 3.11

Web framework

Django 5.2

Frontend

Django Templates, HTML, CSS, JavaScript

Database

SQLite + Django ORM

Data processing

Pandas, NumPy

Machine learning

scikit-learn

Model persistence

Joblib

Explainability

SHAP

PDF extraction

PyMuPDF

Dense retrieval

FastEmbed

Embedding model

BAAI/bge-small-en-v1.5

Sparse retrieval

BM25 / rank-bm25

Rank fusion

Reciprocal Rank Fusion

Evidence generation

Anthropic Claude

Spreadsheet support

OpenPyXL

Deployment

Render

Project Structure

IBD/
│
├── artifacts/
│   ├── model.joblib
│   ├── model_report.md
│   ├── roc_pr.png
│   ├── calibration.png
│   └── shap_summary.png
│
├── Full text article/
│
├── rag/
│   ├── ingest.py
│   ├── index.py
│   ├── retrieve.py
│   ├── evidence.py
│   └── llm.py
│
├── rag_index/
│   ├── embeddings.npy
│   ├── chunks.jsonl
│   └── docs.json
│
├── webapp/
│   ├── clinic/
│   │   ├── templates/
│   │   ├── static/
│   │   ├── management/
│   │   ├── models.py
│   │   ├── services.py
│   │   └── views.py
│   └── manage.py
│
├── Saudi_IBD_Synthetic.xlsx
├── IBD_Risk_Model.ipynb
├── features.py
├── train.py
├── predict.py
├── explain.py
├── example_patient.json
├── requirements.txt
├── .env.example
└── README.md

Run Locally

<details open>
<summary><b>1. Clone and install</b></summary>

git clone https://github.com/ghaida-alsalamah/IBD.git
cd IBD

python -m venv .venv

Windows PowerShell

.\.venv\Scripts\Activate.ps1

macOS / Linux

source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

</details>

<details open>
<summary><b>2. Prepare Django</b></summary>

cd webapp
python manage.py migrate
python manage.py load_patients --demo-user --password nurse-demo26

</details>

<details>
<summary><b>3. Build the Evidence Index</b></summary>

python manage.py build_index

This extracts the research papers, creates passages, builds BGE embeddings, constructs the BM25 index and saves the hybrid retrieval index.

</details>

<details open>
<summary><b>4. Start the application</b></summary>

python manage.py runserver

Open:

http://127.0.0.1:8000/

Demo login:

Username: nurse
Password: nurse-demo26

</details>

Optional Claude Configuration

Claude is not required for risk prediction.

It is used only for grounded evidence summaries.

ANTHROPIC_API_KEY=your_key_here

Without this key, the application automatically uses retrieval-only evidence mode.

Never commit .env or API keys to GitHub.

Testing & Validation

Validation

Result

Django tests

35 passing

Expanded layout checks

56

Collapsed layout checks

39

Long-page scroll checks

48

PDF output

Reviewed

Run tests:

cd webapp
python manage.py test clinic

Deployment



Live URL:
https://ibd-care-demo.onrender.com

Demo credentials

Username: nurse
Password: nurse-demo26

Responsible AI & Clinical Safety

<details>
<summary><b>Current Prototype Limitations</b></summary>

<br>

Patient data are synthetic.

Model performance is not clinical validation.

SHAP explanations describe model behavior, not biological causality.

The research corpus is curated but not exhaustive.

Retrieval can miss relevant evidence.

Generated evidence summaries require human review.

The system must not independently guide diagnosis or treatment.

</details>

<details>
<summary><b>Requirements Before Real Clinical Use</b></summary>

<br>

validation on representative real Saudi patient data;

prospective clinical evaluation;

clinical governance and regulatory review;

privacy and security assessment;

bias and subgroup evaluation;

calibration and drift monitoring;

approved EHR / clinical workflow integration;

formal nurse usability and human-factors testing.

</details>

Future Work

Direction

Planned Improvement

Clinical validation

Validate on a larger real Saudi cohort

Integration

Connect with hospital / EHR systems

Monitoring

Add calibration and model-drift monitoring

Evidence

Expand microbiome and biomarker literature

Security

Production authentication and audit logging

Persistence

Production-grade persistent database

Usability

Formal nurse usability studies

Longitudinal care

Expand clinical monitoring over time

Hackathon Context





Event

Nursing Innovation Hackathon 2026

Hackathon ID

NH-74

Track

Track 3 — AI-Driven Clinical Decision Support

Project

Machine Learning-Based Prediction of Inflammatory Bowel Disease Risk Using Gut Dysbiosis Biomarkers in Saudi Youth

<div align="center">

IBD Care

Information · Understanding · Care



</div>
