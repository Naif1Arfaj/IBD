<div align="center">

IBD Care

Machine Learning-Based Prediction of Inflammatory Bowel Disease Risk Using Gut Dysbiosis Biomarkers in Saudi Youth

A nurse-focused clinical decision-support prototype combining interpretable machine learning, patient-level explanations, and evidence-grounded research retrieval.

Nursing Innovation Hackathon 2026 · Team NH-74 · Track 3 — AI-Driven Clinical Decision Support

<br>








</div>

[!IMPORTANT]
IBD Care is a demonstration prototype built with synthetic data.
It is not validated for clinical use, does not provide a diagnosis, and must not be used to guide treatment. Model outputs and SHAP explanations reflect relationships in the synthetic data-generation process rather than validated clinical biology.

Overview

IBD Care is a clinical decision-support prototype designed to help nurses review patient information, run an interpretable IBD risk assessment, understand the main factors influencing the estimate, and explore supporting research evidence within one workflow.

Rather than presenting AI as an autonomous decision-maker, the system follows a Human-Centered AI (HCAI) approach:

the nurse remains the final decision-maker;

the system communicates risk, not diagnosis;

patient-level explanations are shown in clinically understandable language;

technical implementation details are kept outside the primary nursing workflow;

supporting literature is available when deeper review is needed;

safety, validation status, and synthetic-data limitations remain transparent.

The Problem

IBD-related risk assessment can involve information from multiple domains: demographics, family history, lifestyle, medication exposure, inflammatory markers, microbiome characteristics, metabolic biomarkers, and clinical red flags.

A useful decision-support system therefore needs to do more than output a classification. It should help clinicians answer:

What is the estimated risk for this patient?

Which recorded factors influenced that estimate?

What evidence is available for the relevant findings?

What should the nurse review next?

How can the result be documented clearly without presenting AI output as a diagnosis?

IBD Care combines these tasks into one clinical workflow.

Key Capabilities

Capability

What it does

Patient workspace

Search, add, and review patient records in a nurse-focused interface

IBD risk assessment

Uses 61 structured inputs to estimate IBD risk

Risk stratification

Presents estimated probability with Low / Moderate / High risk tiers

Explainable AI

Identifies patient-specific factors that increased or reduced the model estimate

Assessment history

Compares saved estimates over time without implying disease progression

Clinical snapshot

Summarizes important recorded biomarkers, family history, antibiotic exposure, and flags

Evidence Library

Searches a curated IBD research collection using hybrid retrieval

Grounded summaries

Optionally uses Claude to synthesize retrieved evidence with citations

Offline evidence mode

Works without an LLM API key by returning retrieved passages and citations

Unified report

The assessment result is immediately printable / saveable as PDF

Human oversight

Keeps clinical judgment and final interpretation with the care team

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
    N["Nurse / Clinical User"] --> UI["Django Clinical Workspace"]

    subgraph APP["Clinical Application"]
        UI --> P["Patient Record"]
        P --> A["61-Input Assessment"]
        UI --> H["Assessment History"]
        UI --> EL["Evidence Library"]
    end

    subgraph ML["Risk Estimation"]
        A --> ENC["Feature Validation & Encoding"]
        ENC --> MODEL["Sparse Logistic Regression (L1)"]
        MODEL --> RISK["Risk Probability + Tier"]
        MODEL --> SHAP["Patient-Level SHAP Explanation"]
        SHAP --> FACTORS["Top Contributing Factors"]
    end

    subgraph RAG["Evidence Pipeline"]
        EL --> QUERY["Clinical / Evidence Query"]
        QUERY --> DENSE["BGE-small Dense Retrieval"]
        QUERY --> BM25["BM25 Keyword Retrieval"]
        DENSE --> RRF["Reciprocal Rank Fusion"]
        BM25 --> RRF
        RRF --> PASSAGES["Top Research Passages + Metadata"]
        PASSAGES --> MODE{"Claude available?"}
        MODE -->|Yes| CLAUDE["Grounded Summary + Citations"]
        MODE -->|No| OFFLINE["Retrieval-Only Evidence + Citations"]
    end

    subgraph DATA["Persistence"]
        DB[("SQLite / Django ORM")]
        LIB["67 Research Papers"]
        IDX["2,280 Indexed Passages"]
        ART["Trained Model Artifact"]
    end

    P <--> DB
    H <--> DB
    MODEL <--> ART
    LIB --> IDX
    IDX --> DENSE
    IDX --> BM25

    RISK --> REPORT["Unified Assessment / Clinical Report"]
    FACTORS --> REPORT
    CLAUDE --> REPORT
    OFFLINE --> REPORT
    REPORT --> N

    classDef clinical fill:#E8F1F3,stroke:#72AEB8,color:#183747,stroke-width:1.5px;
    classDef ml fill:#EBF2ED,stroke:#456C5B,color:#183747,stroke-width:1.5px;
    classDef evidence fill:#F1EDF3,stroke:#796382,color:#183747,stroke-width:1.5px;
    classDef output fill:#F7EAE6,stroke:#A14337,color:#183747,stroke-width:1.5px;

    class UI,P,A,H clinical;
    class ENC,MODEL,RISK,SHAP,FACTORS ml;
    class EL,QUERY,DENSE,BM25,RRF,PASSAGES,MODE,CLAUDE,OFFLINE evidence;
    class REPORT output;

