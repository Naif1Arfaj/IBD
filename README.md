# IBD-Risk AI: ML model, research RAG and clinical web app

> ⚠️ Synthetic data only. Model outputs and explanations reflect a synthetic generation formula, not real biology or clinical accuracy.

## Run the web app
```bash
cd "ibd_model/webapp"
../.venv/bin/python manage.py runserver
```
Open http://127.0.0.1:8000 and sign in as **nurse / nurse-demo-2026**.

## First-time setup (already done on this machine)
```bash
/opt/homebrew/bin/python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd webapp
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py load_patients --demo-user --password nurse-demo-2026   # 2,500 synthetic patients
../.venv/bin/python manage.py build_index        # 67 papers → 2,280 passages (~3 min)
```

## Enable Claude (optional)
1. Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`.
2. Restart the server.

Reports and the Evidence Library then get written summaries with citations (model `claude-opus-5-5`, server-side refusal fallback enabled).

- **Cost:** about $0.03 per variable summary (cached after first use) and $0.05 per report narrative.
- **Optional pre-build:** `manage.py build_evidence` generates every variable's summary up front (about $3 total).

## Layout
| Path | What |
|---|---|
| `features.py`, `explain.py`, `predict.py`, `train.py` | ML model: 61 inputs, Sparse Logistic Regression, SHAP |
| `IBD_Risk_Model.ipynb` | Notebook walkthrough of training and evaluation |
| `rag/` | PDF ingest, hybrid search (BGE-small + BM25), Claude with citations, evidence |
| `rag_index/` | Built search index |
| `Full text article/` | Research PDFs |
| `webapp/` | Django app: patients, risk assessment, reports, evidence library |

## Tests
```bash
cd webapp && ../.venv/bin/python manage.py test clinic
```
