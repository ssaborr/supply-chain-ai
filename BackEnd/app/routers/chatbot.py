from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import httpx
import re
import json
from app.services.auth_service import get_current_admin
from app.core.database import get_db

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])

class ChatRequest(BaseModel):
    message: str

@router.post("/query")
async def query_chatbot(request: ChatRequest, db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    message = request.message.strip()
    message_lower = message.lower()
    
    is_supplier = current_admin.get("role") == "supplier"
    supplier_name = current_admin.get("supplier_name")
    supplier_skus = set()
    supplier_order_ids = set()

    if is_supplier:
        if not supplier_name:
            return {
                "response": "Access Denied: Your user account is not associated with any supplier name. Please contact the administrator."
            }
        
        # 1. Fetch SKUs supplied by this supplier
        async for p in db["purchases"].find({"Supplier": supplier_name}):
            for line in p.get("purchase_lines", []):
                sku = line.get("product_sku")
                if sku is not None:
                    supplier_skus.add(int(sku))
                    
        # 2. Fetch related sales order IDs
        async for o in db["sales_orders"].find({"order_lines.product_sku": {"$in": list(supplier_skus)}}):
            supplier_order_ids.add(int(o["id"]))

    # Special mockup response for PO #41241 (restricted to non-suppliers)
    if "41241" in message and not is_supplier:
        return {
            "response": (
                "PO #41241 is flagged due to a high Anomaly Score (89/100). The Random Forest model detected:\n\n"
                "• **Real shipment date matches order date** (impossible for international cargo).\n"
                "• **Order profit margin is negative** (-15%).\n"
                "• **Client C23312 has 3 other canceled orders** this week."
            )
        }
    
    # Extract order IDs from query (up to 8 digits)
    order_id_match = re.search(r'\b(?:po|order|purchase\s*order)?\s*#?\s*(\d{1,8})\b', message_lower)
    order_id = None
    pre_context = {}
    
    # If no po/order prefix, fallback to standalone number lookup, ignoring timestamps like HH:MM
    if not order_id_match:
        cleaned_msg = re.sub(r'\b\d+:\d+\b', '', message)
        standalone_num = re.search(r'\b\d{1,8}\b', cleaned_msg)
        if standalone_num:
            order_id = int(standalone_num.group(0))
    else:
        order_id = int(order_id_match.group(1))

    # Pre-retrieve context (RAG)
    try:
        if is_supplier:
            # Supplier stats/context only
            pre_context["stats"] = {
                "total_orders": await db["sales_orders"].count_documents({"order_lines.product_sku": {"$in": list(supplier_skus)}}),
                "total_anomalies": await db["anomalies"].count_documents({"sales_order_id": {"$in": list(supplier_order_ids)}}),
                "total_products": await db["products"].count_documents({"sku": {"$in": list(supplier_skus)}}),
            }
            pre_context["supplier_name"] = supplier_name
        else:
            pre_context["stats"] = {
                "total_orders": await db["sales_orders"].count_documents({}),
                "total_anomalies": await db["anomalies"].count_documents({}),
                "total_products": await db["products"].count_documents({}),
                "total_clients": await db["client"].count_documents({}),
                "total_insights": await db["insights"].count_documents({})
            }
            
            kpis_cursor = db["kpis"].find({})
            pre_context["kpis"] = [{"name": k["name"], "value": k["value"], "description": k["description"]} async for k in kpis_cursor]
        
        if order_id is not None:
            # Enforce supplier check on order
            if is_supplier:
                order_data = await db["sales_orders"].find_one({
                    "id": order_id,
                    "order_lines.product_sku": {"$in": list(supplier_skus)}
                })
            else:
                order_data = await db["sales_orders"].find_one({"id": order_id})
                
            if order_data:
                order_data.pop("_id", None)
                pre_context["sales_orders"] = order_data
                
                anoms_cursor = db["anomalies"].find({"sales_order_id": order_id})
                anoms = [a async for a in anoms_cursor]
                for a in anoms:
                    a.pop("_id", None)
                pre_context["anomalies_for_order"] = anoms
                
        sku_match = re.search(r'\bsku\s*#?(\d+)\b', message_lower) or re.search(r'\bproduct\s*#?(\d+)\b', message_lower)
        if sku_match:
            sku_id = int(sku_match.group(1))
            # Enforce supplier check on product
            if is_supplier:
                if sku_id in supplier_skus:
                    prod_data = await db["products"].find_one({"sku": sku_id})
                else:
                    prod_data = None
            else:
                prod_data = await db["products"].find_one({"sku": sku_id})
                
            if prod_data:
                prod_data.pop("_id", None)
                pre_context["product"] = prod_data
                
    except Exception as e:
        pre_context["db_error"] = str(e)

    # ReAct agent system prompt
    if is_supplier:
        system_prompt = (
            f"You are the 'Supplier Portal AI Assistant' for '{supplier_name}'.\n"
            f"You can ONLY access and discuss data directly related to your company's supplier dashboard and your inventory.\n"
            f"You are strictly prohibited from discussing client details, other suppliers, general company-wide KPIs, or overall system metrics.\n\n"
            f"DATABASE SCHEMA & COLLECTIONS:\n"
            f"1. **sales_orders**:\n"
            f"   - Fields: 'id' (int), 'order_date' (str), 'status' (str), 'order_lines' (list of {{'quantity': int, 'unitPrice': float, 'product_sku': int}})\n"
            f"   - Notice: You only have access to sales orders containing products you supply.\n"
            f"2. **anomalies**:\n"
            f"   - Fields: 'anomaly' (str), 'score' (float), 'type' (str), 'description' (str), 'sales_order_id' (int)\n"
            f"   - Notice: You only have access to anomalies linked to your sales orders.\n"
            f"3. **products**:\n"
            f"   - Fields: 'sku' (int), 'name' (str), 'price' (float), 'current_stock' (int)\n"
            f"   - Notice: You only have access to products you supply.\n\n"
            f"HOW TO QUERY THE DATABASE (MCP TOOL CALLING):\n"
            f"If you need to query database collections, write a tool call in the following format:\n"
            f"DB_QUERY: {{\"collection\": \"<collection_name>\", \"operation\": \"find_one\"|\"find_many\"|\"count\", \"filter\": <filter_dict>}}\n"
            f"Ensure any filter strictly restricts results to your supplier scope.\n"
            f"If the user asks for client details, other suppliers, or general KPIs, refuse to answer politely.\n\n"
            f"FINAL ANSWER INSTRUCTIONS:\n"
            f"Keep responses conversational and under 3 sentences. Do not mention client names or other suppliers. "
            f"If the response references a sales order ID, use the markdown link format: [PO #<id>](http://localhost:4200/sales-order?orderId=<id>)."
        )
    else:
        system_prompt = (
            "You are 'Executive AI Assistant', a supply chain database querying agent.\n"
            "You have direct connection tools to query MongoDB to answer user questions.\n\n"
            "DATABASE SCHEMA & COLLECTIONS:\n"
            "1. **sales_orders**:\n"
            "   - Fields: 'id' (int), 'client_id' (str), 'order_date' (str), 'status' (str, e.g., 'CLOSED', 'SUSPECTED_FRAUD'), 'order_profit' (float), 'scheduled_shipment' (int), 'real_shipment' (int), 'order_lines' (list of {'quantity': int, 'unitPrice': float, 'product_sku': int})\n"
            "2. **anomalies**:\n"
            "   - Fields: 'anomaly' (str, name of anomaly), 'score' (float), 'type' (str, 'fraud'|'delay'), 'timestamp' (str), 'description' (str), 'sales_order_id' (int)\n"
            "3. **products**:\n"
            "   - Fields: 'sku' (int), 'name' (str), 'price' (float), 'discount' (float), 'category' (str), 'current_stock' (int)\n"
            "4. **client**:\n"
            "   - Fields: 'id' (str, e.g., '20755'), 'first_name' (str), 'last_name' (str), 'email' (str), 'country' (str), 'rfm_score' (float)\n"
            "5. **kpis**:\n"
            "   - Fields: 'name' (str), 'description' (str), 'value' (float)\n\n"
            "HOW TO QUERY THE DATABASE (MCP TOOL CALLING):\n"
            "If you do not have the database answers in the pre-retrieved data, you MUST write a tool call in the following format on a single line:\n"
            "DB_QUERY: {\"collection\": \"<collection_name>\", \"operation\": \"find_one\"|\"find_many\"|\"count\", \"filter\": <filter_dict>}\n"
            "Do not write any other text when writing a DB_QUERY. Output ONLY the DB_QUERY line and stop.\n\n"
            "Example:\n"
            "User asks: 'anomalies for order 367'\n"
            "You write: DB_QUERY: {\"collection\": \"anomalies\", \"operation\": \"find_many\", \"filter\": {\"sales_order_id\": 367}}\n\n"
            "FINAL ANSWER INSTRUCTIONS:\n"
            "Once you have the database results (either pre-retrieved or after executing DB_QUERY), write a clean, conversational response to the user. "
            "Do not display the DB_QUERY commands to the user. Keep final responses to 3 sentences max. "
            "If the response references a specific sales order ID (e.g. PO 367), you MUST output a markdown link formatted exactly as: [PO #<id>](http://localhost:4200/sales-order?orderId=<id>) so the user can easily open it directly from the chat window."
        )

    prompt = (
        f"{system_prompt}\n\n"
        f"Pre-retrieved Database Context:\n{json.dumps(pre_context)}\n\n"
        f"User Query: {message}"
    )

    llm_response = ""
    model_name = "qwen2.5:7b"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            installed = [m["name"] for m in resp.json().get("models", [])] if resp.status_code == 200 else []
            model_name = "qwen2.5:7b" if "qwen2.5:7b" in installed else (installed[0] if installed else "qwen2.5:7b")
            
            gen_resp = await client.post("http://localhost:11434/api/generate", json={
                "model": model_name,
                "prompt": prompt,
                "stream": False
            })
            if gen_resp.status_code == 200:
                llm_response = gen_resp.json().get("response", "").strip()
    except Exception:
        pass

    # ReAct Loop: Execute requested DB query if present
    if "DB_QUERY:" in llm_response:
        try:
            query_line = [line for line in llm_response.split('\n') if "DB_QUERY:" in line][0]
            json_str = query_line.split("DB_QUERY:", 1)[1].strip()
            query_obj = json.loads(json_str)
            
            collection = query_obj.get("collection")
            operation = query_obj.get("operation", "find_one")
            db_filter = query_obj.get("filter", {})
            
            query_result = None
            
            # Enforce supplier check on DB_QUERY filters
            allowed_collections = ["sales_orders", "anomalies", "products"] if is_supplier else ["sales_orders", "anomalies", "products", "client", "kpis"]
            
            if collection in allowed_collections:
                if is_supplier:
                    if collection == "sales_orders":
                        db_filter = {"$and": [db_filter, {"order_lines.product_sku": {"$in": list(supplier_skus)}}]}
                    elif collection == "products":
                        db_filter = {"$and": [db_filter, {"sku": {"$in": list(supplier_skus)}}]}
                    elif collection == "anomalies":
                        db_filter = {"$and": [db_filter, {"sales_order_id": {"$in": list(supplier_order_ids)}}]}
                
                if operation == "find_one":
                    res = await db[collection].find_one(db_filter)
                    if res:
                        res.pop("_id", None)
                    query_result = res
                elif operation in ["find_many", "find"]:
                    cursor = db[collection].find(db_filter).limit(10)
                    res_list = []
                    async for doc in cursor:
                        doc.pop("_id", None)
                        res_list.append(doc)
                    query_result = res_list
                elif operation == "count":
                    count = await db[collection].count_documents(db_filter)
                    query_result = {"count": count}

                # Step 2: Feed DB results back to LLM for final answer
                second_prompt = (
                    f"{system_prompt}\n\n"
                    f"User Query: {message}\n"
                    f"Executed DB Query: {json_str}\n"
                    f"Database Results: {json.dumps(query_result)}\n\n"
                    f"Now write your final answer to the user based on these database results."
                )
                
                async with httpx.AsyncClient(timeout=20.0) as client:
                    gen_resp = await client.post("http://localhost:11434/api/generate", json={
                        "model": model_name,
                        "prompt": second_prompt,
                        "stream": False
                    })
                    if gen_resp.status_code == 200:
                        return {"response": gen_resp.json().get("response", "").strip()}
            else:
                if is_supplier:
                    return {"response": "Access Denied: You do not have permission to access that data."}
        except Exception:
            pass

    if llm_response and "DB_QUERY:" not in llm_response:
        return {"response": llm_response}

    # Fallback response using pre_context (offline mode / error)
    stats = pre_context.get("stats", {})
    if order_id is not None:
        if "sales_orders" in pre_context:
            o = pre_context["sales_orders"]
            a = pre_context.get("anomalies_for_order", [])
            delay = o.get("real_shipment", 0) - o.get("scheduled_shipment", 0)
            if a:
                anoms_desc = "\n".join([f"• **{item['anomaly']}**: {item['description']} (Score: {item['score']})" for item in a])
                return {
                    "response": (
                        f"Order [PO #{order_id}](http://localhost:4200/sales-order?orderId={order_id}) has the following anomalies flagged in the database:\n\n"
                        f"{anoms_desc}\n\n"
                        f"Details: Profit is **${o.get('order_profit', 0.0):.2f}**, real shipping duration was **{o.get('real_shipment')} days** (promised {o.get('scheduled_shipment')} days)."
                    )
                }
            else:
                return {
                    "response": (
                        f"For [PO #{order_id}](http://localhost:4200/sales-order?orderId={order_id}), no active anomalies are registered in the database. "
                        f"The order profit margin is **${o.get('order_profit', 0.0):.2f}** and shipping delay was **{delay} days**."
                    )
                }
        else:
            return {
                "response": f"I queried the database for PO #{order_id}, but no matching order record was found."
            }
            
    elif "order" in message_lower and ("count" in message_lower or "how many" in message_lower or "total" in message_lower):
        if is_supplier:
            return {
                "response": f"We are currently tracking a total of **{stats.get('total_orders', 0)}** customer sales orders related to your products."
            }
        return {
            "response": f"The database currently records a total of **{stats.get('total_orders', 500)}** sales orders."
        }
    elif "anomaly" in message_lower and ("count" in message_lower or "how many" in message_lower or "total" in message_lower):
        if is_supplier:
            return {
                "response": f"There are **{stats.get('total_anomalies', 0)}** active anomalies flagged across your related sales orders."
            }
        return {
            "response": f"There are **{stats.get('total_anomalies', 54)}** active anomalies flagged across our transactions."
        }
    elif "product" in message_lower and ("count" in message_lower or "how many" in message_lower or "total" in message_lower):
        if is_supplier:
            return {
                "response": f"You currently supply **{stats.get('total_products', 0)}** products tracked in our inventory."
            }
        return {
            "response": f"We are currently tracking **{stats.get('total_products', 118)}** products in stock."
        }
    elif "kpi" in message_lower or "otif" in message_lower:
        if is_supplier:
            return {
                "response": "General company KPIs are restricted. Please refer to your Supplier Dashboard tab for your specific lead time and OTIF metrics."
            }
        kpis_list = pre_context.get("kpis", [])
        if kpis_list:
            kpi_desc = "\n".join([f"• **{k['name']}**: {k['value']}% ({k['description']})" for k in kpis_list])
            return {
                "response": f"Here are the current system KPIs:\n\n{kpi_desc}"
            }
    
    if is_supplier:
        return {
            "response": (
                "I am your Supplier Portal Assistant. You can query me about your specific products "
                "(e.g. 'check stock for SKU 120') or related customer sales orders (e.g. 'details for PO 105')."
            )
        }
    
    return {
        "response": (
            "I have access to database connections. You can query me about orders "
            "(e.g. 'tell me about PO 367' or 'check anomalies for PO 105'), stock levels (e.g. 'check SKU 120'), "
            "or general stats like KPI values and total product counts."
        )
    }
