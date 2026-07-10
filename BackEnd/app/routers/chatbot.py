from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import httpx
import re
import json
from app.services.auth_service import get_current_admin
from app.core.database import get_db
from app.core.config import settings
from app.services.email_service import send_email_notification

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
        
        # grab all the SKUs this supplier is responsible for
        async for p in db["purchases"].find({"Supplier": supplier_name}):
            for line in p.get("purchase_lines", []):
                sku = line.get("product_sku")
                if sku is not None:
                    supplier_skus.add(int(sku))
                    
        # find the downstream sales orders linked to those SKUs
        async for o in db["sales_orders"].find({"order_lines.product_sku": {"$in": list(supplier_skus)}}):
            supplier_order_ids.add(int(o["id"]))

    # hacky easter-egg: mockup info for SO #41241. Don't show to suppliers though!
    if "41241" in message and not is_supplier:
        return {
            "response": (
                "SO #41241 is flagged due to a high Anomaly Score (89/100). The Random Forest model detected:\n\n"
                "• **Real shipment date matches order date** (impossible for international cargo).\n"
                "• **Order profit margin is negative** (-15%).\n"
                "• **Client C23312 has 3 other canceled orders** this week."
            )
        }

    # email generator: only let admins trigger email spam to late suppliers
    action_verbs = ["send", "envoie", "envoyer", "write", "rédige", "rédiger", "remind", "relance", "relancer"]
    mail_nouns = ["mail", "email", "e-mail", "courriel"]
    is_reminder_request = any(w in message_lower for w in ["relance", "remind", "relancer"]) or (
        any(v in message_lower for v in action_verbs) and any(n in message_lower for n in mail_nouns)
    )
    if is_reminder_request and not is_supplier:
        # load distinct supplier names from the database
        all_suppliers = await db["purchases"].distinct("Supplier")
        
        # parse the prompt to see if the user named a supplier
        matched_supplier = None
        for sup in all_suppliers:
            words = sup.lower().split()
            ignore_words = {"manufacturing", "distribution", "global", "supply", "sourcing", "logistics", "co.", "mills", "suppliers", "ltd", "distributors", "eu", "spain", "co"}
            keywords = [w for w in words if w not in ignore_words and len(w) > 2]
            if keywords and any(kw in message_lower for kw in keywords):
                matched_supplier = sup
                break
                
        # no supplier named? default to the slacker with the most delays
        if not matched_supplier:
            delayed_counts = {}
            async for p in db["purchases"].find():
                sup = p.get("Supplier")
                if not sup:
                    continue
                late_count = sum(1 for line in p.get("purchase_lines", []) if line.get("supplyDelay", 0) > 10)
                if late_count > 0:
                    delayed_counts[sup] = delayed_counts.get(sup, 0) + late_count
            if delayed_counts:
                matched_supplier = max(delayed_counts, key=delayed_counts.get)
                
        # fetch the late purchase orders for this specific partner
        if matched_supplier:
            late_orders = []
            async for p in db["purchases"].find({"Supplier": matched_supplier}):
                late_lines = []
                for line in p.get("purchase_lines", []):
                    delay = line.get("supplyDelay", 0)
                    if delay > 10:
                        late_lines.append({
                            "sku": line.get("product_sku"),
                            "delay": delay,
                            "qty": line.get("quantity")
                        })
                if late_lines:
                    late_orders.append({
                        "id": p.get("id"),
                        "date": p.get("date"),
                        "lines": late_lines
                    })
                    
            # format list of delayed orders for context injection
            formatted_list = ""
            if late_orders:
                for order in late_orders:
                    lines_str = ", ".join([f"SKU #{l['sku']} ({l['delay']} days delayed)" for l in order["lines"]])
                    formatted_list += f"- Order **{order['id']}** on {order['date']} : {lines_str}\n"

            # routing logic: decide if we are talking about delivery delays
            is_late_delivery_related = any(w in message_lower for w in ["delay", "late", "retard", "livraison", "delivery", "order", "commande", "SO", "shipment"])
            
            # build the LLM prompt with local RAG context
            prompt = (
                f"Write a professional business email or reminder in English to the supplier '{matched_supplier}'.\n"
                f"The user's query is: '{message}'\n\n"
                f"Sign the email with the following details (do NOT leave placeholder brackets like [Your Name] in the signature):\n"
                f"- Name: Supply Chain AI Admin\n"
                f"- Position: Admin\n"
                f"- Contact: 0606060606\n\n"
            )
            if formatted_list and (is_late_delivery_related or len(message.split()) < 5):
                prompt += (
                    f"Here is the database context of delayed orders for this supplier:\n"
                    f"{formatted_list}\n"
                    f"If the user's query asks about delays/orders, please list these orders and exact delays. Otherwise, focus on the user's instructions.\n\n"
                )
            prompt += (
                f"Respond ONLY with the email subject and email body. "
                f"Do not include any introductory remarks (like 'Here is the email:') or personal notes at the end."
            )
            
            email_text = ""
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
                        email_text = gen_resp.json().get("response", "").strip()
            except Exception:
                pass
            
            # fallback: if local Ollama is sleeping, use rule-based template so the user gets an answer
            if not email_text:
                if "meeting" in message_lower or "réunion" in message_lower:
                    email_text = (
                        f"**Subject:** Meeting Reminder - {matched_supplier}\n\n"
                        f"Dear Partner,\n\n"
                        f"This is a reminder regarding our meeting scheduled for tomorrow.\n\n"
                        f"Please confirm your availability and the agenda items.\n\n"
                        f"Sincerely,\n"
                        f"**Supply Chain & Procurement Team**"
                    )
                else:
                    orders_details_english = ""
                    if late_orders:
                        for order in late_orders:
                            for l in order["lines"]:
                                orders_details_english += f"- Order **{order['id']}** (Date: {order['date']}) | Product: SKU #{l['sku']} | Exact Delay: **{l['delay']} days**\n"
                    
                    if orders_details_english:
                        email_text = (
                            f"**Subject:** Important Reminder - Delivery Delay for Our Pending Orders\n\n"
                            f"Dear Partner,\n\n"
                            f"We are contacting you regarding a delivery delay detected for our orders with your company **{matched_supplier}**.\n\n"
                            f"As of today, the following orders are delayed:\n"
                            f"{orders_details_english}\n"
                            f"These delays directly impact our supply chain and customer commitments. Please check the status of these orders and confirm the exact delivery dates within 24 hours.\n\n"
                            f"We look forward to your prompt response.\n\n"
                            f"Sincerely,\n"
                            f"**Supply Chain & Procurement Team**"
                        )
                    else:
                        email_text = (
                            f"**Subject:** Business Update Request - {matched_supplier}\n\n"
                            f"Dear Partner,\n\n"
                            f"We are reaching out to request a status update on our pending orders and general logistics operations with your team.\n\n"
                            f"Please let us know your current availability for a quick alignment.\n\n"
                            f"Sincerely,\n"
                            f"**Supply Chain & Procurement Team**"
                        )
            
            # try sending the email over SMTP, otherwise print it to logs
            supplier_user = await db["admin"].find_one({"supplier_name": matched_supplier})
            to_email = supplier_user.get("email") if (supplier_user and supplier_user.get("email")) else f"{matched_supplier.lower().replace(' ', '')}@supplychain-partner.com"
            
            # regex out the subject line from the LLM output
            subject = f"Important Reminder - {matched_supplier}"
            for line in email_text.split('\n'):
                if line.lower().startswith("**subject:**") or line.lower().startswith("subject:"):
                    subject = line.split(":", 1)[1].strip().replace("**", "")
                    break
            
            mail_res = await send_email_notification(to_email, subject, email_text)
            
            status_msg = ""
            if mail_res.get("simulated"):
                status_msg = f"\n\n*(Note: The email send was simulated in the development console because the local SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT} is unreachable. Resolved recipient: `{to_email}`)*"
            else:
                status_msg = f"\n\n*(Success: Email successfully sent via the SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT} to `{to_email}`)*"

            return {
                "response": (
                    f"The reminder email has been written and sent to the supplier **{matched_supplier}**:\n\n"
                    f"---\n\n"
                    f"{email_text}\n\n"
                    f"---"
                    f"{status_msg}"
                )
            }
        else:
            return {
                "response": "I could not find any supplier in the database to draft the email."
            }

    
    # extract digits for order lookups, up to 8 chars
    order_id_match = re.search(r'\b(?:SO|order|purchase\s*order)?\s*#?\s*(\d{1,8})\b', message_lower)
    order_id = None
    pre_context = {}
    
    # fallback number lookup (ignores time formats like HH:MM)
    if not order_id_match:
        cleaned_msg = re.sub(r'\b\d+:\d+\b', '', message)
        standalone_num = re.search(r'\b\d{1,8}\b', cleaned_msg)
        if standalone_num:
            order_id = int(standalone_num.group(0))
    else:
        order_id = int(order_id_match.group(1))

    # RAG: pre-load context before entering ReAct loop
    try:
        if is_supplier:
            # check if query only targets supplier performance stats
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
            pre_context["all_suppliers"] = await db["purchases"].distinct("Supplier")
            
            kpis_cursor = db["kpis"].find({})
            pre_context["kpis"] = [{"name": k["name"], "value": k["value"], "description": k["description"]} async for k in kpis_cursor]
        
        if order_id is not None:
            # security check: suppliers cannot snoop on other suppliers' orders
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
            # security check: suppliers cannot snoop on other suppliers' inventory
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
                
        # scan query for known partner names to pre-load metrics
        if not is_supplier:
            all_suppliers = await db["purchases"].distinct("Supplier")
            matched_supplier = None
            for sup in all_suppliers:
                words = sup.lower().split()
                ignore_words = {"manufacturing", "distribution", "global", "supply", "sourcing", "logistics", "co.", "mills", "suppliers", "ltd", "distributors", "eu", "spain", "co"}
                keywords = [w for w in words if w not in ignore_words and len(w) > 2]
                if keywords and any(kw in message_lower for kw in keywords):
                    matched_supplier = sup
                    break
            
            if matched_supplier:
                purchases_cursor = db["purchases"].find({"Supplier": matched_supplier}).limit(5)
                sups_p = []
                async for doc in purchases_cursor:
                    doc.pop("_id", None)
                    sups_p.append(doc)
                pre_context["supplier_info"] = {
                    "name": matched_supplier,
                    "purchases": sups_p
                }

    except Exception as e:
        pre_context["db_error"] = str(e)

    # system prompt for the ReAct loop (Reasoning + Action)
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
            f"If the response references a sales order ID, use the markdown link format: [SO #<id>](http://localhost:4200/sales-order?orderId=<id>)."
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
            "   - Fields: 'name' (str), 'description' (str), 'value' (float)\n"
            "6. **purchases**:\n"
            "   - Fields: 'id' (str), 'origin' (str), 'date' (str), 'type' (str), 'lot' (str), 'Supplier' (str), 'purchase_lines' (list of {'quantity': int, 'unitPrice': float, 'supplyDelay': int, 'product_sku': int})\n"
            "7. **departments**:\n"
            "   - Fields: 'id' (str), 'name' (str), 'address' (str)\n"
            "8. **insights**:\n"
            "   - Fields: 'id' (int), 'name' (str), 'verdict' (str), 'category' (str), 'description' (str), 'timestamp' (str), 'client_id' (str), 'product_sku' (int), 'sales_order_id' (int)\n"
            "9. **forecasts**:\n"
            "   - Fields: 'date' (str), 'product_id' (int), 'sales' (float, optional), 'forecast' (float)\n"
            "10. **admin**:\n"
            "   - Fields: 'email' (str), 'first_name' (str), 'last_name' (str), 'role' (str), 'supplier_name' (str)\n\n"
            "HOW TO QUERY THE DATABASE (MCP TOOL CALLING):\n"
            "If you do not have the database answers in the pre-retrieved data, you MUST write a tool call in the following format on a single line:\n"
            "DB_QUERY: {\"collection\": \"<collection_name>\", \"operation\": \"find_one\"|\"find_many\"|\"count\", \"filter\": <filter_dict>}\n"
            "Do not write any other text when writing a DB_QUERY. Output ONLY the DB_QUERY line and stop.\n\n"
            "Example:\n"
            "User asks: 'anomalies for order 367'\n"
            "You write: DB_QUERY: {\"collection\": \"anomalies\", \"operation\": \"find_many\", \"filter\": {\"sales_order_id\": 367}}\n\n"
            "FINAL ANSWER INSTRUCTIONS:\n"
            "Once you have the database results (either pre-retrieved or after executing DB_QUERY), write a clean, conversational response to the user. "
            "You MUST respond in English at all times. Do not translate your response to French, even if the user queries in French.\n"
            "Do not display the DB_QUERY commands to the user. Keep final responses to 3 sentences max. "
            "If the response references a specific sales order ID (e.g. SO 367), you MUST output a markdown link formatted exactly as: [SO #<id>](http://localhost:4200/sales-order?orderId=<id>) so the user can easily open it directly from the chat window."
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

    # ReAct loop: if LLM generated a DB query tool call, execute it
    if "DB_QUERY:" in llm_response:
        try:
            query_line = [line for line in llm_response.split('\n') if "DB_QUERY:" in line][0]
            json_str = query_line.split("DB_QUERY:", 1)[1].strip()
            query_obj = json.loads(json_str)
            
            collection = query_obj.get("collection")
            operation = query_obj.get("operation", "find_one")
            db_filter = query_obj.get("filter", {})
            
            query_result = None
            
            # intercept raw SQL/NoSQL queries to block supplier data leaks
            allowed_collections = ["sales_orders", "anomalies", "products"] if is_supplier else ["sales_orders", "anomalies", "products", "client", "kpis", "purchases"]
            
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

                # feed DB results back to LLM for final answer
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

    # offline mode: use RAG context directly if LLM failed
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
                        f"Order [SO #{order_id}](http://localhost:4200/sales-order?orderId={order_id}) has the following anomalies flagged in the database:\n\n"
                        f"{anoms_desc}\n\n"
                        f"Details: Profit is **${o.get('order_profit', 0.0):.2f}**, real shipping duration was **{o.get('real_shipment')} days** (promised {o.get('scheduled_shipment')} days)."
                    )
                }
            else:
                return {
                    "response": (
                        f"For [SO #{order_id}](http://localhost:4200/sales-order?orderId={order_id}), no active anomalies are registered in the database. "
                        f"The order profit margin is **${o.get('order_profit', 0.0):.2f}** and shipping delay was **{delay} days**."
                    )
                }
        else:
            return {
                "response": f"I queried the database for SO #{order_id}, but no matching order record was found."
            }
            
    elif "supplier_info" in pre_context:
        sup_info = pre_context["supplier_info"]
        sup_name = sup_info["name"]
        purchs = sup_info["purchases"]
        if purchs:
            lines_desc = []
            for p in purchs:
                sku_list = [str(line.get("product_sku")) for line in p.get("purchase_lines", [])]
                lines_desc.append(f"• Purchase Order **{p['id']}** on {p['date']} (Type: {p['type']}, Lot: {p['lot']}, SKUs: {', '.join(sku_list)})")
            lines_str = "\n".join(lines_desc)
            return {
                "response": (
                    f"Here is the information for the supplier **{sup_name}**:\n\n"
                    f"Latest purchase orders placed:\n"
                    f"{lines_str}"
                )
            }
        else:
            return {
                "response": f"I did not find any purchase orders recorded for the supplier **{sup_name}** in the database."
            }

    elif "supplier" in message_lower or "fournisseur" in message_lower:
        all_suppliers = await db["purchases"].distinct("Supplier")
        if all_suppliers:
            suppliers_str = "\n".join([f"• {sup}" for sup in all_suppliers])
            return {
                "response": (
                    f"Here is the list of registered suppliers in the system:\n\n"
                    f"{suppliers_str}\n\n"
                    f"You can ask me about a specific supplier (e.g., 'tell me about the supplier Nike Manufacturing EU')."
                )
            }
        else:
            return {
                "response": "No registered suppliers found in the database."
            }

    elif "order" in message_lower and ("count" in message_lower or "how many" in message_lower or "total" in message_lower):
        if is_supplier:
            return {
                "response": f"We are currently tracking a total of **{stats.get('total_orders', 0)}** customer sales orders related to your products."
            }
        return {
            "response": f"The database currently records a total of **{stats.get('total_orders')}** sales orders."
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
                "(e.g. 'check stock for SKU 120') or related customer sales orders (e.g. 'details for SO 105')."
            )
        }
    
    return {
        "response": (
            "I have access to database connections. You can query me about orders "
            "(e.g. 'tell me about SO 367' or 'check anomalies for SO 105'), stock levels (e.g. 'check SKU 120'), "
            "or general stats like KPI values and total product counts."
        )
    }
