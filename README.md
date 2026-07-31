# Smart Supply Chain AI Dashboard

The **Smart Supply Chain AI Dashboard** is an intelligent decision-support web application designed to help managers monitor logistics, prevent stockouts, and automate inventory purchasing.

By analyzing sales records, supplier performance, and shipping timelines, the platform provides real-time visibility over supply chain operations and helps managers make proactive decisions before inventory disruptions occur.

---

## 🌟 What This Application Does

* **Executive Logistics Dashboard:** Displays an overall health score of supply chain operations, tracking delivery performance (OTIF), active stockouts, and shipping delays in real time.
* **90-Day Demand Forecasting:** Predicts customer order volumes 3 months into the future so inventory managers know when demand will peak and when to reorder stock.
* **Automated Stockout Alerts:** Flags high-demand days and automatically calculates how many units to reorder when stock drops below safety thresholds.
* **Supplier Performance Tracking:** Evaluates vendor delivery reliability, tracks shipping delays, and generates recommended purchase orders.
* **Smart AI Assistant:** Features an embedded AI chatbot that answers questions about orders, inventory, and suppliers in plain language and sends automated email alerts to vendors.
* **Biometric Face Login:** Secures manager access with optional webcam facial verification.

---

## 📋 Requirements to Run

To run this application on your machine, ensure you have the following installed:

1. **[Node.js](https://nodejs.org/)** (v18.0 or higher) — Required for running the frontend web app.
2. **[Python](https://www.python.org/)** (v3.11 or higher) — Required for running the backend API and calculations.
3. **[MongoDB Community Server](https://www.mongodb.com/try/download/community)** — Required for database storage (running locally on port `27017`).
4. **[Ollama](https://ollama.com/)** *(Optional)* — Required for the AI chatbot (running locally on port `11434` with model `qwen2.5:7b` installed).

---

## 🚀 How to Run the Project

### 1. Setup & Seed Database
Open your terminal and run the following commands:
```bash
cd BackEnd
python -m venv venv

# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
python seed_db.py
```

### 2. Start the Backend API
Run the backend server:
```bash
python run.py
```
*(The backend server will run at `http://localhost:8000`)*

### 3. Start the Frontend Application
Open a new terminal window and run:
```bash
cd FrontEnd
npm install
npm run dev
```
*(The web application will open in your browser at `http://localhost:4200`)*

---

## 👤 Author

* **Developer:** SABOR Abderrahmane
* **Academic Institution:** École Nationale des Sciences Appliquées de Khouribga (ENSAK)
* **Host Organization:** AddSer Conseil (Casablanca, Morocco)
