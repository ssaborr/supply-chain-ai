# Chatbot Supplier Guardrails — Implementation Guide

This document explains the multi-layer security guardrail system implemented to prevent supplier accounts from accessing or discussing company data outside of their authorized scope (e.g., general KPIs, other suppliers' details, client names, or unrelated orders).

---

## 1. Security Architecture Overview

The guardrail system does not rely solely on the LLM's system prompt instructions. It implements a **hybrid defense-in-depth model** with four layers of constraints:

```
                  ┌──────────────────────────────┐
                  │      User Chat Request       │
                  └──────────────┬───────────────┘
                                 │
                  ┌──────────────v───────────────┐
                  │ 1. Dynamic Scope Resolution  │
                  │    - Maps supplier SKUs      │
                  │    - Maps related order IDs  │
                  └──────────────┬───────────────┘
                                 │
                  ┌──────────────v───────────────┐
                  │ 2. Context Isolation (RAG)   │
                  │    - Filters pre-retrieved   │
                  │      context & stats         │
                  └──────────────┬───────────────┘
                                 │
                  ┌──────────────v───────────────┐
                  │ 3. LLM Prompt Adaptation     │
                  │    - Restricts AI behavior   │
                  │      via system prompt       │
                  └──────────────┬───────────────┘
                                 │
                  ┌──────────────v───────────────┐
                  │ 4. Hard Query Interception   │
                  │    - Restricts db collection │
                  │    - Injects filter filters  │
                  └──────────────────────────────┘
```

---

## 2. Layer 1: Dynamic Scope Resolution

When a request arrives at `/chatbot/query`, the router checks the user's role from the authenticated JWT session. If the user is a `supplier`, we compile their specific product and order scope:

1. **Supplied SKUs:** The system queries the `purchases` collection for all entries matching their `supplier_name` and extracts all distinct `product_sku` integers.
2. **Related Sales Orders:** The system queries the `sales_orders` collection to find all customer orders containing any of those supplied SKUs.

```python
is_supplier = current_admin.get("role") == "supplier"
supplier_name = current_admin.get("supplier_name")
supplier_skus = set()
supplier_order_ids = set()

if is_supplier:
    # 1. Fetch SKUs supplied by this supplier
    async for p in db["purchases"].find({"Supplier": supplier_name}):
        for line in p.get("purchase_lines", []):
            sku = line.get("product_sku")
            if sku is not None:
                supplier_skus.add(int(sku))
                
    # 2. Fetch related sales order IDs
    async for o in db["sales_orders"].find({"order_lines.product_sku": {"$in": list(supplier_skus)}}):
        supplier_order_ids.add(int(o["id"]))
```

---

## 3. Layer 2: Context Isolation (RAG)

Before calling the LLM, the chatbot pre-retrieves database context (RAG) to feed into the prompt. The guardrail strictly limits this pre-retrieved context for supplier accounts:

- **Total Statistics:** Overrides general counts (e.g., `total_orders`, `total_anomalies`, `total_products`) to reflect only counts associated with their supplied SKUs/orders.
- **Client & KPI Context:** Completely strips `client` counts and the `kpis` list from the pre-retrieved database payload.
- **Mock/Hardcoded Responses:** Prevents execution of sensitive mockups (such as the detailed review for `PO #41241`, which leaks client names and margins) when a supplier is logged in.

---

## 4. Layer 3: LLM Prompt Adaptation

The chatbot tailors the system instructions based on the user's role:

- **Admins:** Receive the standard "Executive AI Assistant" prompt with full database schemas for all collections.
- **Suppliers:** Receive a restricted "Supplier Portal AI Assistant" prompt. It explicitly states their supplier scope limit, removes mention of the `client` or `kpis` schemas, and instructs them to politely refuse to disclose information outside of their specific inventory and orders.

---

## 5. Layer 5: Hard Database Query Interception

Even if the LLM attempts to bypass the prompt instructions or is tricked into query injection, the **query execution backend enforces hard constraints**:

```python
# 1. Restrict allowed collections
allowed_collections = ["sales_orders", "anomalies", "products"] if is_supplier else ["sales_orders", "anomalies", "products", "client", "kpis"]

if collection in allowed_collections:
    if is_supplier:
        # 2. Force injection of supplier boundaries into filters
        if collection == "sales_orders":
            db_filter = {"$and": [db_filter, {"order_lines.product_sku": {"$in": list(supplier_skus)}}]}
        elif collection == "products":
            db_filter = {"$and": [db_filter, {"sku": {"$in": list(supplier_skus)}}]}
        elif collection == "anomalies":
            db_filter = {"$and": [db_filter, {"sales_order_id": {"$in": list(supplier_order_ids)}}]}
```

### Why this is secure:
Using the MongoDB `$and` operator guarantees that the query is strictly limited by the pre-compiled `supplier_skus` and `supplier_order_ids` arrays. If the LLM generates a query like `find_one({"id": 105})` (which might belong to another supplier), the filter becomes:
```json
{
  "$and": [
    { "id": 105 },
    { "order_lines.product_sku": { "$in": [191, 192, ...] } }
  ]
}
```
If `PO #105` does not contain any of their SKUs, MongoDB returns `null` (no results), ensuring complete data isolation.

---

## 6. Fallback and General Question Handling

If the local LLM is offline or fails, or if a user asks a general summary question directly, the fallback handlers intercept it:
- **Order Count Questions:** Reports only the count of orders related to their products.
- **Anomaly Count Questions:** Reports only anomalies related to their orders.
- **KPI Queries:** Responds with a warning indicating that company-wide KPIs are restricted and advises the supplier to check their personal supplier dashboard.

---

*Guide generated: 2026-07-06 | Security & Data Isolation*
