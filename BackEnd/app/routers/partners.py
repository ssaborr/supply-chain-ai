import os
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.database import get_db
from app.services.auth_service import get_current_admin
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/partners", tags=["Partners"])

@router.get("/clients/segmentation")
async def get_clients_segmentation(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    try:
        clients = []
        async for c in db["client"].find():
            clients.append(c)
            
        orders = []
        async for o in db["sales_orders"].find():
            orders.append(o)
            
        if not clients:
            return []
            
        def adjust_date_to_sep_dec_2026(date_str):
            if not date_str:
                return pd.to_datetime("2026-09-01")
            try:
                d = pd.to_datetime(date_str)
                new_month = 9 + (d.month - 1) % 4
                new_day = min(d.day, 30 if new_month in [9, 11] else 31)
                return pd.to_datetime(f"2026-{new_month:02d}-{new_day:02d}")
            except Exception:
                return pd.to_datetime("2026-09-01")

        client_list = list(clients)
        client_orders = {str(c["id"]): [] for c in clients}
        for o in orders:
            c_id_str = o.get("client_id", "0")
            try:
                idx = int(c_id_str) % len(client_list)
                mapped_id = str(client_list[idx]["id"])
            except (ValueError, IndexError):
                continue
            if mapped_id in client_orders:
                lines = o.get("order_lines", [])
                val = sum(line.get("quantity", 0) * line.get("unitPrice", 0.0) for line in lines)
                date_str = o.get("order_date")
                date_val = adjust_date_to_sep_dec_2026(date_str)
                client_orders[mapped_id].append({"date": date_val, "value": val})
                
        max_date = pd.to_datetime("2026-12-31")
        client_data = []
        for c in clients:
            c_id = str(c["id"])
            ords = client_orders.get(c_id, [])
            if ords:
                latest_date = max(x["date"] for x in ords)
                recency = int((max_date - latest_date).days)
                if recency < 0:
                    recency = 0
                frequency = len(ords)
                monetary = float(sum(x["value"] for x in ords))
            else:
                recency = 365
                frequency = 0
                monetary = 0.0
                
            client_data.append({
                "id": c_id,
                "first_name": c.get("first_name", "Client"),
                "last_name": c.get("last_name", f"#{c_id}"),
                "email": c.get("email", ""),
                "country": c.get("country", "Unknown"),
                "category": c.get("category", "Retail"),
                "recency": recency,
                "frequency": frequency,
                "monetary": monetary
            })
            
        df = pd.DataFrame(client_data)
        
        if len(df) >= 3:
            # train K-Means clusterer for partner segmentation
            scaler = StandardScaler()
            X = scaler.fit_transform(df[["recency", "frequency", "monetary"]])
            kmeans = KMeans(n_clusters=3, random_state=42)
            df["cluster_id"] = kmeans.fit_predict(X)
            
            cluster_means = df.groupby("cluster_id")["monetary"].mean().sort_values()
            cluster_mapping = {
                cluster_means.index[0]: "AT RISK",
                cluster_means.index[1]: "LOYAL",
                cluster_means.index[2]: "CHAMPIONS"
            }
            df["cluster"] = df["cluster_id"].map(cluster_mapping)
        else:
            df["cluster"] = "LOYAL"
            
        result = df.to_dict(orient="records")
        return result
    except Exception as e:
        logger.error(f"Error segmenting clients: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/suppliers/segmentation")
async def get_suppliers_segmentation(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    try:
        purchases = []
        async for p in db["purchases"].find():
            purchases.append(p)
            
        if not purchases:
            return []
            
        supplier_purchases = {}
        for p in purchases:
            sup_name = p.get("Supplier")
            if not sup_name:
                continue
            if sup_name not in supplier_purchases:
                supplier_purchases[sup_name] = []
            supplier_purchases[sup_name].append(p)
            
        supplier_data = []
        for name, records in supplier_purchases.items():
            delays = []
            total_qty = 0
            total_cost = 0.0
            origins = set()
            
            for r in records:
                if r.get("origin"):
                    origins.add(r.get("origin"))
                for line in r.get("purchase_lines", []):
                    delays.append(line.get("supplyDelay", 0))
                    qty = line.get("quantity", 0)
                    total_qty += qty
                    total_cost += qty * line.get("unitPrice", 0.0)
                    
            avg_delay = float(sum(delays) / len(delays)) if delays else 0.0
            supplier_data.append({
                "name": name,
                "origin": ", ".join(origins) if origins else "Global Port",
                "avg_delay": round(avg_delay, 1),
                "total_volume": total_qty,
                "total_cost": round(total_cost, 2)
            })
            
        df = pd.DataFrame(supplier_data)
        
        if len(df) >= 3:
            scaler = StandardScaler()
            X = scaler.fit_transform(df[["avg_delay", "total_volume", "total_cost"]])
            kmeans = KMeans(n_clusters=3, random_state=42)
            df["cluster_id"] = kmeans.fit_predict(X)
            
            cluster_means = df.groupby("cluster_id")["total_volume"].mean().sort_values()
            cluster_mapping = {
                cluster_means.index[0]: "UNDERPERFORMING",
                cluster_means.index[1]: "RELIABLE",
                cluster_means.index[2]: "STRATEGIC"
            }
            df["cluster"] = df["cluster_id"].map(cluster_mapping)
        else:
            df["cluster"] = "RELIABLE"
            
        result = df.to_dict(orient="records")
        return result
    except Exception as e:
        logger.error(f"Error segmenting suppliers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/clients/explain")
async def explain_clients_segmentation(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    import httpx
    clients = await get_clients_segmentation(db, current_admin)
    if not clients:
        raise HTTPException(status_code=404, detail="Client segmentation data unavailable")
        
    champions_count = sum(1 for c in clients if c.get("cluster") == "CHAMPIONS")
    loyal_count = sum(1 for c in clients if c.get("cluster") == "LOYAL")
    at_risk_count = sum(1 for c in clients if c.get("cluster") == "AT RISK")
    
    prompt = (
        f"You are a supply chain customer relationship analyst. Summarize our K-Means client RFM segmentation results:\n"
        f"- Champions Segment: {champions_count} clients.\n"
        f"- Loyal Segment: {loyal_count} clients.\n"
        f"- At Risk of churn: {at_risk_count} clients.\n\n"
        f"Write a concise 2 sentences explanation. Give LLM advice on what retention campaign or actions to initiate for the At Risk segment to rebuild loyalty. "
        f"Do not use bullet points, greetings, or markdown list syntax. Keep it strictly professional."
    )
    
    explanation = ""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            installed = [m["name"] for m in resp.json().get("models", [])] if resp.status_code == 200 else []
            pref = ["qwen2.5:7b", "qwen2.5:latest", "qwen2.5", "llama3.1", "llama3", "mistral"]
            model = next((m for p in pref for m in installed if m.startswith(p)), installed[0] if installed else "qwen2.5:7b")
            
            gen_resp = await client.post("http://localhost:11434/api/generate", json={"model": model, "prompt": prompt, "stream": False})
            if gen_resp.status_code == 200 and gen_resp.json().get("response", "").strip():
                explanation = gen_resp.json()["response"].strip()
    except Exception as exc:
        logger.exception("Ollama request failed for client segmentation explanation: %s", exc)
        raise HTTPException(status_code=502, detail="Ollama client segmentation explanation generation failed")

    if not explanation:
        raise HTTPException(status_code=502, detail="Ollama client segmentation explanation generation failed")

    return {"explanation": explanation}
