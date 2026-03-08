# webhook_server.py
# ─────────────────────────────────────────────────────────────────────────────
# Fan360 — HTTP webhook receiver for Fabric Activator
# Fabric Activator fires POST /webhook when a fan event is detected
# This server receives it and triggers the full orchestrator pipeline
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn, json, logging, os, asyncio, concurrent.futures
from orchestrator import run_orchestrator
from event_bus import push_event, subscribe, unsubscribe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fan360-webhook")

app = FastAPI(title="Fan360 Webhook Server")

# ── CORS — React dev server needs this ────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Thread pool for running blocking orchestrator in async context ─────────────
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


# ── SSE endpoint — React UI subscribes here ──────────────────────────────────
@app.get("/events")
async def event_stream():
    """Server-Sent Events endpoint — React UI subscribes here"""
    client_q = subscribe()
    async def generate():
        try:
            heartbeat_count = 0
            while True:
                try:
                    event = client_q.get_nowait()
                    yield f"data: {event}\n\n"
                    heartbeat_count = 0
                except:
                    heartbeat_count += 1
                    if heartbeat_count >= 30:    # heartbeat every ~15s
                        yield f"data: {{}}\n\n"
                        heartbeat_count = 0
                    await asyncio.sleep(0.5)
        finally:
            unsubscribe(client_q)
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/status")
def get_status():
    return {
        "system": "Fan360 Multi-Agent System",
        "agents": [
            "Orchestrator", "ChurnAgent", "PersonalisationAgent",
            "RecommendationAgent", "SegmentationAgent", "SponsorMatchingAgent",
        ],
        "status": "online",
    }

@app.get("/health")
def health():
    return {"status": "ok", "service": "Fan360 Webhook Server"}

@app.post("/webhook")
async def receive_webhook(request: Request):
    try:
        body = await request.json()
        logger.info(f"📨 Webhook received: {json.dumps(body, indent=2)}")

        # Fabric Activator payload shape:
        # {
        #   "fan_id":         "FAN-d65867e0",
        #   "event_type":     "ChurnDrop",
        #   "trigger_source": "FabricActivator",
        #   "context":        {}
        # }

        fan_id     = body.get("fan_id")
        event_type = body.get("event_type", "ChurnDrop")

        if not fan_id:
            raise HTTPException(status_code=400, detail="fan_id is required")

        payload = {
            "fan_id":         fan_id,
            "event_type":     event_type,
            "trigger_source": "FabricActivator",
            "context":        body.get("context", {})
        }

        logger.info(f"🚀 Triggering orchestrator for {fan_id}...")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, run_orchestrator, payload)

        logger.info(f"✅ Pipeline complete for {fan_id}")
        return JSONResponse(status_code=200, content=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/test")
async def test_webhook(request: Request):
    """
    Test endpoint — call this manually to simulate a Fabric Activator event
    curl -X POST http://localhost:8000/webhook/test \
         -H "Content-Type: application/json" \
         -d '{"fan_id": "FAN-d65867e0", "event_type": "ChurnDrop"}'
    """
    return await receive_webhook(request)

if __name__ == "__main__":
    port = int(os.environ.get("WEBHOOK_PORT", 8000))
    uvicorn.run("webhook_server:app", host="0.0.0.0", port=port, reload=False)