End-to-End Clinical Workflow

Patient record
     ↓
Review clinical snapshot
     ↓
61 structured inputs
     ↓
ML risk estimation
     ↓
Low / Moderate / High estimated risk
     ↓
Patient-specific contributing factors
     ↓
Supporting research evidence
     ↓
Nurse / clinician review
     ↓
Printable assessment report

The system intentionally keeps the human review step after the AI output.

Machine Learning Pipeline

Dataset

The current prototype uses Saudi_IBD_Synthetic.xlsx.

Item

Value

Records

2,500 synthetic patients

Target

synthetic_IBD_outcome

IBD prevalence in synthetic data

24.7%

Model inputs

61 features

Input groups

10

Train / test split

80% / 20%

Held-out test set

500 records

Random seed

42

Input Groups

The 61 model inputs are organized into:

Demographic data

Family history

Diet

Lifestyle

Medication and antibiotics

Birth mode and early life

Microbiome diversity

Inflammatory biomarkers

Metabolism-related biomarkers

Red flags

Examples include fecal calprotectin, CRP, vitamin D, Shannon diversity, Faecalibacterium abundance, Proteobacteria abundance, butyrate-related biomarkers, antibiotic exposure, fiber intake, family history, and clinical flags.

Leakage Prevention

The following fields are explicitly excluded from model inputs:

patient ID;

the target label;

synthetic risk probability;

composite dysbiosis / microbial / metabolomic risk scores;

oral contraceptive use.

This prevents the model from learning directly from synthetic target-generating scores or identifiers.

Model Selection

Multiple candidate models are compared:

Logistic Regression (L2)

Sparse Logistic Regression (L1)

Logistic Regression with spline features

Random Forest

HistGradientBoosting

Ensemble model

Model selection uses nested 5-fold cross-validation on the training set, with PR-AUC as the primary tuning metric.

Selected Model

Sparse Logistic Regression (L1)

Why it was selected:

highest out-of-fold PR-AUC among the evaluated candidates;

strong performance on structured tabular data;

sparse coefficients reduce unnecessary signal;

easier to interpret than more complex black-box alternatives;

supports transparent patient-level explanations.

Final tuned regularization:

C = 0.3

Decision Logic

The classification threshold is selected by maximizing F1 while requiring recall of at least 0.85 on out-of-fold training predictions.

Classification threshold = 0.454

Risk tiers are displayed separately:

Low       < 0.20
Moderate  0.20 – < 0.50
High      ≥ 0.50

The probability and risk tier are presented as estimated model risk, not as a clinical diagnosis.

Model Evaluation

[!WARNING]
These metrics measure how well the model recovers patterns in the synthetic dataset. They must not be interpreted as clinical or diagnostic performance.

Held-Out Test Set

Metric

Result

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

Brier score

0.059

The held-out set contains 500 synthetic records that were not used for model training or hyperparameter tuning.

Explainability

IBD Care uses SHAP-based patient-level explanations.

For the selected linear model, the explanation layer computes exact linear feature contributions relative to a background sample. The system then ranks the most influential recorded factors for the individual assessment.

The clinical interface does not expose raw SHAP values as the main explanation. Instead, it translates them into:

Factors increasing estimated risk

Factors reducing estimated risk

This supports interpretability without presenting model explanations as biological causality.

Examples of high-impact model features

The current synthetic model places strong importance on variables including:

fecal calprotectin;

fecal butyrate;

Shannon diversity;

ultra-processed food frequency;

antibiotic courses;

fiber intake;

Proteobacteria abundance;

serum butyrate;

fast-food frequency;

indole-3-acetic acid.

Again, these rankings describe the synthetic model, not validated clinical importance.

Evidence-Grounded RAG Pipeline

The Evidence Library complements the risk model with research retrieval.

It is intentionally separate from the classifier:

The ML model estimates risk. The RAG pipeline retrieves and summarizes literature.

The language model does not generate the IBD risk score.

Research Corpus

67 full-text research papers
        ↓
PDF extraction
        ↓
2,280 indexed passages

1. PDF Ingestion

