from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Optional
from app.core.database import get_db
from app.services.auth_service import get_current_admin, require_admin_role
from app.models.product import ProductOut
from app.models.kpi import DemandForecastOut
from app.services.forecast_service import retrain_demand_forecast, generate_forecast_explanation
from app.services.product_service import generate_cluster_summary

router = APIRouter(prefix="/products", tags=["Products"])

RETRAINED_PRODUCTS = set()

async def _get_product_query_for_user(db, current_admin: dict) -> dict:
    if current_admin.get("role") != "supplier":
        return {}

    supplier_name = current_admin.get("supplier_name")
    if not supplier_name:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supplier user has no associated company name"
        )

    supplier_skus = set()
    async for purchase in db["purchases"].find({"Supplier": supplier_name}):
        for line in purchase.get("purchase_lines", []):
            sku = line.get("product_sku")
            if sku is not None:
                supplier_skus.add(int(sku))

    return {"sku": {"$in": list(supplier_skus)}}


def _serialize_product(doc: dict) -> Optional[dict]:
    try:
        sku = doc.get("sku")
        if sku is None:
            return None
        sku_id = int(sku)
        doc_id_str = str(doc.pop("_id"))
        return {**doc, "id": sku_id, "id_str": doc_id_str}
    except Exception:
        return None


@router.get("/clusters/summary")
async def get_clusters_summary(language: Optional[str] = None, db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    query = await _get_product_query_for_user(db, current_admin)
    supplier_name = current_admin.get("supplier_name") if current_admin.get("role") == "supplier" else None
    return {"summary": await generate_cluster_summary(db, query, supplier_name, language)}


@router.get("", response_model=List[ProductOut])
async def list_products(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    products = []
    query = await _get_product_query_for_user(db, current_admin)
    async for doc in db["products"].find(query).sort("name", 1):
        product = _serialize_product(doc)
        if product:
            products.append(product)
    return products

@router.get("/clusters", response_model=List[ProductOut])
async def list_product_clusters(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    products = []
    query = await _get_product_query_for_user(db, current_admin)
    async for doc in db["products"].find(query).sort("name", 1):
        product = _serialize_product(doc)
        if product:
            products.append(product)
    return products

@router.get("/forecasts/aggregate", response_model=List[DemandForecastOut])
async def get_aggregated_forecasts(db = Depends(get_db), current_admin: dict = Depends(require_admin_role)):
    return [{**doc, "id": str(doc.pop("_id"))} async for doc in db["forecasts"].find({"product_id": 0}).sort("date", 1)]

@router.get("/forecasts", response_model=List[DemandForecastOut])
async def list_forecasts(
    background_tasks: BackgroundTasks,
    product_id: Optional[int] = None,
    limit: int = 2000,
    db = Depends(get_db),
    current_admin: dict = Depends(require_admin_role)
):
    query = {"product_id": product_id} if product_id is not None else {}
    if product_id is not None and product_id != 0:
        global RETRAINED_PRODUCTS
        if product_id not in RETRAINED_PRODUCTS:
            hist_count = await db["forecasts"].count_documents({"product_id": product_id, "sales": {"$ne": None}})
            if hist_count >= 2:
                RETRAINED_PRODUCTS.add(product_id)
                # Trigger asynchronous model retraining in the background to avoid blocking the API response
                background_tasks.add_task(retrain_demand_forecast, db, product_id)
    return [{**doc, "id": str(doc.pop("_id"))} async for doc in db["forecasts"].find(query).sort("date", 1).limit(limit)]

@router.get("/forecasts/explain")
async def explain_forecast(product_id: int, language: Optional[str] = None, db = Depends(get_db), current_admin: dict = Depends(require_admin_role)):
    return {"explanation": await generate_forecast_explanation(db, product_id, language)}

@router.post("/forecasts/retrain", status_code=status.HTTP_202_ACCEPTED)
async def trigger_retrain(background_tasks: BackgroundTasks, product_id: Optional[int] = None, db = Depends(get_db), current_admin: dict = Depends(require_admin_role)):
    background_tasks.add_task(retrain_demand_forecast, db, product_id)
    return {"message": f"Prophet model retraining triggered in background for product_id={product_id}."}

@router.get("/discount-revenue")
async def get_discount_revenue(db = Depends(get_db), current_admin: dict = Depends(require_admin_role)):
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


from pydantic import BaseModel

class ProductDelaysUpdate(BaseModel):
    prep_delay: int
    internal_delay: int
    transport_delay: int

@router.put("/{sku}/delays")
async def update_product_delays(sku: int, payload: ProductDelaysUpdate, db = Depends(get_db), current_admin: dict = Depends(require_admin_role)):
    result = await db["products"].update_one(
        {"sku": sku},
        {"$set": {
            "prep_delay": payload.prep_delay,
            "internal_delay": payload.internal_delay,
            "transport_delay": payload.transport_delay
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product delays updated successfully"}


from app.services.delay_service import train_delay_model

@router.post("/train-delays")
async def trigger_train_delays(db = Depends(get_db), current_admin: dict = Depends(require_admin_role)):
    res = await train_delay_model(db)
    if res.get("status") == "error":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.get("message"))
    return res
