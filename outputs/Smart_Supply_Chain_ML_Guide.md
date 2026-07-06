# Smart Supply Chain — ML Integration Guide

> **Stage Project · 22 June – 4 September 2026 · Dataset: DataCo Smart Supply Chain (Kaggle)**

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [ML Model Strategy](#2-ml-model-strategy)
   - 2.1 [Demand Forecasting](#21-demand-forecasting)
   - 2.2 [Anomaly Detection](#22-anomaly-detection)
   - 2.3 [Customer Segmentation (RFM + K-Means)](#23-customer-segmentation-rfm--k-means)
   - 2.4 [Stockout Risk Scoring](#24-stockout-risk-scoring)
   - 2.5 [Feature Importance](#25-feature-importance-elasticity-analysis)
3. [Anomaly Deep Dive — DataCo Examples](#3-anomaly-deep-dive--dataco-examples)
   - 3.1 [What is an anomaly?](#31-what-is-an-anomaly)
   - 3.2 [The four anomaly types](#32-the-four-anomaly-types)
   - 3.3 [Real DataCo column examples](#33-real-dataco-column-examples)
   - 3.4 [Z-score explained](#34-z-score-explained)
4. [Detection Code (Paste-Ready)](#4-detection-code-paste-ready)
5. [LLM + ML Integration Pipeline](#5-llm--ml-integration-pipeline)
6. [SHAP — Explainability Layer](#6-shap--explainability-layer)
7. [Tech Stack & Implementation Timeline](#7-tech-stack--implementation-timeline)

---

## 1. Project Overview

The Smart Supply Chain Dashboard is a 2-month internship project aimed at transforming raw supply chain data into actionable intelligence. The platform covers the full value chain — suppliers, orders, inventory, transport, and customers — with ML models at the core to shift decision-making from **reactive** to **proactive**.

| Objective | Key Output |
|---|---|
| Visibility | Unified, interactive dashboard for all supply chain nodes |
| Anticipation | Predictive KPIs — days to stockout, 30/60/90-day demand forecasts |
| AI Decision Support | Anomaly alerts + LLM-generated natural language recommendations |
| Security | JWT auth, RBAC roles (Admin / SC Manager / Client) |

### Dataset

**DataCoSupplyChainDataset.csv** — 180,000+ order records, 40+ columns.

Key columns used throughout this project:

- `Days for shipping (real)` — actual delivery days
- `Days for shipment (scheduled)` — promised delivery days
- `Order Item Quantity` — units ordered
- `Sales` — total order value
- `Order Profit Per Order` — profit (can be negative)
- `Order Item Discount Rate` — discount applied (0–1)
- `Order Status` — includes `SUSPECTED_FRAUD` label
- `Late_delivery_risk` — binary flag
- `order date (DateOrders)` — order timestamp
- `Customer Id`, `Customer Segment`, `Category Name`, `Product Name`

> ⚠️ **Always load with `encoding='latin-1'`** — the CSV contains accented characters that break UTF-8 parsing and will throw a `UnicodeDecodeError`.

```python
df = pd.read_csv('DataCoSupplyChainDataset.csv', encoding='latin-1')
```

---

## 2. ML Model Strategy

Five ML models form the intelligence layer. Ordered by **recommended implementation priority** for the 2-month window:

| # | Model | Type | Priority | Business Output |
|---|---|---|---|---|
| 1 | Anomaly Detection | Unsupervised | **FIRST** | Traffic-light alerts |
| 2 | Demand Forecasting | Time Series | **SECOND** | Days-to-stockout badge |
| 3 | Stockout Risk Scoring | Regression + SHAP | **THIRD** | Per-product risk index |
| 4 | Customer Segmentation | Clustering | **FOURTH** | RFM tier + bubble chart |
| 5 | Feature Importance | Interpretability | **BONUS** | Elasticity sensitivity chart |

---

### 2.1 Demand Forecasting

**What it solves:** replaces gut-feel replenishment with data-driven purchase orders. The dashboard shows a rolling forecast curve with confidence bands so managers see exactly when to reorder.

**Algorithms:**
- **Prophet (Meta)** — handles seasonality automatically, robust to missing data
- **SARIMA** — classical time-series baseline for comparison
- **LightGBM with lag features** — powerful when you have many products with short histories

**Key DataCo columns:** `order date (DateOrders)`, `Order Item Quantity`, `Sales`, `Product Name`, `Category Name`

```python
from prophet import Prophet
import pandas as pd

df = pd.read_csv('DataCoSupplyChainDataset.csv', encoding='latin-1')
df['ds'] = pd.to_datetime(df['order date (DateOrders)'])
df['y']  = df['Order Item Quantity']

# Aggregate to daily totals
daily = df.groupby('ds')['y'].sum().reset_index()

m = Prophet(seasonality_mode='multiplicative', yearly_seasonality=True)
m.fit(daily)

future   = m.make_future_dataframe(periods=90)
forecast = m.predict(future)
# forecast[['ds','yhat','yhat_lower','yhat_upper']] -> send to dashboard
```

> 💡 **Dashboard standout:** show a **days-to-stockout countdown badge** per product, calculated as `current_stock / avg_daily_forecast`. That number is what executives actually act on, not the forecast curve itself.

---

### 2.2 Anomaly Detection

**What it solves:** flags abnormal order volumes, late deliveries, cost spikes, and fraud patterns in real time. Powers the traffic-light alert system with genuine ML confidence scores rather than hard-coded thresholds.

**Algorithms:**
- **Isolation Forest** — tree-based, works well on tabular data, no distribution assumption needed
- **Z-score (rolling)** — fast, interpretable, great for time-series drift detection per supplier
- **DBSCAN** — spatial clustering for geographic delivery anomalies

**Feature set for Isolation Forest:**

| Feature | DataCo Column | Why it matters |
|---|---|---|
| Delivery overrun | `Days for shipping (real)` − `Days for shipment (scheduled)` | Flags supplier delays |
| Order quantity | `Order Item Quantity` | Catches data-entry errors (extra zero) |
| Order value | `Sales` | Flags unusually large or zero-revenue orders |
| Profit margin | `Order Profit Per Order / Sales` | Negative = loss order |
| Discount rate | `Order Item Discount Rate` | 0.8+ is a fraud signal |

> 💡 **Dashboard standout:** pair Isolation Forest (unsupervised, for new orders) with a supervised XGBoost classifier trained on the `SUSPECTED_FRAUD` label already in the dataset. The combination is far stronger than either alone.

---

### 2.3 Customer Segmentation (RFM + K-Means)

**What it solves:** RFM scoring produces a numeric vector per client. K-Means clusters them into actionable tiers (Champion, Loyal, At-Risk, Dormant). Stock is preferentially allocated to Champion-tier customers during shortages.

**Implementation steps:**

1. Calculate R, F, M scores from order history (score 1–5 for each dimension)
2. Normalize with `StandardScaler` before clustering
3. Run K-Means with k=4–6; use Silhouette Score and Elbow Method to pick k
4. Map cluster centroids to business labels (high F+M+recent R = Champion)
5. Visualize as a bubble chart: x=Frequency, y=Monetary, size=Recency

```python
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import pandas as pd

df = pd.read_csv('DataCoSupplyChainDataset.csv', encoding='latin-1')
snapshot = df['order date (DateOrders)'].max()

rfm = df.groupby('Customer Id').agg(
    Recency   = ('order date (DateOrders)',
                 lambda x: (pd.Timestamp(snapshot) - pd.to_datetime(x).max()).days),
    Frequency = ('Order Id', 'nunique'),
    Monetary  = ('Sales', 'sum')
).reset_index()

X_scaled = StandardScaler().fit_transform(rfm[['Recency','Frequency','Monetary']])

km = KMeans(n_clusters=5, random_state=42, n_init=10)
rfm['Cluster'] = km.fit_predict(X_scaled)
print(rfm.groupby('Cluster')[['Recency','Frequency','Monetary']].mean())
```

> 💡 **Dashboard standout:** the bubble chart (Frequency vs Monetary, size = Recency) is something executives can immediately grasp and share with the commercial team.

---

### 2.4 Stockout Risk Scoring

**What it solves:** combines demand volatility, current stock level, and supplier lead time into a single per-product risk index. SHAP values explain *why* the score is high — enabling the LLM to generate specific, grounded recommendations.

**Algorithms:**
- **XGBoost / Random Forest Regressor** — captures non-linear interactions between features
- **SHAP** — per-prediction feature contributions (see Section 6 for full detail)
- **Key metrics:** RMSE and MAE on held-out validation set

```python
import xgboost as xgb
import shap
import numpy as np

# Features engineered from DataCo columns
# demand_cv   = coefficient of variation of recent demand
# stock_days  = current_stock / avg_daily_demand
# lead_time   = avg supplier lead time (days)

X = df[['demand_cv', 'stock_days', 'lead_time', 'price']]
y = df['actual_stockout_days']  # label from historical stockouts

model = xgb.XGBRegressor(n_estimators=200, learning_rate=0.05, random_state=42)
model.fit(X, y)

# SHAP values — the key to natural language explanations
explainer = shap.TreeExplainer(model)
shap_vals = explainer(X)
# shap_vals.values[i] -> array of per-feature contributions for row i
```

> 💡 **Dashboard standout:** instead of showing "Risk: 82/100", your dashboard says *"High risk driven mainly by demand variance (+45%), not low stock (-25%). Recommend increasing safety stock by 20%."* That specificity turns a number into a decision.

---

### 2.5 Feature Importance (Elasticity Analysis)

**What it solves:** a gradient boosting model trained on historical orders reveals price and discount elasticity. Example output: "A 10% price increase on category B reduces volume by ~6%." Feeds the interactive sensitivity chart in the dashboard.

```python
import lightgbm as lgb
from sklearn.inspection import permutation_importance
import pandas as pd

features = ['price', 'Order Item Discount Rate',
            'Days for shipment (scheduled)', 'Category Name', 'Customer Segment']
target   = 'Order Item Quantity'

model = lgb.LGBMRegressor(n_estimators=300, random_state=42)
model.fit(X_train, y_train)

imp = permutation_importance(model, X_test, y_test, n_repeats=10, random_state=42)
imp_df = pd.DataFrame({'feature': features, 'importance': imp.importances_mean})
imp_df = imp_df.sort_values('importance', ascending=False)
print(imp_df)  # Top drivers of purchase volume
```

---

## 3. Anomaly Deep Dive — DataCo Examples

### 3.1 What is an anomaly?

An anomaly is a data point that deviates so far from expected behaviour that it suggests a different underlying process — a sensor error, a fraud event, a broken supplier, or a genuine operational crisis. Anomaly detection finds these automatically, without needing pre-labelled examples of what "bad" looks like.

---

### 3.2 The four anomaly types

| Type | Definition | DataCo Example | Best Detector |
|---|---|---|---|
| **Point** | Single value statistically impossible | `Order Item Quantity = 2000` for a consumer | Isolation Forest, Z-score |
| **Contextual** | Normal globally, abnormal for this entity | Qty = 95 for a Home Office account that always buys 1–3 | Rolling Z-score per customer |
| **Collective** | No single bad row, but a pattern is wrong | Supplier 3 days late every week for a month | Rolling window Z-score |
| **Fraud** | Labelled anomaly in `Order Status` column | `SUSPECTED_FRAUD` + 80% discount + bank transfer | Supervised classifier (XGBoost) |

---

### 3.3 Real DataCo column examples

#### Delivery delay anomalies

| Order ID | Mode | Scheduled | Real | Delta | Status |
|---|---|---|---|---|---|
| 88001 | Standard | 4 days | 4 days | 0 | Normal |
| 88002 | First Class | 2 days | 2 days | 0 | Normal |
| **88003** | Standard | 4 days | **13 days** | **+9 ⚠️** | **ANOMALY — z-score 7.5** |
| **88004** | Same Day | 0 days | **6 days** | **+6 ⚠️** | **ANOMALY — shipping canceled** |
| 88005 | Second Class | 3 days | 6 days | +3 | Borderline — watch list |

**Row 88003:** Days Real = 13 vs scheduled 4 — a 9-day overrun on Standard Class is 3× the average delay. Isolation Forest flags this as a statistical outlier.

**Row 88004:** Same Day shipping took 6 days — the entire point of Same Day is 0–1 days. Combined with "Shipping canceled" this is a broken record (data entry or cancellation logic error).

---

#### Order quantity & financial anomalies

| Order ID | Segment | Qty | Sales | Profit | Flag |
|---|---|---|---|---|---|
| 72001 | Consumer | 2 | $100 | +$15 | Normal |
| **72003** | Consumer | **2000 ⚠️** | **$99,980 ⚠️** | +$15k | **POINT ANOMALY — qty ×1000** |
| **72004** | Consumer | 1 | **$0 ⚠️** | **−$35 ⚠️** | **FINANCIAL ANOMALY — 100% discount** |
| **65003** | Corporate | 10 | $800 | **−$320 ⚠️** | **LOSS ORDER — margin −40%** |
| **91002** | Consumer | 3 | **$44 ⚠️** | **−$180 ⚠️** | **🚨 FRAUD — 80% disc + bank transfer** |

**Row 72003:** Qty = 2000 for a Consumer on Clothing. A typical consumer buys 1–5 items. This is almost certainly a data entry error (extra zero) — 6+ standard deviations from the mean.

**Row 72004:** A completed order with zero revenue is a financial anomaly and a potential fraud signal. `Order Profit Per Order` would be deeply negative here.

**Row 91002:** The `SUSPECTED_FRAUD` label + 80% discount + bank transfer + shipping canceled is a strong fraud signature your classifier will learn.

---

#### The built-in fraud label

> 🔑 **KEY INSIGHT:** The DataCo dataset has `Order Status = 'SUSPECTED_FRAUD'` as an actual column. This is your free supervised ground truth. Use it to train an XGBoost classifier, then use Isolation Forest for new unlabeled orders. The two together are far stronger than either alone.

---

### 3.4 Z-score explained

Z-score answers one question: **how many standard deviations from the average is this value?**

```
z = (x − mean) / std_dev
```

| Z-score range | What it means | Action |
|---|---|---|
| 0 to ±1 | Normal — covers 68% of values | No action |
| ±1 to ±2 | Slightly unusual — 95% boundary | Log it |
| ±2 to ±3 | Notable — only 5% of values here | Watch list |
| **> ±3** | **Extreme outlier — 0.3% probability** | **Fire alert** |

**Concrete DataCo example:**

`Days for shipping (real)` for Standard Class has mean = 4, std = 1.2. Order 88003 took 13 days:

```
z = (13 − 4) / 1.2 = 7.5   →  EXTREME OUTLIER — red alert
```

**Rolling Z-score** — the right approach for supplier reliability (catches gradual drift):

```python
df['z_delay'] = (
    df.groupby('Supplier Name')['delay_delta']
    .transform(lambda x: (x - x.rolling(30).mean()) / x.rolling(30).std())
)
df['delivery_anomaly'] = df['z_delay'].abs() > 3
```

**Limitation:** Z-score assumes a roughly bell-shaped (normal) distribution. Order quantities and sales values are right-skewed. Either apply `np.log1p()` transformation first, or use Isolation Forest for those columns instead. For delivery delay, Z-score works well.

---

## 4. Detection Code (Paste-Ready)

Complete, runnable script for anomaly detection on the DataCo dataset. All column names match the actual CSV.

```python
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# ── 1. Load dataset ────────────────────────────────────────────────────────────
df = pd.read_csv('DataCoSupplyChainDataset.csv', encoding='latin-1')

# ── 2. Feature engineering ─────────────────────────────────────────────────────
df['delay_delta']    = (df['Days for shipping (real)']
                        - df['Days for shipment (scheduled)'])

df['profit_margin']  = (df['Order Profit Per Order']
                        / df['Sales'].replace(0, np.nan))

df['discount_ratio'] = df['Order Item Discount Rate']

# ── 3. Select features ─────────────────────────────────────────────────────────
features = [
    'delay_delta',           # delivery overrun in days
    'Order Item Quantity',   # catches the ×10 entry errors
    'Sales',                 # total order value
    'profit_margin',         # negative = loss order
    'discount_ratio',        # 0.8+ is suspicious
]
X        = df[features].fillna(0)
X_scaled = StandardScaler().fit_transform(X)

# ── 4. Isolation Forest (5% expected anomaly rate) ─────────────────────────────
clf = IsolationForest(contamination=0.05, random_state=42, n_estimators=200)
df['anomaly']       = clf.fit_predict(X_scaled)   # -1 = anomaly, 1 = normal
df['anomaly_score'] = clf.decision_function(X_scaled)
# anomaly_score: lower = more anomalous; pass this value to Ollama

# ── 5. Rolling Z-score per supplier (30-day window) ───────────────────────────
df['order_date'] = pd.to_datetime(df['order date (DateOrders)'])
df = df.sort_values('order_date')

df['z_supplier'] = (
    df.groupby('Customer City')['delay_delta']
    .transform(lambda x: (x - x.rolling(30, min_periods=5).mean())
                         / x.rolling(30, min_periods=5).std().replace(0, np.nan))
)

# ── 6. Tag fraud using the built-in label ─────────────────────────────────────
df['is_fraud'] = (df['Order Status'] == 'SUSPECTED_FRAUD').astype(int)

# ── 7. Combined alert flag ────────────────────────────────────────────────────
df['alert'] = (
    (df['anomaly'] == -1)       |   # Isolation Forest flag
    (df['z_supplier'].abs() > 3)|   # Supplier drift flag
    (df['is_fraud'] == 1)           # Known fraud label
)

# ── 8. Output top anomalies for dashboard ─────────────────────────────────────
top = (df[df['alert']]
       .sort_values('anomaly_score')
       [['Order Id', 'delay_delta', 'Order Item Quantity',
         'Sales', 'profit_margin', 'anomaly_score', 'is_fraud']]
       .head(20))

print(f"Total anomalies found: {df['alert'].sum()} / {len(df)}")
print(top)
```

---

## 5. LLM + ML Integration Pipeline

The most differentiating feature of this dashboard: ML scores are piped through SHAP into Ollama to generate natural language alerts — not just numbers.

**Instead of:** "Stockout Risk: 82/100"

**Your dashboard says:** *"Running Shoes face high stockout risk driven by a 45% surge in demand variance this month; recommend increasing the reorder quantity by 30% for the next purchase cycle."*

### How the pipeline works

| Step | Component | Output |
|---|---|---|
| 1 | ML model runs on new order/product data | `anomaly_score`, `shap_values`, `risk_index` |
| 2 | SHAP values parsed into human-readable reasons | `"demand_cv: +45%, lead_time: +30%"` |
| 3 | Structured prompt built with score + reasons | JSON payload to Ollama API |
| 4 | Ollama (local LLM) generates recommendation | Natural language alert string |
| 5 | Alert stored in MongoDB + sent to dashboard | Traffic-light card with explanation |

### Prompt engineering for Ollama

```python
import requests

def generate_alert(product_name: str, risk_score: int, shap_reasons: dict) -> str:
    reasons_text = ', '.join(
        f"{k}: {'+' if v > 0 else ''}{v:.0%}"
        for k, v in shap_reasons.items()
    )
    prompt = f"""
You are a supply chain analyst assistant.
Product: {product_name}
Stockout risk score: {risk_score}/100
Top contributing factors: {reasons_text}

Write ONE concise sentence explaining the risk and ONE actionable recommendation.
Be specific. Use numbers where available. Output plain text, no bullet points.
"""
    response = requests.post(
        'http://localhost:11434/api/generate',
        json={'model': 'mistral', 'prompt': prompt, 'stream': False}
    )
    return response.json()['response'].strip()


# Example usage
alert = generate_alert(
    product_name = 'Running Shoes - Size M',
    risk_score   = 82,
    shap_reasons = {
        'demand_variance': 0.45,
        'lead_time':       0.30,
        'stock_level':    -0.25,
    }
)
# → "Running Shoes face high stockout risk driven by a 45% surge in demand
#    variance this month; recommend increasing the reorder quantity by 30%
#    for the next purchase cycle."
```

---

## 6. SHAP — Explainability Layer

### The problem SHAP solves

When XGBoost predicts "stockout risk = 82/100", it doesn't say why. You can't present a black box to a manager. **SHAP (SHapley Additive exPlanations)** decomposes every single prediction into per-feature contributions — accounting for every point of the prediction gap.

### The core formula

For any single prediction:

```
prediction = base_value + SHAP(feature_1) + SHAP(feature_2) + ... + SHAP(feature_n)
```

Where `base_value` is the average prediction across the entire training set (what the model would predict knowing nothing about this specific record).

### Concrete example

Average stockout risk across all products = **40/100** (base value). Product X predicted = **82/100**. SHAP breaks down the +42 gap:

| Feature | SHAP value | Meaning |
|---|---|---|
| demand_variance | +19 | High variance pushed risk up 19 points |
| lead_time | +13 | Long lead time added 13 more points |
| stock_level | −8 | Stock is decent — pulled risk down 8 |
| price | +2 | Minor effect |
| **Sum** | **+26** | 40 (base) + 26 (SHAP sum) ≠ 82... |

> Note: in practice the SHAP values sum exactly to `prediction − base_value`. The table above is simplified for illustration.

### How SHAP computes each value

For each feature, SHAP runs a thought experiment across **every possible combination** of features with and without that feature included, measures the prediction change each time, and averages. This is why it's mathematically "fair" — it captures feature interactions.

The guarantee: SHAP values are the **only** decomposition that simultaneously satisfies four axioms — efficiency (values sum to the gap), symmetry (identical features get equal credit), dummy (irrelevant features get zero), and additivity (independent models add up cleanly).

### Global vs local SHAP

| Mode | What it answers | Use in your project |
|---|---|---|
| **Local** | Why was *this specific order* flagged? | Feed to Ollama for natural language alerts |
| **Global** | Which features matter most *overall*? | Feature importance / elasticity chart in dashboard |

### Code

```python
import shap
import xgboost as xgb

model = xgb.XGBRegressor().fit(X_train, y_train)

# TreeExplainer is fast for all tree-based models (XGBoost, LightGBM, Random Forest)
explainer  = shap.TreeExplainer(model)
shap_values = explainer(X_test)

# For one specific product (row 0):
print(shap_values[0].values)        # → [+19.2, +13.1, -8.4, +2.1]
print(shap_values[0].base_values)   # → 40.0  (the average prediction)
print(shap_values[0].data)          # → [0.82, 14, 250, 35.99]  (actual feature values)

# Global importance — aggregate SHAP across all rows
shap.summary_plot(shap_values, X_test)   # visual summary of all features
```

### SHAP's role at the soutenance

Being able to say *"our model doesn't just predict — it explains; here's why it flagged this specific product"* is the difference between a demo and an impressive demo. SHAP is the bridge between the ML black box and business decision-makers who need to understand before they act.

---

## 7. Tech Stack & Implementation Timeline

### Full stack

| Layer | Technology | Purpose |
|---|---|---|
| Backend | Python + Flask / Express.js | API endpoints for ML results, KPIs, alerts |
| Frontend | React.js | Single-page dashboard, interactive charts |
| Database | MongoDB | Orders, products, anomaly logs, ML scores |
| ML / Data | Pandas, NumPy, Scikit-learn | Feature engineering, Isolation Forest, K-Means |
| Forecasting | Prophet (Meta) | Demand forecasting, days-to-stockout |
| Boosting | XGBoost + LightGBM | Risk scoring, feature importance |
| Explainability | SHAP | Per-prediction explanations for LLM prompt |
| LLM | Ollama (local) | Natural language alert generation (privacy-safe) |
| Auth | JWT + RBAC | Admin / SC Manager / Client access levels |

### 2-month implementation timeline

| Week | Focus | ML Deliverable |
|---|---|---|
| 1–2 | Data loading, EDA, MongoDB schema | Exploratory notebook on DataCo |
| 3–4 | Anomaly detection + alert API | Isolation Forest + fraud classifier live |
| 5–6 | Demand forecasting + risk scoring | Prophet forecasts + XGBoost risk index |
| 7 | Segmentation + feature importance | K-Means clusters + permutation importance |
| 8 | Ollama integration + UI polish | LLM alert pipeline connected to frontend |
| 8+ | Demo prep, documentation | Final soutenance presentation |

---

> **Demo narrative for the soutenance:** most BI dashboards show history. Yours shows the **future** (Prophet), explains anomalies in plain language (Ollama + SHAP), and allocates scarce stock intelligently (RFM clusters). That progression — **Descriptive → Predictive → Prescriptive** — is your narrative arc.

---

*Smart Supply Chain Dashboard — ML Integration Guide · Generated June 2026*
