from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Optional
from app.core.database import get_db
from app.services.auth_service import get_current_admin
from app.models.product import ProductOut
from app.models.kpi import DemandForecastOut
from app.services.forecast_service import retrain_demand_forecast, generate_forecast_explanation
from app.services.product_service import generate_cluster_summary

router = APIRouter(prefix="/products", tags=["Products"])

RETRAINED_PRODUCTS = set()

@router.get("/clusters/summary")
async def get_clusters_summary(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    return {"summary": await generate_cluster_summary(db)}


@router.get("", response_model=List[ProductOut])
async def list_products(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    products = []
    async for doc in db["products"].find().sort("name", 1):
        try:
            sku = doc.get("sku")
            if sku is None:
                continue
            sku_id = int(sku)
            doc_id_str = str(doc.pop("_id"))
            products.append({**doc, "id": sku_id, "id_str": doc_id_str})
        except Exception:
            continue
    return products

@router.get("/clusters", response_model=List[ProductOut])
async def list_product_clusters(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    products = []
    async for doc in db["products"].find().sort("name", 1):
        try:
            sku = doc.get("sku")
            if sku is None:
                continue
            sku_id = int(sku)
            doc_id_str = str(doc.pop("_id"))
            products.append({**doc, "id": sku_id, "id_str": doc_id_str})
        except Exception:
            continue
    return products

@router.get("/forecasts/aggregate", response_model=List[DemandForecastOut])
async def get_aggregated_forecasts(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    return [{**doc, "id": str(doc.pop("_id"))} async for doc in db["forecasts"].find({"product_id": 0}).sort("date", 1)]

@router.get("/forecasts", response_model=List[DemandForecastOut])
async def list_forecasts(
    background_tasks: BackgroundTasks,
    product_id: Optional[int] = None,
    limit: int = 2000,
    db = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    query = {"product_id": product_id} if product_id is not None else {}
    if product_id is not None and product_id != 0:
        global RETRAINED_PRODUCTS
        if product_id not in RETRAINED_PRODUCTS:
            hist_count = await db["forecasts"].count_documents({"product_id": product_id, "sales": {"$ne": None}})
            if hist_count >= 2:
                RETRAINED_PRODUCTS.add(product_id)
                # Fire-and-forget: return existing data immediately, train in background.
                # The frontend loading state will poll and load the updated flexible forecast in 8s.
                background_tasks.add_task(retrain_demand_forecast, db, product_id)
    return [{**doc, "id": str(doc.pop("_id"))} async for doc in db["forecasts"].find(query).sort("date", 1).limit(limit)]

@router.get("/forecasts/explain")
async def explain_forecast(product_id: int, db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    return {"explanation": await generate_forecast_explanation(db, product_id)}

@router.post("/forecasts/retrain", status_code=status.HTTP_202_ACCEPTED)
async def trigger_retrain(background_tasks: BackgroundTasks, product_id: Optional[int] = None, db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    background_tasks.add_task(retrain_demand_forecast, db, product_id)
    return {"message": f"Prophet model retraining triggered in background for product_id={product_id}."}

@router.get("/discount-revenue")
async def get_discount_revenue(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    # 1. Aggregate revenue by product SKU from sales_orders
    pipeline = [
        {"$unwind": "$order_lines"},
        {"$group": {
            "_id": "$order_lines.product_sku",
            "revenue": {"$sum": {"$multiply": ["$order_lines.quantity", "$order_lines.unitPrice"]}}
        }}
    ]
    
    order_revenues = {}
    async for doc in db["sales_orders"].aggregate(pipeline):
        sku = doc["_id"]
        order_revenues[sku] = doc["revenue"]
        
    # 2. Match with product details
    results = []
    async for p in db["products"].find():
        sku = p.get("sku")
        discount = p.get("discount", 0.0)
        discount_pct = round(discount * 100, 1)
        revenue = order_revenues.get(sku, 0.0)
        
        results.append({
            "product_id": sku,
            "product_name": p.get("name", "Unknown SKU"),
            "discount": discount_pct,
            "revenue": round(revenue, 2)
        })
    return results
