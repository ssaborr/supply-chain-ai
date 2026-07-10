import os
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.database import get_db
from app.services.auth_service import get_current_admin
import httpx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/supplier", tags=["Supplier"])

@router.get("/list", response_model=List[str])
async def list_suppliers(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    try:
        # grab supplier names from purchase history
        suppliers = await db["purchases"].distinct("Supplier")
        return [s for s in suppliers if s]
    except Exception as e:
        logger.error(f"Error listing suppliers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard-data")
async def get_supplier_dashboard_data(
    supplier_name: Optional[str] = None,
    db = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    try:
        user_role = current_admin.get("role")
        user_supplier_name = current_admin.get("supplier_name")
        
        # security: supplier users only view their own stats, dude
        if user_role == "supplier":
            if user_supplier_name:
                supplier_name = user_supplier_name
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Supplier user has no associated company name"
                )
        elif not supplier_name:
            # admin fallback for testing supplier view
            all_sups = await db["purchases"].distinct("Supplier")
            supplier_name = all_sups[0] if all_sups else "Nike Manufacturing EU"

        purchases = []
        async for p in db["purchases"].find({"Supplier": supplier_name}):
            purchases.append(p)

        supplier_skus = set()
        for p in purchases:
            for line in p.get("purchase_lines", []):
                sku = line.get("product_sku")
                if sku is not None:
                    supplier_skus.add(int(sku))

        # compute avg supply lead time for active items
        delays = []
        for p in purchases:
            for line in p.get("purchase_lines", []):
                delays.append(line.get("supplyDelay", 0))
        avg_lead_time = float(sum(delays) / len(delays)) if delays else 10.0

        products = []
        low_stock_items = []
        low_stock_count = 0

        async for prod in db["products"].find({"sku": {"$in": list(supplier_skus)}}):
            sku = prod.get("sku")
            prod["_id"] = str(prod["_id"])
            
            # calculate safety stock levels based on lead time variance
            prod_lead_times = []
            for p in purchases:
                for line in p.get("purchase_lines", []):
                    if line.get("product_sku") == sku:
                        prod_lead_times.append(line.get("supplyDelay", 0))
                        
            L = float(sum(prod_lead_times) / len(prod_lead_times)) if prod_lead_times else avg_lead_time
            if L <= 0:
                L = 10.0
                
            # get historical daily demand variance
            demand_sales = []
            async for f in db["forecasts"].find({"product_id": sku}):
                val = f.get("sales") if f.get("sales") is not None else f.get("forecast")
                if val is not None:
                    demand_sales.append(val)
                    
            if demand_sales:
                n_points = len(demand_sales)
                mean_d = sum(demand_sales) / n_points
                var_d = sum((x - mean_d) ** 2 for x in demand_sales) / n_points
                std_d = var_d ** 0.5
            else:
                mean_d = 15.0
                std_d = 4.0
                
            # Z-score = 1.65 to ensure 95% service rate against stockouts
            Z = 1.65
            safety_stock = int(round(Z * std_d * (L ** 0.5)))
            safety_stock = max(15, safety_stock)  # minimum threshold floor
            
            reorder_point = int(round(safety_stock + (mean_d * L)))
            current_stock = prod.get("current_stock", 0)
            
            target_stock = int(round(safety_stock + 2.0 * mean_d * L))
            suggested_reorder = max(0, target_stock - current_stock)
            
            prod.update({
                "safety_stock": safety_stock,
                "reorder_point": reorder_point,
                "mean_demand": round(mean_d, 2),
                "std_demand": round(std_d, 2),
                "lead_time": round(L, 1),
                "suggested_reorder": suggested_reorder
            })
            products.append(prod)
            
            if current_stock < reorder_point:
                low_stock_items.append({
                    "sku": sku,
                    "name": prod.get("name"),
                    "price": prod.get("price"),
                    "current_stock": current_stock,
                    "safety_stock": safety_stock,
                    "reorder_point": reorder_point,
                    "suggested_reorder": suggested_reorder
                })
                low_stock_count += 1

        # check outgoing orders containing supplier products
        sales_orders = []
        async for order in db["sales_orders"].find({"order_lines.product_sku": {"$in": list(supplier_skus)}}):
            order["mongo_id"] = str(order.pop("_id"))
            
            lines = order.get("order_lines", [])
            total_quantity = sum(line.get("quantity", 0) for line in lines)
            total_sales = sum(line.get("quantity", 0) * line.get("unitPrice", 0.0) for line in lines) or (order.get("order_profit", 0.0) / 0.15 if order.get("order_profit", 0.0) != 0 else 100.0)
            profit_margin = order.get("order_profit", 0.0) / total_sales
            
            delay_delta = order.get("real_shipment", 0) - order.get("scheduled_shipment", 0)
            anomaly_status = "unusual" if order.get("status") == "SUSPECTED_FRAUD" else ("delay anomaly" if delay_delta > 3 else "valid")
            
            order.update({
                "anomaly_status": anomaly_status,
                "delay_delta": delay_delta,
                "total_quantity": total_quantity,
                "total_sales": total_sales,
                "profit_margin": profit_margin
            })
            sales_orders.append(order)

        # calculate OTIF rate and lead times for supplier
        total_volume_supplied = 0
        total_supply_cost = 0.0
        on_time_count = 0
        total_purchase_lines = 0

        for p in purchases:
            for line in p.get("purchase_lines", []):
                delay = line.get("supplyDelay", 0)
                qty = line.get("quantity", 0)
                total_volume_supplied += qty
                total_supply_cost += qty * line.get("unitPrice", 0.0)
                total_purchase_lines += 1
                if delay <= 12:  # 12 days on-time threshold
                    on_time_count += 1

        otif_rate = float(on_time_count / total_purchase_lines * 100) if total_purchase_lines > 0 else 100.0

        total_sales_revenue = 0.0
        total_sales_volume = 0
        for o in sales_orders:
            for line in o.get("order_lines", []):
                if int(line.get("product_sku")) in supplier_skus:
                    qty = line.get("quantity", 0)
                    total_sales_volume += qty
                    total_sales_revenue += qty * line.get("unitPrice", 0.0)

        low_stock_items = [{k: v for k, v in item.items() if k != "_id"} for item in low_stock_items]

        # build AI recommendation context for supplier dashboard
        prompt = (
            f"You are a supply chain operations coordinator. Write a brief executive summary reviewing supplier '{supplier_name}' performance:\n"
            f"- Average Lead Time: {avg_lead_time:.1f} days.\n"
            f"- On-Time In-Full (OTIF) Rate: {otif_rate:.1f}%.\n"
            f"- Total Volume Supplied: {total_volume_supplied} units.\n"
            f"- Products with Low Stock (<120 units): {len(low_stock_items)}.\n"
            f"- Downstream customer sales orders related to their products: {len(sales_orders)} orders.\n\n"
            f"Write a concise professional summary (3-4 sentences) directly addressing the supplier. Tell them how their delay affects downstream deliveries, and advise them on what low-stock items to restock immediately. "
            f"Keep it strictly professional. Do not use bullet points or markdown list syntax."
        )

        ai_explanation = ""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get("http://localhost:11434/api/tags")
                installed = [m["name"] for m in resp.json().get("models", [])] if resp.status_code == 200 else []
                pref = ["qwen2.5:7b", "qwen2.5:latest", "qwen2.5", "llama3.1", "llama3", "mistral"]
                model = next((m for p in pref for m in installed if m.startswith(p)), installed[0] if installed else "qwen2.5:7b")
                
                gen_resp = await client.post("http://localhost:11434/api/generate", json={"model": model, "prompt": prompt, "stream": False})
                if gen_resp.status_code == 200 and gen_resp.json().get("response", "").strip():
                    ai_explanation = gen_resp.json()["response"].strip()
        except Exception:
            pass

        if not ai_explanation:
            low_stock_names = ", ".join([p.get("name") for p in low_stock_items[:3]])
            stock_msg = f" (specifically {low_stock_names})" if low_stock_items else ""
            ai_explanation = (
                f"Dear Partner, your operational performance for {supplier_name} shows a reliable On-Time In-Full (OTIF) rate of {otif_rate:.1f}% with an average lead time of {avg_lead_time:.1f} days. "
                f"Currently, there are {len(sales_orders)} active downstream customer sales orders reliant on your products. "
                f"We have detected {len(low_stock_items)} products approaching critical stock levels{stock_msg}. "
                f"Please coordinate with our logistics team and prioritize replenishment shipments for these items to avoid customer order delays."
            )

        return {
            "supplier_name": supplier_name,
            "kpis": {
                "avg_lead_time": round(avg_lead_time, 1),
                "otif_rate": round(otif_rate, 1),
                "total_volume_supplied": total_volume_supplied,
                "total_supply_cost": round(total_supply_cost, 2),
                "total_sales_revenue": round(total_sales_revenue, 2),
                "total_sales_volume": total_sales_volume,
                "sales_orders_count": len(sales_orders),
                "low_stock_count": len(low_stock_items)
            },
            "sales_orders": sales_orders,
            "products": products,
            "low_stock_items": [{k: v for k, v in p.items() if k != "_id"} for p in low_stock_items],
            "ai_explanation": ai_explanation
        }
    except Exception as e:
        logger.error(f"Error compiling supplier dashboard data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))