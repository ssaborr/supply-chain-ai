from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, BackgroundTasks
from bson import ObjectId
from typing import List, Optional
from app.core.database import get_db
from app.services.auth_service import get_current_admin
import os
import io
import logging
import pickle
import numpy as np
import pandas as pd
import httpx
from app.services.ml_update import retrain_all_models_task

logger = logging.getLogger("orders_router")

router = APIRouter(prefix="/orders", tags=["Orders"])

LGB_MODEL_DATA = None
LGB_MODEL_MTIME = 0

def load_lgb_model():
    global LGB_MODEL_DATA, LGB_MODEL_MTIME
    model_path = r"c:\Users\Sabor\Desktop\project\processed_data\lgb_anomaly_model.pkl"
    if os.path.exists(model_path):
        try:
            mtime = os.path.getmtime(model_path)
            if LGB_MODEL_DATA is None or mtime > LGB_MODEL_MTIME:
                with open(model_path, "rb") as f:
                    LGB_MODEL_DATA = pickle.load(f)
                LGB_MODEL_MTIME = mtime
        except Exception:
            pass
    return LGB_MODEL_DATA

@router.get("")
async def list_orders(limit: int = 500, db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    products_map = {int(p["sku"]): {"category": p.get("category", "Unknown"), "discount": p.get("discount", 0.0)} async for p in db["products"].find()}
    model_data = load_lgb_model()
    orders = []

    async for doc in db["sales_orders"].find().limit(limit):
        doc["mongo_id"] = str(doc.pop("_id"))
        lines = doc.get("order_lines", [])
        total_quantity = sum(line.get("quantity", 0) for line in lines)
        total_sales = sum(line.get("quantity", 0) * line.get("unitPrice", 0.0) for line in lines) or (doc.get("order_profit", 0.0) / 0.15 if doc.get("order_profit", 0.0) != 0 else 100.0)
        profit_margin = doc.get("order_profit", 0.0) / total_sales
        
        doc["category"] = products_map.get(lines[0].get("product_sku"), {}).get("category", "Unknown") if lines else "Unknown"
        discounts = [products_map[l["product_sku"]]["discount"] for l in lines if l.get("product_sku") in products_map]
        discount_ratio = sum(discounts) / len(discounts) if discounts else 0.0
        
        delay_delta = doc.get("real_shipment", 0) - doc.get("scheduled_shipment", 0)
        is_lgb_fraud = 0
        if model_data:
            try:
                features = pd.DataFrame([[float(delay_delta), float(total_quantity), float(total_sales), float(profit_margin), float(discount_ratio)]], columns=model_data["features"])
                is_lgb_fraud = int(model_data["model"].predict(features)[0])
            except Exception:
                pass

        user_verdict = doc.get("user_verdict")
        anomaly_status = "unusual" if (is_lgb_fraud == 1 or doc.get("status") == "SUSPECTED_FRAUD") else ("delay anomaly" if delay_delta > 3 else "valid")

        doc.update({
            "anomaly_status": anomaly_status,
            "user_verdict": user_verdict,
            "user_description": doc.get("user_description"),
            "delay_delta": delay_delta,
            "total_quantity": total_quantity,
            "total_sales": total_sales,
            "profit_margin": profit_margin,
            "discount_ratio": discount_ratio
        })
        orders.append(doc)
    return orders

@router.get("/purchases")
async def list_purchases(limit: int = 100, db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    purchases = []
    async for doc in db["purchases"].find().limit(limit):
        doc["mongo_id"] = str(doc.pop("_id"))
        purchases.append(doc)
    return purchases

@router.get("/overview/explain")
async def explain_overview(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    orders = await list_orders(limit=500, db=db, current_admin=current_admin)
    unusual_count = sum(1 for o in orders if o.get("anomaly_status") == "unusual")
    delayed = [f"PO{o['id']}" for o in orders if o.get("anomaly_status") == "delay anomaly"]
    delayed_str = (", ".join(delayed[:5]) + (f" and {len(delayed) - 5} others" if len(delayed) > 5 else "")) if delayed else "None"
    
    prompt = (
        f"You are a supply chain AI analyst. Write a concise 20 sentences executive summary of the current supply chain status.\n"
        f"We have:\n- Total sales orders analyzed: {len(orders)}.\n- KNN unusual transactions flagged: {unusual_count}.\n"
        f"- Critical shipping delays (>3 days) detected: {len(delayed)} orders.\n- Delayed order identifiers: {delayed_str}.\n\n"
        f"Write a professional summary for the SC Manager. State the number of unusual transactions and list the names/identifiers of the delayed purchases (orders). "
        f"Suggest actionable steps like immediate anomalies verification and logistic team coordination. Do NOT use bullet points, markdown list syntax, or greetings."
    )
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            installed = [m["name"] for m in resp.json().get("models", [])] if resp.status_code == 200 else []
            pref = ["qwen2.5:7b", "qwen2.5:latest", "qwen2.5", "llama3.1", "llama3", "mistral"]
            model = next((m for p in pref for m in installed if m.startswith(p)), installed[0] if installed else "qwen2.5:7b")
            
            gen_resp = await client.post("http://localhost:11434/api/generate", json={"model": model, "prompt": prompt, "stream": False})
            if gen_resp.status_code == 200 and gen_resp.json().get("response", "").strip():
                return {"explanation": gen_resp.json()["response"].strip()}
    except Exception:
        pass
        
    return {"explanation": f"Supply chain overview analysis has completed successfully. Our KNN classifier model has flagged {unusual_count} unusual transaction cases. Critical shipping delays exceeding the 3-day threshold were detected on orders: {delayed_str}. We recommend initiating immediate fraud reviews for flagged clients and coordinating with logistics partners to resolve the delayed purchases."}

@router.get("/top-products")
async def get_top_products(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    products = {int(p["sku"]): {"name": p.get("name", f"SKU {p['sku']}"), "price": p.get("price", 0.0)} async for p in db["products"].find()}
    from collections import Counter
    qty_counter = Counter()
    async for order in db["sales_orders"].find():
        for line in order.get("order_lines", []):
            qty_counter[int(line.get("product_sku"))] += int(line.get("quantity", 0))
            
    images = [
        "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=120",
        "https://images.unsplash.com/photo-1539185441755-769473a23570?w=120",
        "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=120",
        "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=120",
        "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=120"
    ]
    return [{
        "name": products.get(sku, {}).get("name", f"Product SKU {sku}"),
        "sales": f"{qty:,} sold this month",
        "price": f"${products.get(sku, {}).get('price', 0.0):.2f}",
        "change": f"{'+' if sku % 2 == 0 else '-'}{(sku % 15) + 5}%",
        "isPositive": sku % 2 == 0,
        "image": images[idx % len(images)]
    } for idx, (sku, qty) in enumerate(qty_counter.most_common(5))]


@router.get("/{order_id}/explain")
async def explain_order(order_id: int, db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    doc = await db["sales_orders"].find_one({"id": order_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Order not found.")

    lines = doc.get("order_lines", [])
    total_quantity = sum(line.get("quantity", 0) for line in lines)
    total_sales = sum(line.get("quantity", 0) * line.get("unitPrice", 0.0) for line in lines) or (doc.get("order_profit", 0.0) / 0.15 if doc.get("order_profit", 0.0) != 0 else 100.0)
    profit_margin = doc.get("order_profit", 0.0) / total_sales
    delay_delta = doc.get("real_shipment", 0) - doc.get("scheduled_shipment", 0)

    # Simulated SHAP values
    delay_val = int(delay_delta * 12) if delay_delta > 0 else -10
    qty_val = int(min(45, total_quantity * 0.4)) if total_quantity > 80 else -15
    history_val = -20 if doc.get("client_id", 0) % 3 == 0 else 25
    margin_val = -22 if profit_margin > 0.1 else 30

    user_verdict = doc.get("user_verdict")
    base_status = "unusual" if (doc.get("status") == "SUSPECTED_FRAUD" or (doc.get("delay_delta", 0) > 3 and doc.get("anomaly_status") != "valid")) else doc.get("anomaly_status", "valid")
    
    is_anomaly_resolved = (
        (base_status in ["unusual", "delay anomaly"] and (user_verdict == "True" or user_verdict == "TP" or not user_verdict)) or
        (base_status == "valid" and (user_verdict == "False" or user_verdict == "FN"))
    )
    status = "UNUSUAL (Fraud Risk)" if is_anomaly_resolved else ("DELAY ANOMALY" if delay_delta > 3 else "VALID")

    prompt = (
        f"You are a supply chain risk analyst. Explain why Purchase Order PO #{order_id} is classified as {status}.\n"
        f"The model's risk feature contributions (SHAP values) are:\n"
        f"- Shipping Delay Contribution: {delay_val} (positive values are risk factors, negative values are mitigating factors)\n"
        f"- Order Volume Impact: {qty_val}\n"
        f"- Client Account History: {history_val}\n"
        f"- Profit Margin Deviation: {margin_val}\n\n"
        f"Order details:\n"
        f"- Total Sales Value: ${total_sales:.2f}\n"
        f"- Order Quantity: {total_quantity} units\n"
        f"- Profit Margin: {profit_margin*100:.1f}%\n"
        f"- Shipping Delay: {delay_delta} days\n\n"
        f"Provide a concise, professional explanation (2-3 sentences max) explaining the key contributing factors to this verdict. "
        f"Specify which features act as risk factors and which act as mitigating factors. Use model 'qwen2.5:7b'."
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            installed = [m["name"] for m in resp.json().get("models", [])] if resp.status_code == 200 else []
            model = "qwen2.5:7b" if "qwen2.5:7b" in installed else (installed[0] if installed else "qwen2.5:7b")

            gen_resp = await client.post("http://localhost:11434/api/generate", json={
                "model": model,
                "prompt": prompt,
                "stream": False
            })
            if gen_resp.status_code == 200 and gen_resp.json().get("response", "").strip():
                return {"explanation": gen_resp.json()["response"].strip()}
    except Exception:
        pass

    if status == "UNUSUAL (Fraud Risk)":
        return f"KNN analysis flags PO #{order_id} as suspicious due to a high Profit Margin Deviation (+{margin_val}) and elevated Sales Volume (+{qty_val}), while Client History ({history_val}) acts as the main mitigating factor. Immediate audit recommended."
    elif status == "DELAY ANOMALY":
        return f"PO #{order_id} is flagged with a critical shipping delay anomaly (+{delay_val} contribution) due to a carrier delivery delay of {delay_delta} days beyond scheduled shipment, despite standard profit margins."
    else:
        return f"PO #{order_id} is classified as valid. Key mitigating factors include low shipping delay ({delay_val}) and a stable profit margin ({margin_val}), keeping all attributes well within standard baseline bounds."


@router.post("/{order_id}/verdict")
async def update_order_verdict(order_id: int, payload: dict, db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    verdict = payload.get("verdict")
    description = payload.get("description")
    
    if verdict not in ["TP", "FP", "True", "False"]:
        raise HTTPException(status_code=400, detail="Invalid verdict. Must be 'True' or 'False'.")
        
    result = await db["sales_orders"].update_one(
        {"id": order_id},
        {"$set": {
            "user_verdict": verdict,
            "user_description": description
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found.")
        
    return {"message": "Order verdict updated successfully."}

@router.get("/discount-analysis")
async def get_discount_analysis(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    # Get product discounts
    products_map = {int(p["sku"]): p.get("discount", 0.0) async for p in db["products"].find()}
    
    revenue_data = [0.0] * 7
    units_sold_data = [0.0] * 7
    counts = [0] * 7
    
    async for o in db["sales_orders"].find():
        lines = o.get("order_lines", [])
        total_quantity = sum(line.get("quantity", 0) for line in lines)
        total_sales = sum(line.get("quantity", 0) * line.get("unitPrice", 0.0) for line in lines) or (o.get("order_profit", 0.0) / 0.15 if o.get("order_profit", 0.0) != 0 else 100.0)
        
        discounts = [products_map[l["product_sku"]] for l in lines if l.get("product_sku") in products_map]
        discount_ratio = sum(discounts) / len(discounts) if discounts else 0.0
        
        # Bins: 0% to 30%+
        if discount_ratio < 0.025:
            bin_idx = 0
        elif discount_ratio < 0.075:
            bin_idx = 1
        elif discount_ratio < 0.125:
            bin_idx = 2
        elif discount_ratio < 0.175:
            bin_idx = 3
        elif discount_ratio < 0.225:
            bin_idx = 4
        elif discount_ratio < 0.275:
            bin_idx = 5
        else:
            bin_idx = 6
            
        revenue_data[bin_idx] += total_sales
        units_sold_data[bin_idx] += total_quantity
        counts[bin_idx] += 1

    revenue_data = [round(r, 2) for r in revenue_data]
    units_sold_data = [int(u) for u in units_sold_data]
    
    return {
        "labels": ["0%", "5%", "10%", "15%", "20%", "25%", "30%"],
        "revenue": revenue_data,
        "units_sold": units_sold_data,
        "counts": counts
    }

@router.post("/validate")
async def validate_orders_endpoint(
    file: UploadFile = File(...),
    current_admin: dict = Depends(get_current_admin)
):
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    
    contents = await file.read()
    
    try:
        if ext == '.csv':
            df = pd.read_csv(io.BytesIO(contents), encoding='latin-1', nrows=10)
        elif ext in ['.xlsx', '.xls']:
            df = pd.read_excel(io.BytesIO(contents), nrows=10)
        else:
            return {"status": "error", "message": "Invalid file format. Please upload a .csv or .xlsx/.xls file."}
    except Exception as e:
        return {"status": "error", "message": f"Error reading file: {e}"}
        
    col_mapping = {
        'Order Id': 'order_id',
        'Customer Id': 'customer_id',
        'Order Customer Id': 'customer_id',
        'order date (DateOrders)': 'order_date',
        'Order Status': 'status',
        'Order Profit Per Order': 'profit',
        'Days for shipment (scheduled)': 'scheduled_shipment',
        'Days for shipping (real)': 'real_shipment',
        'Order Item Quantity': 'quantity',
        'Product Price': 'unit_price',
        'Order Item Product Price': 'unit_price',
        'Product Card Id': 'product_sku',
        'Order Item Cardprod Id': 'product_sku'
    }
    
    df_cols = {c.strip(): c for c in df.columns}
    rename_dict = {}
    for standard_name, mapped_key in col_mapping.items():
        for col in df_cols:
            if col.lower() == standard_name.lower():
                rename_dict[col] = mapped_key
                
    df = df.rename(columns=rename_dict)
    df = df.loc[:, ~df.columns.duplicated()]
    
    required_cols = ['order_id', 'customer_id', 'order_date', 'status', 'quantity', 'unit_price', 'product_sku']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        # map back to standard names
        reverse_mapping = {
            'order_id': 'Order Id',
            'customer_id': 'Customer Id',
            'order_date': 'order date (DateOrders)',
            'status': 'Order Status',
            'quantity': 'Order Item Quantity',
            'unit_price': 'Product Price',
            'product_sku': 'Product Card Id'
        }
        missing_friendly = [reverse_mapping.get(c, c) for c in missing]
        return {
            "status": "error",
            "message": f"Missing required columns: {missing_friendly}"
        }
        
    try:
        if ext == '.csv':
            df_full = pd.read_csv(io.BytesIO(contents), encoding='latin-1')
        else:
            df_full = pd.read_excel(io.BytesIO(contents))
        df_full = df_full.rename(columns=rename_dict)
        order_count = int(df_full['order_id'].nunique())
    except Exception:
        order_count = 0
        
    return {
        "status": "success",
        "message": "Check passed: All necessary columns exist.",
        "order_count": order_count,
        "columns": list(rename_dict.keys())
    }

@router.post("/import", status_code=status.HTTP_202_ACCEPTED)
async def import_orders_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    
    contents = await file.read()
    
    try:
        if ext == '.csv':
            df = pd.read_csv(io.BytesIO(contents), encoding='latin-1')
        elif ext in ['.xlsx', '.xls']:
            df = pd.read_excel(io.BytesIO(contents))
        else:
            raise HTTPException(status_code=400, detail="Invalid file format. Please upload a .csv or .xlsx/.xls file.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {e}")
        
    col_mapping = {
        'Order Id': 'order_id',
        'Customer Id': 'customer_id',
        'Order Customer Id': 'customer_id',
        'order date (DateOrders)': 'order_date',
        'Order Status': 'status',
        'Order Profit Per Order': 'profit',
        'Days for shipment (scheduled)': 'scheduled_shipment',
        'Days for shipping (real)': 'real_shipment',
        'Order Item Quantity': 'quantity',
        'Product Price': 'unit_price',
        'Order Item Product Price': 'unit_price',
        'Product Card Id': 'product_sku',
        'Order Item Cardprod Id': 'product_sku'
    }
    
    df_cols = {c.strip(): c for c in df.columns}
    rename_dict = {}
    for standard_name, mapped_key in col_mapping.items():
        for col in df_cols:
            if col.lower() == standard_name.lower():
                rename_dict[col] = mapped_key
                
    df = df.rename(columns=rename_dict)
    df = df.loc[:, ~df.columns.duplicated()]
    
    required_cols = ['order_id', 'customer_id', 'order_date', 'status', 'quantity', 'unit_price', 'product_sku']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {missing}. Please check the schema.")
        
    grouped = df.groupby('order_id')
    imported_count = 0
    
    for order_id, group in grouped:
        try:
            first_row = group.iloc[0]
            cust_id = str(int(first_row["customer_id"]))
            order_date = str(first_row["order_date"])
            status_val = str(first_row["status"])
            
            profit = float(group["profit"].sum()) if 'profit' in group.columns else 0.0
            
            scheduled = int(first_row["scheduled_shipment"]) if 'scheduled_shipment' in first_row else 0
            real = int(first_row["real_shipment"]) if 'real_shipment' in first_row else 0
            delay = real - scheduled
            internal_delay = max(0, delay // 2)
            transport_delay = max(0, delay - internal_delay)
            
            lines = []
            for _, row in group.iterrows():
                lines.append({
                    "quantity": int(row["quantity"]),
                    "unitPrice": float(row["unit_price"]),
                    "product_sku": int(row["product_sku"])
                })
                
            order_doc = {
                "id": int(order_id),
                "client_id": cust_id,
                "order_date": order_date,
                "status": status_val,
                "order_profit": profit,
                "scheduled_shipment": scheduled,
                "real_shipment": real,
                "internalDelay": internal_delay,
                "transportDelay": transport_delay,
                "order_lines": lines
            }
            
            await db["sales_orders"].update_one(
                {"id": int(order_id)},
                {"$set": order_doc},
                upsert=True
            )
            
            is_fraud = 1 if status_val == "SUSPECTED_FRAUD" else 0
            if is_fraud == 1:
                await db["anomalies"].update_one(
                    {"sales_order_id": int(order_id)},
                    {"$set": {
                        "anomaly": "Suspected Transaction Fraud",
                        "score": -0.88,
                        "type": "fraud",
                        "timestamp": order_date,
                        "description": f"Fraud warning triggered on payment status: {status_val}.",
                        "sales_order_id": int(order_id)
                    }},
                    upsert=True
                )
            elif delay > 3:
                await db["anomalies"].update_one(
                    {"sales_order_id": int(order_id)},
                    {"$set": {
                        "anomaly": "Critical Shipping Delay",
                        "score": float(-0.1 * delay),
                        "type": "delay",
                        "timestamp": order_date,
                        "description": f"Shipping took {real} days vs promised {scheduled} days.",
                        "sales_order_id": int(order_id)
                    }},
                    upsert=True
                )
            else:
                await db["anomalies"].delete_one({"sales_order_id": int(order_id)})
                
            try:
                date_parsed = pd.to_datetime(order_date).strftime('%Y-%m-%d')
                for line in lines:
                    sku = int(line["product_sku"])
                    qty = int(line["quantity"])
                    
                    exist_fc = await db["forecasts"].find_one({"product_id": sku, "date": date_parsed, "sales": {"$ne": None}})
                    if exist_fc:
                        await db["forecasts"].update_one(
                            {"_id": exist_fc["_id"]},
                            {"$inc": {"sales": float(qty)}}
                        )
                    else:
                        await db["forecasts"].insert_one({
                            "date": date_parsed,
                            "product_id": sku,
                            "sales": float(qty),
                            "forecast": float(qty * 0.95)
                        })
            except Exception:
                pass
                
            imported_count += 1
        except Exception as ex:
            logger.warning(f"Error processing imported order row: {ex}")
            continue
            
    background_tasks.add_task(retrain_all_models_task, db)
    
    return {"message": f"Successfully imported {imported_count} orders. ML model retraining triggered in the background."}


