# Supply Chain KPI Reference & Definitions

This document details how each of the 8 KPI cards displayed on the Dashboard is calculated from the MongoDB collections and what each metric means operationally.

---

## 1. Global SC Health
* **Database Collections**: `sales_orders`, `products`
* **Mathematical Formula**:
  \[\text{Global SC Health} = \frac{\text{OTIF} + (100.0 - \text{Stockout Rate})}{2}\]
* **Operational Meaning**:
  A balanced operational index combining customer-facing delivery performance (OTIF) and inventory health (non-stockout rate). It represents the overall operational efficiency of the supply chain ecosystem.

---

## 2. Service Level (OTIF)
* **Database Collections**: `sales_orders`
* **Mathematical Formula**:
  \[\text{OTIF \%} = \frac{\text{Orders Delivered On-Time}}{\text{Total Orders}} \times 100\]
  * *On-Time Condition*: \(\text{real\_shipment} - \text{scheduled\_shipment} \le 0\)
* **Operational Meaning**:
  **On-Time In-Full (OTIF)** measures logistics execution efficiency. It shows the percentage of sales orders shipped within or ahead of the scheduled shipping time frame promised to customers.

---

## 3. Active Stockout Rate
* **Database Collections**: `products`
* **Mathematical Formula**:
  \[\text{Stockout Rate \%} = \frac{\text{Products with Current Stock } = 0}{\text{Total Catalog SKUs}} \times 100\]
* **Operational Meaning**:
  Measures catalog item availability. A high stockout rate indicates inventory depletion of active SKUs, leading to missed sales opportunities and poor customer satisfaction.

---

## 4. Avg Delivery Lead Time
* **Database Collections**: `sales_orders`
* **Mathematical Formula**:
  \[\text{Avg Lead Time} = \frac{\sum \text{real\_shipment}}{\text{Total Orders}}\]
* **Operational Meaning**:
  The average number of days required to complete shipments. Rising lead times flag potential distribution network bottlenecks or supplier transit delays.

---

## 5. Total Revenue (Sales)
* **Database Collections**: `sales_orders`
* **Mathematical Formula**:
  \[\text{Total Revenue} = \sum_{\text{Orders}} \left( \sum_{\text{Lines}} \text{quantity} \times \text{unitPrice} \right)\]
  * *Fallback*: If line-items are missing for an order, the system estimates the order gross sales via: \(\text{order\_profit} \div 0.15\) (assuming a standard 15% profit margin).
* **Operational Meaning**:
  The total gross transaction revenue generated across all processed customer orders.

---

## 6. Total Orders
* **Database Collections**: `sales_orders`
* **Mathematical Formula**:
  \[\text{Total Orders} = \text{Count of all documents in } \text{sales\_orders}\]
* **Operational Meaning**:
  The aggregate order volume handled by the business, highlighting demand throughput and transaction activity.

---

## 7. Active Products
* **Database Collections**: `products`
* **Mathematical Formula**:
  \[\text{Active Products} = \text{Count of all documents in } \text{products}\]
* **Operational Meaning**:
  The total catalog width (number of active SKUs) carried in inventory.

---

## 8. Total Customers
* **Database Collections**: `sales_orders`
* **Mathematical Formula**:
  \[\text{Total Customers} = \text{Count of unique } \text{client\_id} \text{ values present in } \text{sales\_orders}\]
* **Operational Meaning**:
  The size of the active buying customer cohort placing orders in the system.
