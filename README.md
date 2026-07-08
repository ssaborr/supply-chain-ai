# Smart Supply Chain Dashboard

A comprehensive, end-to-end web application that integrates real-time supply chain monitoring, interactive demand forecasting, customer segmentation, anomaly detection, and secure order importation.

Built with a **FastAPI backend**, an **Angular frontend**, **MongoDB**, and an array of **Machine Learning models** (ARIMA, LightGBM, KNN, KMeans), this system offers businesses a premium, zero-downtime control center for logistics, sales, and predictive operations.

---

## Key Features

### 1. Ingestion & In-Memory Model Hot-Swapping
*   **Sales Order Importation:** Supports importing sales records from `.csv` and `.xlsx` files with automatic pre-flight schema and header validation.
*   **Column Deduplication:** Implements robust pandas column deduplication (`df.loc[:, ~df.columns.duplicated()]`) to ensure clean ingestion from raw datasets.
*   **Zero-Downtime Retraining:** Initiates asynchronous retraining loops in non-blocking OS subprocesses via `asyncio.create_subprocess_exec`. The FastAPI thread stays fully responsive, retaining old model weights in memory and swapping to the new ones atomically upon success.

### 2. Machine Learning Pipeline
*   **Demand Forecasting (ARIMA):** Predicts 90-day demand volume using an `ARIMA(1, 1, 1)x(1, 0, 1, 7)` seasonal model. Adds deterministic seeded noise (`np.random.seed(product_id)`) based on residual standard deviation to capture realistic daily demand swings instead of outputting flat expectation curves.
*   **Fraud Detection (LightGBM):** Classifies suspicious transaction patterns (e.g., suspected payment fraud) on the fly during sales order ingestion.
*   **Anomaly Detection (KNN):** Detects logistics delays and shipment anomalies using multi-dimensional K-Nearest Neighbors.
*   **Customer Segmentation (KMeans):** Clusters clients using RFM (Recency, Frequency, Monetary) metrics to identify high-value buyers and inactive partnerships.

### 3. Executive AI Summaries & Insights
*   **Local LLM Integration:** Uses a locally-hosted Ollama model (e.g. `qwen2.5:7b` or `llama3`) to analyze metrics (OTIF service level, stockouts, revenue, anomaly counts) and generate concise, professional executive summaries for supply chain managers.
*   **Synchronized UI Loading Overlay:** Frontend cards for AI summaries and forecasting charts enter a coordinated loading state when changing product selection to prevent showing stale data.

---

## Project Structure

```text
├── BackEnd/
│   ├── app/
│   │   ├── core/           # Database configurations and app settings
│   │   ├── models/         # Pydantic validation schemas
│   │   ├── routers/        # FastAPI API endpoints (orders, products, kpis, chatbot)
│   │   └── services/       # Core services (auth, anomaly sync, ML update, ARIMA forecast)
│   ├── processed_data/     # Rebuilt CSV training sets and pickled model weights
│   ├── requirements.txt    # Python virtual environment dependencies
│   ├── run.py              # Backend Uvicorn runner
│   ├── seed_db.py          # MongoDB initial seeder script
│   └── train_global.py     # Standsalone global demand forecast trainer
├── FrontEnd/
│   ├── src/app/
│   │   ├── dashboard/      # Main executive dashboard component
│   │   ├── demand-forecast/# Forecasting calendar and Chart.js graphics
│   │   ├── sales-order/    # Sales order data tables and custom import modals
│   │   └── services/       # Angular HTTP services (auth, route guards)
│   └── angular.json        # Frontend workspace configuration
├── arima_model_evaluation.ipynb # Interactive ARIMA evaluation notebook
├── processed_data/         # Shared output folder for serialized model binaries
├── test_orders_new.csv     # Pre-configured validation test set (Order IDs offset by 10M)
└── README.md
```

---

## Tech Stack

*   **Frontend:** Angular 17, TypeScript, RxJS, Chart.js, FullCalendar
*   **Backend:** FastAPI, Uvicorn, Motor (Async MongoDB Driver)
*   **Database:** MongoDB
*   **AI/ML Libraries:** Scikit-Learn, LightGBM, Statsmodels (ARIMA), NumPy, Pandas
*   **Natural Language:** Ollama (Local LLM API)

---

## Getting Started

### Prerequisites
*   [Node.js](https://nodejs.org/) (v18+)
*   [Python](https://www.python.org/) (v3.11+)
*   [MongoDB](https://www.mongodb.com/) (running locally on port `27017`)
*   [Ollama](https://ollama.com/) (optional, running locally on port `11434` with model `qwen2.5:7b` installed)

### 1. Database Setup
Ensure MongoDB is running, then seed the initial data:
```bash
cd BackEnd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python seed_db.py
```

### 2. Run the FastAPI Backend
Start the Uvicorn web server (hot-reloads automatically on code modifications):
```bash
python run.py
```
The API documentation will be available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### 3. Run the Angular Frontend
```bash
cd FrontEnd
npm install
npm run dev
```
The web application will be accessible at [http://localhost:4200](http://localhost:4200).

---

## Interactive ARIMA Model Evaluation

To inspect the training details, summary metrics (MAE, RMSE, MAPE), and plotting evaluations of the demand forecasting engine, you can run the Jupyter Notebook:
```bash
pip install jupyter
jupyter notebook arima_model_evaluation.ipynb
```

---

## Developer Manuals & Reference Guides
Refer to the `outputs/` directory for detailed documentation:
*   [Import & Retraining Implementation Guide](outputs/import_feature_implementation.pdf): Full manual detailing Angular and FastAPI integration patterns.
*   [KPI & Statistics Guide](outputs/KPI_Reference_Guide.pdf): Overview of supply chain metrics calculations.
*   [Face Liveness Anti-Spoofing Guide](outputs/face_recognition_guide.pdf): Implementation guide on incorporating anti-spoofing checks (like Silent-Face-Anti-Spoofing or Google Mediapipe) to prevent users from bypassing logins with flat photos or screens.
