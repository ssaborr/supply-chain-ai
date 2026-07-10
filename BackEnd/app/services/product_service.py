import httpx
import logging
from fastapi import HTTPException
from app.core.database import get_db

logger = logging.getLogger(__name__)

async def generate_cluster_summary(db) -> str:
    try:
        # helper to aggregate stats (count, price, stock) for a specific product cluster, dude
        async def get_cluster_stats(cluster_name: str):
            pipeline = [
                {"$match": {"cluster": cluster_name}},
                {"$group": {
                    "_id": None,
                    "avg_price": {"$avg": "$price"},
                    "avg_volume": {"$avg": "$monthly_volume"},
                    "count": {"$sum": 1}
                }}
            ]
            cursor = db["products"].aggregate(pipeline)
            results = []
            async for doc in cursor:
                results.append(doc)
            if results:
                return {
                    "avg_price": float(results[0].get("avg_price") or 0.0),
                    "avg_volume": float(results[0].get("avg_volume") or 0.0),
                    "count": int(results[0].get("count") or 0)
                }
            return {"avg_price": 0.0, "avg_volume": 0.0, "count": 0}

        hv = await get_cluster_stats("HIGH VALUE")
        vd = await get_cluster_stats("VOLUME DRIVERS")
        lp = await get_cluster_stats("LOW PERFORMERS")
        
        total_count = hv["count"] + vd["count"] + lp["count"]

        # handle empty db gracefully, dude
        if total_count == 0:
            raise HTTPException(status_code=404, detail="Product clustering data unavailable")

        prompt = (
            f"You are a supply chain inventory analyst. Summarize our K-Means product clustering tier results:\n"
            f"- Total Catalog size: {total_count} products.\n"
            f"- High Value tier: {hv['count']} premium items (avg price ${hv['avg_price']:.2f} each).\n"
            f"- Volume Drivers tier: {vd['count']} items (avg monthly volume {vd['avg_volume']:.0f} units).\n"
            f"- Low Performers tier: {lp['count']} items (avg volume {lp['avg_volume']:.0f} units).\n\n"
            f"Write a concise 2 sentences explanation. Give LLM advice on inventory optimization or SKU rationalization based on these tiers. "
            f"Do not use bullet points, greetings, or markdown list syntax."
        )
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get("http://localhost:11434/api/tags")
                installed = [m["name"] for m in resp.json().get("models", [])] if resp.status_code == 200 else []
                pref = ["qwen2.5:7b", "qwen2.5:latest", "qwen2.5", "llama3.1", "llama3", "mistral"]
                model = next((m for p in pref for m in installed if m.startswith(p)), installed[0] if installed else "qwen2.5:7b")
                
                gen_resp = await client.post("http://localhost:11434/api/generate", json={"model": model, "prompt": prompt, "stream": False})
                if gen_resp.status_code == 200 and gen_resp.json().get("response", "").strip():
                    return gen_resp.json()["response"].strip()
                elif gen_resp.status_code != 200:
                    logger.error("Ollama /api/generate failed for product cluster summary: %s %s", gen_resp.status_code, await gen_resp.text())
                else:
                    logger.error("Ollama returned empty cluster summary response for model %s", model)
        except Exception as exc:
            logger.exception("Ollama request failed for cluster summary: %s", exc)
            raise

        raise HTTPException(status_code=502, detail="Ollama cluster summary generation failed")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating cluster summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to generate clustering summary due to an internal error.")