PyMuPDF extracts text and document metadata from the research library.

Each document is divided into overlapping chunks:

Chunk size:   300 words
Overlap:       60 words
Minimum:       40 words

Metadata retained for evidence includes:

paper title;

year;

DOI when available;

PDF filename;

source page number.

2. Hybrid Retrieval

IBD Care uses two retrieval strategies in parallel:

Dense semantic retrieval

Embedding model: BAAI/bge-small-en-v1.5

Runtime: FastEmbed

Similarity: cosine similarity

Sparse keyword retrieval

BM25

useful for exact biomedical terminology and biomarker names

The two rankings are merged using:

Reciprocal Rank Fusion (RRF)

Dense retrieval ─┐
                 ├─→ RRF fusion → evidence passages
BM25 retrieval ──┘

3. Grounded Evidence Generation

When an Anthropic API key is configured, retrieved passages are provided to Claude to generate concise evidence summaries with citations.

The clinical research assistant is instructed to:

use only the supplied retrieved literature;

cite factual claims;

state when evidence is weak, mixed, or unavailable;

avoid diagnosis;

distinguish synthetic model output from published clinical evidence;

write for nurses and physicians.

4. Offline Mode

The Evidence Library remains usable without an LLM API key.

In offline mode the system returns:

retrieved passages;

paper titles;

years;

pages;

citations.

This keeps the retrieval layer functional even when generation is unavailable.

Web Application

The clinical application is built with Django and designed around a nursing workflow.

Main Screens

Overview

patient count;

completed assessment count;

current risk distribution;

priority high-risk cases;

direct access to patient review.

Patients

full patient search;

risk filtering;

add-patient workflow;

dedicated patient record pages.

Patient Record

clinical snapshot;

latest estimated risk;

key recorded biomarkers;

family history;

antibiotic exposure;

recorded flags;

assessment history;

estimated risk over time.

Assessment

Inputs are organized into six nurse-facing sections:

patient profile;

clinical history;

lifestyle / diet;

biomarkers;

microbiome;

red flags / surgical history.

Assessment Result

The result page acts as the clinical report and includes:

patient and assessment identity;

estimated IBD risk;

risk tier and risk scale;

contributing-factor visualization;

suggested next step;

comparison with a previous assessment when available;

supporting literature;

print / save PDF.

Evidence Library

Supports clinical literature search without exposing RAG implementation terminology in the nurse-facing UI.

About

Centralizes:

intended use;

safety;

synthetic-data notice;

validation status;

human oversight;

technical transparency.

Human-Centered AI Design

The interface follows several HCAI principles:

Human control

The system supports nurses and clinicians; it does not replace clinical judgment.

Explainability

Every assessment can surface patient-specific factors influencing the estimate.

Progressive disclosure

Clinical users see the information needed for the current task without being overwhelmed by model implementation details.

Appropriate uncertainty

Results are framed as estimated risk rather than diagnosis.

Evidence access

Supporting research is available when deeper review is needed.

Avoiding automation bias

The interface explicitly separates:

model estimate;

model explanation;

published evidence;

human clinical interpretation.

Safety transparency

Synthetic-data and validation limitations remain accessible without overwhelming every screen with repeated warnings.

Technology Stack

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

Training plots

Matplotlib

PDF extraction

PyMuPDF

Dense embeddings

FastEmbed

Embedding model

BAAI/bge-small-en-v1.5

Sparse retrieval

BM25 (rank-bm25)

Rank fusion

Reciprocal Rank Fusion

Evidence generation

Anthropic Claude (optional)

Deployment target

Render

Spreadsheet input

OpenPyXL

Project Structure

IBD/
│
├── artifacts/
│   ├── model.joblib             # Trained model + metadata
│   ├── model_report.md          # Training/evaluation report
│   ├── roc_pr.png
│   ├── calibration.png
│   └── shap_summary.png
│
├── Full text article/           # Curated IBD research PDFs
│
├── rag/
│   ├── ingest.py                # PDF extraction and chunking
│   ├── index.py                 # Embeddings + BM25 index
│   ├── retrieve.py              # Hybrid retrieval + RRF
│   ├── evidence.py              # Evidence orchestration
│   └── llm.py                   # Claude grounded summaries
│
├── rag_index/
│   ├── embeddings.npy
│   ├── chunks.jsonl
│   └── docs.json
│
├── webapp/
│   ├── clinic/
│   │   ├── templates/           # Clinical UI
│   │   ├── static/              # CSS / JavaScript
│   │   ├── management/          # Data and index commands
│   │   ├── models.py
│   │   ├── services.py
│   │   └── views.py
│   └── manage.py
│
│
├── Saudi_IBD_Synthetic.xlsx     # Synthetic prototype dataset
├── IBD_Risk_Model.ipynb         # Model walkthrough
├── features.py                  # Feature governance / encoding
├── train.py                     # Model training and selection
├── predict.py                   # Prediction interface
├── explain.py                   # SHAP explainability
├── example_patient.json
├── requirements.txt
├── .env.example
└── README.md

