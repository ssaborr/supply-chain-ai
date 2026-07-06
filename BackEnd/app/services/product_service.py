import httpx
import logging
from app.core.database import get_db

logger = logging.getLogger(__name__)

async def generate_cluster_summary(db) -> str:
    try:
        # Helper to get statistics for a specific cluster
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

        # If database is completely empty
        if total_count == 0:
            return "No product clustering data available. Please run the K-Means training script."

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
        except Exception:
            pass

        # Fallback rule-based summary
        return (
            f"K-Means clustering has segmented our catalog of {total_count} products into three distinct performance tiers. "
            f"The High Value tier contains {hv['count']} premium items averaging ${hv['avg_price']:.2f} each. "
            f"The Volume Drivers tier is comprised of {vd['count']} high-turnover products averaging {vd['avg_volume']:.0f} units per month, "
            f"which are critical for cash flow. The remaining {lp['count']} low performing products average only {lp['avg_volume']:.0f} units in volume, "
            f"representing candidates for inventory optimization or SKU rationalization."
        )

    except Exception as e:
        logger.error(f"Error generating cluster summary: {e}", exc_info=True)
        return "Unable to generate clustering summary due to an internal error."
