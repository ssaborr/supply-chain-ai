# Smart Supply Chain AI Dashboard

An integrated, end-to-end enterprise decision-support platform designed to transform complex supply chain telemetry into proactive, predictive logistics intelligence.

Developed for **AddSer Conseil** in collaboration with **ENSA Khouribga**, the platform combines a decoupled **FastAPI** Python backend, a responsive **Angular 17** single-page web application, a document-oriented **MongoDB NoSQL** data store, and a multi-tiered **Artificial Intelligence & Machine Learning pipeline**.

---

## 🌟 Key System Capabilities

### 1. Ingestion Pipeline & Zero-Downtime Hot-Swapping
* **Batch Sales Order Importation:** Real-time CSV and XLSX order ingestion with automated Pandas schema validation, type checking, and header deduplication.
* **Non-Blocking Asynchronous Retraining:** Initiates background retraining tasks in isolated OS subprocesses via `asyncio.create_subprocess_exec`. The FastAPI event loop remains 100% unblocked and responsive during training cycles.
* **Atomic In-Memory Hot-Swapping:** Newly trained model binaries (`.pkl`) overwrite disk files atomically, and active memory pointers update seamlessly with **zero application downtime**.

### 2. Multi-Model Machine Learning Engine
* **Demand Forecasting (ARIMA & Meta Prophet):** Predicts daily demand velocity over a 90-day horizon with 95% confidence bounds. Uses logarithmic variance transformation $\log(1+y)$ for volatile sales curves and residual Gaussian noise simulation.
* **Supervised Fraud & Discount Anomaly Classifier (LightGBM):** Real-time classification of unauthorized discount overrides and suspicious transaction patterns upon batch order import.
* **Logistics Delay Anomaly Detector (KNN):** Distance-based K-Nearest Neighbors ($k=5$) identifying shipment lead-time variances on normalized $Z$-score feature spaces.
* **Product & Customer RFM Segmentation (K-Means):** Unsupervised clustering categorizing catalog inventory into performance tiers (*High Value, Volume Drivers, Low Performers*) and customers into RFM segments (*Champions, Loyal, At-Risk, Inactive*).

### 3. Biometric Security & Access Control
* **InsightFace Biometric 2FA:** Facial recognition authentication using CNN face detection ($S_{\text{det}} \ge 0.65$) and normalized 512D ArcFace feature embeddings. Validates identity via cosine similarity matching ($\text{Similarity} \ge 0.65$).
* **Role-Based Access Control (RBAC):** Strict JWT token validation (24-hour expiration) separating **Executive Admin** and **Supplier Partner** workspace views.

### 4. Conversational AI Assistant & Automated Email Dispatch
* **Local ReAct Agent (Ollama Qwen2.5):** Natural language text-to-MongoDB translation executing a Reasoning + Acting loop with strict role-scoped query guardrails.
* **Automated SMTP Supplier Emailing:** Generates context-aware reminder emails for supply risks and dispatches them directly to vendor partners via single-click triggers.

---

## 🏗️ System Architecture

```text
                                  +------------------------------+
                                  |     Angular 17 Client UI     |
                                  | (RxJS, Chart.js, FullCalendar)|
                                  +--------------+---------------+
                                                 |
                                         HTTP / REST API
                                                 |
                                  +--------------v---------------+
                                  |    FastAPI Python Backend    |
                                  |  (JWT Auth, Motor Driver)    |
                                  +-------+--------------+-------+
                                          |              |
                    +---------------------+              +---------------------+
                    |                                                          |
     +--------------v---------------+                          +---------------+--------------+
     |   MongoDB NoSQL Data Store   |                          |   AI & ML Intelligence Engine|
     | (Orders, Products, Clients)  |                          | (LightGBM, KNN, Prophet, LLM)|
     +------------------------------+                          +------------------------------+
```

---

## 📂 Project Repository Structure

```text
├── BackEnd/
│   ├── app/
│   │   ├── core/           # Database connections and CORS middleware settings
│   │   ├── models/         # Pydantic data validation schemas
│   │   ├── routers/        # FastAPI REST API endpoints (orders, products, kpis, chatbot, auth)
│   │   └── services/       # Core services (ml_update, forecast_service, delay_service, anomaly_sync)
│   ├── processed_data/     # Feature matrices and serialized model binaries (.gitkeep)
│   ├── requirements.txt    # Backend Python virtual environment dependencies
│   ├── run.py              # Backend Uvicorn application runner
│   ├── seed_db.py          # MongoDB initial seeder script
│   └── train_global.py     # Global demand forecasting trainer
├── FrontEnd/
│   ├── src/app/
│   │   ├── dashboard/      # Main executive control center component
│   │   ├── demand-forecast/# Forecasting calendar and Chart.js graphics
│   │   ├── sales-order/    # Order management tables and import modals
│   │   └── services/       # Angular HTTP services and RBAC route guards
│   ├── angular.json        # Frontend workspace configuration
│   └── package.json        # Node.js dependencies and scripts
├── class_diagram_latest.png# System UML Class Diagram
└── README.md
```

---

## 🛠️ Technology Stack

* **Frontend:** Angular 17, TypeScript, RxJS, Chart.js, FullCalendar
* **Backend:** FastAPI, Uvicorn, Motor (Async MongoDB Driver), Pydantic
* **Database:** MongoDB Document Store
* **Machine Learning:** LightGBM, Scikit-Learn, Statsmodels (ARIMA), Meta Prophet, InsightFace, NumPy, Pandas
* **Generative AI:** Ollama (Local Qwen2.5-7B LLM instance)

---

## 🚀 Quickstart Guide

### Prerequisites
* **Node.js** (v18.0+)
* **Python** (v3.11+)
* **MongoDB** (running locally on port `27017`)
* **Ollama** (running locally on port `11434` with `qwen2.5:7b` installed)

---

### 1. Database Initialization
Start MongoDB locally, then seed initial catalog and transaction data:
```bash
cd BackEnd
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
python seed_db.py
```

### 2. Start Backend API Server
Launch the FastAPI backend server:
```bash
python run.py
```
* **API Interactive OpenAPI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Start Frontend Dashboard
Launch the Angular development server:
```bash
cd FrontEnd
npm install
npm run dev
```
* **Dashboard Application:** [http://localhost:4200](http://localhost:4200)

---

## 📜 License & Academic Attribution
Developed by **SABOR Abderrahmane** (2nd Year IRIC Engineering Student, ENSA Khouribga) during the End-of-Year Internship (PFA) at **AddSer Conseil** (Casablanca, Morocco).
