# Supply Chain KPI Reference & Definitions

This document details how each of the 8 KPI cards displayed on the Dashboard is calculated from the MongoDB collections and what each metric means operationally.

---

## 1. Global SC Health
* **Database Collections**: `sales_orders`, `products`
* **Mathematical Formula**:
  Global SC Health = (OTIF + (100 - Stockout Rate)) / 2
* **Operational Meaning**:
  A balanced operational index combining customer-facing delivery performance (OTIF) and inventory health (non-stockout rate). It represents the overall operational efficiency of the supply chain ecosystem.

---

## 2. Service Level (OTIF)
* **Database Collections**: `sales_orders`
* **Mathematical Formula**:
  OTIF % = (Orders delivered on time / Total orders) x 100
  * *On-Time Condition*: actual shipment time - scheduled shipment time <= 0
* **Operational Meaning**:
  **On-Time In-Full (OTIF)** measures logistics execution efficiency. It shows the percentage of sales orders shipped within or ahead of the scheduled shipping time frame promised to customers.

---

## 3. Active Stockout Rate
* **Database Collections**: `products`
* **Mathematical Formula**:
  Stockout Rate % = (Products with current stock equal to 0 / Total catalog SKUs) x 100
* **Operational Meaning**:
  Measures catalog item availability. A high stockout rate indicates inventory depletion of active SKUs, leading to missed sales opportunities and poor customer satisfaction.

---

## 4. Avg Delivery Lead Time
* **Database Collections**: `sales_orders`
* **Mathematical Formula**:
  Average Lead Time = Sum of actual shipment times / Total orders
* **Operational Meaning**:
  The average number of days required to complete shipments. Rising lead times flag potential distribution network bottlenecks or supplier transit delays.

---

## 5. Total Revenue (Sales)
* **Database Collections**: `sales_orders`
* **Mathematical Formula**:
  Total Revenue = Sum of (quantity x unitPrice) for all order lines
  * *Fallback*: If line-items are missing for an order, the system estimates the order gross sales as order profit / 0.15, assuming a standard 15% profit margin.
* **Operational Meaning**:
  The total gross transaction revenue generated across all processed customer orders.

---

## 6. Total Orders
* **Database Collections**: `sales_orders`
* **Mathematical Formula**:
  Total Orders = Count of all documents in sales_orders
* **Operational Meaning**:
  The aggregate order volume handled by the business, highlighting demand throughput and transaction activity.

---

## 7. Active Products
* **Database Collections**: `products`
* **Mathematical Formula**:
  Active Products = Count of all documents in products
* **Operational Meaning**:
  The total catalog width (number of active SKUs) carried in inventory.

---

## 8. Total Customers
* **Database Collections**: `sales_orders`
* **Mathematical Formula**:
  Total Customers = Count of unique client_id values present in sales_orders
* **Operational Meaning**:
  The size of the active buying customer cohort placing orders in the system.
