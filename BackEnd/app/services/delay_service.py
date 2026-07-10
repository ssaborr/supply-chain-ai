import logging
import numpy as np
from sklearn.linear_model import LinearRegression

logger = logging.getLogger("delay_service")

async def train_delay_model(db):
    logger.info("Starting delay prediction model training using Linear Regression...")
    
    products = []
    async for p in db["products"].find():
        products.append(p)
        
    if not products:
        logger.warning("No products found in DB. Skipping training.")
        return {"status": "error", "message": "No products found in database"}
        
    products_map = {int(p["sku"]): p for p in products}
    
    # Retrieve all historical sales orders to use as training samples for the regression models
    orders = []
    async for o in db["sales_orders"].find():
        orders.append(o)
        
    if not orders:
        logger.warning("No sales orders found in DB. Skipping training.")
        return {"status": "error", "message": "No sales orders found in database"}
        
    X_data = []
    y_prep = []
    y_internal = []
    y_transport = []
    
    for o in orders:
        lines = o.get("order_lines", [])
        if not lines:
            continue
            
        preps = []
        internals = []
        transports = []
        
        for line in lines:
            sku = int(line.get("product_sku"))
            prod = products_map.get(sku)
            if prod:
                p_val = prod.get("prep_delay")
                i_val = prod.get("internal_delay")
                t_val = prod.get("transport_delay")
                preps.append(4 if p_val is None else p_val)
                internals.append(0 if i_val is None else i_val)
                transports.append(0 if t_val is None else t_val)
                
        if not preps:
            continue
            
        max_prep = max(preps)
        max_internal = max(internals)
        max_transport = max(transports)
        
        X_data.append([max_prep, max_internal, max_transport])
        
        y_prep.append(o.get("scheduled_shipment", 4))
        y_internal.append(o.get("internalDelay", 0))
        y_transport.append(o.get("transportDelay", 0))
        
    if len(X_data) < 2:
        logger.warning("Insufficient data to train Linear Regression model.")
        return {"status": "error", "message": "Insufficient sales order data to train model"}
        
    X_arr = np.array(X_data)
    
    model_prep = LinearRegression().fit(X_arr, y_prep)
    model_internal = LinearRegression().fit(X_arr, y_internal)
    model_transport = LinearRegression().fit(X_arr, y_transport)
    
    updated_count = 0
    for p in products:
        sku = int(p["sku"])
        current_prep = p.get("prep_delay")
        current_internal = p.get("internal_delay")
        current_transport = p.get("transport_delay")
        
        current_prep = 4 if current_prep is None else current_prep
        current_internal = 0 if current_internal is None else current_internal
        current_transport = 0 if current_transport is None else current_transport
        
        features = np.array([[current_prep, current_internal, current_transport]])
        pred_prep = model_prep.predict(features)[0]
        pred_internal = model_internal.predict(features)[0]
        pred_transport = model_transport.predict(features)[0]
        
        rec_prep = int(max(0, round(pred_prep)))
        rec_internal = int(max(0, round(pred_internal)))
        rec_transport = int(max(0, round(pred_transport)))
        
        await db["products"].update_one(
            {"sku": sku},
            {"$set": {
                "rec_prep_delay": rec_prep,
                "rec_internal_delay": rec_internal,
                "rec_transport_delay": rec_transport
            }}
        )
        updated_count += 1
        
    logger.info(f"Successfully retrained Linear Regression model and updated delay recommendations for {updated_count} products.")
    return {"status": "success", "message": f"Successfully retrained delay prediction model. Updated {updated_count} products."}