Local Setup

Prerequisites

Python 3.11

Git

Internet connection for first-time dependency and embedding-model downloads

Saudi_IBD_Synthetic.xlsx in the project root

1. Clone the Repository

git clone https://github.com/ghaida-alsalamah/IBD.git
cd IBD

2. Create a Virtual Environment

python -m venv .venv

Windows PowerShell

.\.venv\Scripts\Activate.ps1

macOS / Linux

source .venv/bin/activate

3. Install Dependencies

python -m pip install --upgrade pip
pip install -r requirements.txt

4. Prepare the Django Database

cd webapp
python manage.py migrate

5. Load the Synthetic Patient Dataset

python manage.py load_patients --demo-user --password nurse-demo26

This loads the 2,500 synthetic patient records and creates a local demo nurse account.

6. Build the Research Index

python manage.py build_index

This:

extracts the research PDFs;

creates overlapping passages;

generates BGE embeddings;

builds the BM25 index;

saves the local hybrid retrieval index.

7. Run the Application

python manage.py runserver

Open:

http://127.0.0.1:8000/

Local seeded demo account:

Username: nurse
Password: nurse-demo26

For any public deployment, use deployment-specific credentials rather than reusing the local demo password.

Optional Claude Integration

The application does not require Claude for risk prediction.

Claude is used only for evidence-grounded research summaries.

Copy the example environment file:

Windows

Copy-Item .env.example .env

macOS / Linux

cp .env.example .env

Add:

ANTHROPIC_API_KEY=your_key_here

Without this key, the system automatically uses retrieval-only evidence mode.

Never commit .env or API keys to GitHub.

Running the ML Pipeline

To retrain and compare models:

python train.py

Training outputs are written to artifacts/, including:

selected model bundle;

model report;

ROC / PR plots;

calibration plot;

SHAP summary.

A single prediction can also be run from the command line:

python predict.py --json example_patient.json

Testing

Run the Django test suite:

cd webapp
python manage.py test clinic

Current UI / application validation includes:

35 passing Django tests

56 expanded-layout checks

39 collapsed-layout checks

48 long-page scroll checks

PDF output review

Render Deployment

IBD Care is deployed on Render.

Once deployment is live, replace the placeholder below with the final URL:

[Open Live Demo](https://ibd-care-demo.onrender.com)

Recommended production considerations:

do not use Django runserver as the production server;

configure production-safe Django settings and allowed hosts;

store secrets as Render environment variables;

keep ANTHROPIC_API_KEY outside the repository;

run database migrations during deployment;

ensure static files are served correctly;

remember that free-tier local filesystems may be ephemeral;

use persistent storage / a production database before any real clinical deployment.



Responsible AI & Clinical Safety

IBD Care is intentionally presented as clinical decision support, not an autonomous diagnostic system.

Current prototype limitations

The patient dataset is synthetic.

Model performance is not clinical validation.

SHAP explanations describe the model, not biological causality.

The research corpus is curated and is not exhaustive.

Literature retrieval can miss relevant evidence.

Generated summaries depend on retrieved passages and should be reviewed.

No result should be used independently for diagnosis or treatment.

Before real-world clinical use

The system would require, at minimum:

validation on representative real-world Saudi patient data;

prospective clinical evaluation;

clinical governance and regulatory review;

privacy and security assessment;

bias and subgroup evaluation;

calibration and drift monitoring;

integration with approved clinical workflows / EHR systems;

formal human-factors and nurse usability testing.

Future Work

Potential next steps include:

validation on a larger real Saudi cohort;

hospital / EHR integration;

external and prospective validation;

expanded microbiome and biomarker evidence;

calibrated uncertainty communication;

longitudinal clinical monitoring;

production-grade authentication and audit logging;

persistent production database;

nurse usability studies;

model monitoring and drift detection.

Hackathon Context

Event: Nursing Innovation Hackathon 2026
Hackathon ID: NH-74
Track: Track 3 — AI-Driven Clinical Decision Support
Project: Machine Learning-Based Prediction of Inflammatory Bowel Disease Risk Using Gut Dysbiosis Biomarkers in Saudi Youth

The project explores how interpretable machine learning and evidence-grounded AI can be combined in a nurse-centered workflow for early IBD risk assessment.

<div align="center">

IBD Care

Information · Understanding · Care

Built as a clinical decision-support prototype for the Nursing Innovation Hackathon 2026.

</div>
