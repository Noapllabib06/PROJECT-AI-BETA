"""FastAPI Application and REST/WebSocket Gateway for JARVIS Agent.

Provides HTTP REST endpoints and real-time WebSocket communication for UI and external clients.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from config.settings import settings, get_logger
from src.agents.base_agent import ToolCall
from src.workflows.orchestrator import orchestrator, JarvisOrchestrator
from src.game_copilot.core.event_bus import event_bus, GameEvent
from src.game_copilot.core.raphael_brain import RaphaelBrain

logger = get_logger("API")

app = FastAPI(
    title="JARVIS AI Agent API",
    version="2.0.0",
    description="Modular Python Agent Architecture for JARVIS"
)

# Enable CORS for local GUI development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== DATA MODELS ====================

class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    image_base64: Optional[str] = None


class ChatResponse(BaseModel):
    success: bool
    response: str
    conversation_id: str
    tools_used: List[str] = Field(default_factory=list)
    traces: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class ToolExecuteRequest(BaseModel):
    tool_name: str
    args: Dict[str, Any] = Field(default_factory=dict)


class ConfirmSaveRequest(BaseModel):
    filename: str
    content: str


# ==================== HEALTH & SETTINGS ====================

@app.get("/health")
async def health_check():
    """Service health and status report."""
    active_model = getattr(orchestrator.base_agent, "model_name", settings.llm.default_model)
    return {
        "status": "ok",
        "app": "JARVIS Python Agent",
        "version": "2.0.0",
        "model": active_model,
        "tools_registered": len(orchestrator.tool_definitions)
    }


@app.get("/api/settings")
async def get_settings():
    """Retrieve active configuration settings."""
    active_model = getattr(orchestrator.base_agent, "model_name", settings.llm.default_model)
    return {
        "activeModel": active_model,
        "ollamaBaseUrl": settings.llm.ollama_base_url,
        "temperature": settings.llm.temperature,
        "maxIterations": settings.agent.max_iterations,
        "contextWindowSize": settings.agent.context_window_size,
        "toolsCount": len(orchestrator.tool_definitions)
    }


@app.post("/api/settings")
async def update_settings(payload: Dict[str, Any] = Body(...)):
    """Update agent runtime settings."""
    if "activeModel" in payload:
        new_model = str(payload["activeModel"]).strip()
        if new_model:
            settings.llm.default_model = new_model
            orchestrator.base_agent.model_name = new_model
            logger.info(f"Updated active model to: {new_model}")

    if "temperature" in payload:
        settings.llm.temperature = float(payload["temperature"])
        orchestrator.base_agent.temperature = settings.llm.temperature

    active_model = getattr(orchestrator.base_agent, "model_name", settings.llm.default_model)
    return {"success": True, "activeModel": active_model, "temperature": settings.llm.temperature}


@app.get("/api/models")
async def get_models():
    """Fetch available local models from Ollama API."""
    ollama_url = f"{settings.llm.ollama_base_url}/api/tags"
    active_model = getattr(orchestrator.base_agent, "model_name", settings.llm.default_model)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(ollama_url)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                return models or [active_model]
    except Exception as e:
        logger.debug(f"Could not reach Ollama at {ollama_url}: {e}")

    # Fallback list if Ollama is not directly reachable
    return [active_model, "llama3.2:latest", "mistral:latest", "qwen2.5-coder:latest"]


# ==================== CONVERSATIONS ====================

@app.get("/api/conversations")
async def list_conversations():
    """List all stored conversations with metadata."""
    convs = orchestrator.memory.short_term.conv_mgr.list_conversations()
    return convs


@app.post("/api/conversations/new")
async def create_conversation():
    """Create a new conversation session."""
    new_conv = orchestrator.memory.short_term.conv_mgr.create_conversation()
    orchestrator.switch_conversation(new_conv.id)
    return {
        "id": new_conv.id,
        "title": new_conv.title,
        "created_at": new_conv.created_at,
        "messages": []
    }


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """Retrieve specific conversation messages."""
    conv = orchestrator.memory.short_term.conv_mgr.load_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "messages": [m.model_dump() for m in conv.messages]
    }


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    """Delete a conversation by ID."""
    success = orchestrator.memory.short_term.conv_mgr.delete_conversation(conv_id)
    return {"success": success}


@app.post("/api/conversations/{conv_id}/switch")
async def switch_conversation(conv_id: str):
    """Switch current active conversation session."""
    orchestrator.switch_conversation(conv_id)
    return {"success": True, "active_conversation_id": conv_id}


# ==================== CHAT & EXECUTION ====================

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """Non-streaming synchronous chat execution."""
    result = await orchestrator.execute_query(
        user_query=req.query,
        conversation_id=req.conversation_id
    )
    return ChatResponse(
        success=result.success,
        response=result.response,
        conversation_id=result.conversation_id,
        tools_used=result.tools_used,
        traces=result.traces,
        error=result.error
    )


@app.post("/api/tools/execute")
async def execute_tool_direct(req: ToolExecuteRequest):
    """Directly execute a registered tool."""
    tool_call = ToolCall(
        tool=req.tool_name,
        query=str(req.args.get("expression") or req.args.get("query") or ""),
        parameters=req.args
    )
    res = await orchestrator.tool_agent.execute_tool_call(tool_call)
    return res.model_dump()


@app.post("/api/tools/confirm_save_file")
async def confirm_save_file(req: ConfirmSaveRequest):
    """Confirm and write file draft to Desktop or Workspace."""
    safe_name = "".join(c for c in req.filename if c not in '<>:"/\\\\|?*\\0').strip()
    if not safe_name:
        return {"success": False, "error": "Invalid filename."}

    desktop_path = Path.home() / "Desktop"
    try:
        desktop_path.mkdir(parents=True, exist_ok=True)
        dest = desktop_path / safe_name
        dest.write_text(req.content or "", encoding="utf-8")
        size_kb = f"{dest.stat().st_size / 1024:.2f}"
        logger.info(f"File successfully written to: {dest} ({size_kb} KB)")
        return {"success": True, "filePath": str(dest), "sizeKB": size_kb}
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        return {"success": False, "error": str(e)}


# ==================== ACADEMIC HUB ====================

@app.get("/api/academic/courses")
async def list_academic_courses():
    """List detected academic courses and file counts from data/kuliah/."""
    from src.tools.academic_tools import DEFAULT_COURSES_DIR
    courses = []
    if DEFAULT_COURSES_DIR.exists():
        for item in sorted(DEFAULT_COURSES_DIR.iterdir()):
            if item.is_dir() and not item.name.startswith((".", "_")):
                files = [f.name for f in item.iterdir() if f.is_file() and not f.name.startswith((".", "_"))]
                has_manifest = (item / "_course_manifest.json").exists()
                courses.append({
                    "name": item.name.replace("_", " "),
                    "folder": item.name,
                    "files_count": len(files),
                    "files": files[:8],
                    "has_manifest": has_manifest
                })
    return {"success": True, "courses": courses, "total": len(courses)}


# ==================== CANCELLATION & WEBSOCKET STREAMING ====================

active_chat_tasks: Dict[str, asyncio.Task] = {}


@app.post("/api/chat/cancel")
async def cancel_chat_request():
    """Cancels any ongoing chat execution."""
    cancelled_count = 0
    for task in list(active_chat_tasks.values()):
        if not task.done():
            task.cancel()
            cancelled_count += 1
    active_chat_tasks.clear()
    logger.info(f"Cancelled {cancelled_count} active chat tasks.")
    return {"success": True, "cancelled": cancelled_count}


@app.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    """Bidirectional WebSocket for real-time trace events, token streaming, and cancellation."""
    await websocket.accept()
    logger.info("WebSocket client connected to /ws/chat")
    session_id = str(id(websocket))
    current_task: Optional[asyncio.Task] = None

    async def execute_and_stream(query: str, conv_id: Optional[str]):
        # Event handler to stream trace events directly to UI
        async def send_trace(event: Dict[str, Any]):
            try:
                await websocket.send_json({"type": "trace", "data": event})
            except Exception as ex:
                logger.debug(f"Trace send error: {ex}")

        def sync_trace_bridge(event: Dict[str, Any]):
            asyncio.create_task(send_trace(event))

        # Send initial processing status
        await websocket.send_json({"type": "status", "data": "Memproses..."})

        # Execute pipeline
        result = await orchestrator.execute_query(
            user_query=query,
            conversation_id=conv_id,
            on_trace=sync_trace_bridge
        )

        # Stream response in chunks for typewriter effect
        response_text = result.response
        chunk_size = 12
        for i in range(0, len(response_text), chunk_size):
            chunk = response_text[i:i + chunk_size]
            await websocket.send_json({"type": "token", "data": chunk})
            await asyncio.sleep(0.01)

        # Send completion payload
        await websocket.send_json({
            "type": "done",
            "success": result.success,
            "response": result.response,
            "conversation_id": result.conversation_id,
            "tools_used": result.tools_used,
            "traces": result.traces
        })

    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                data = json.loads(data_text)
            except Exception:
                await websocket.send_json({"type": "error", "message": "Invalid JSON format."})
                continue

            msg_type = data.get("type", "chat")

            if msg_type == "cancel":
                if current_task and not current_task.done():
                    logger.info("Cancelling current chat execution on user request...")
                    current_task.cancel()
                    current_task = None
                    active_chat_tasks.pop(session_id, None)
                    await websocket.send_json({
                        "type": "cancelled",
                        "message": "Proses berhasil dibatalkan oleh pengguna."
                    })
                continue

            query = data.get("query") or data.get("text") or ""
            conv_id = data.get("conversation_id")
            
            if not query.strip():
                continue

            # Cancel any existing task for this session before starting new one
            if current_task and not current_task.done():
                current_task.cancel()

            async def task_runner(q: str, cid: Optional[str]):
                try:
                    await execute_and_stream(q, cid)
                except asyncio.CancelledError:
                    logger.info("Chat task successfully cancelled by user.")
                    try:
                        await websocket.send_json({
                            "type": "cancelled",
                            "message": "Proses berhasil dibatalkan oleh pengguna."
                        })
                    except Exception:
                        pass
                except Exception as ex:
                    logger.error(f"Error executing chat stream: {ex}")
                    try:
                        await websocket.send_json({"type": "error", "message": str(ex)})
                    except Exception:
                        pass
                finally:
                    active_chat_tasks.pop(session_id, None)

            current_task = asyncio.create_task(task_runner(query, conv_id))
            active_chat_tasks[session_id] = current_task

    except (WebSocketDisconnect, ConnectionResetError, asyncio.CancelledError):
        logger.info("WebSocket client disconnected from /ws/chat")
        if current_task and not current_task.done():
            current_task.cancel()
        active_chat_tasks.pop(session_id, None)
    except Exception as e:
        logger.error(f"WebSocket session error: {e}")
        if current_task and not current_task.done():
            current_task.cancel()
        active_chat_tasks.pop(session_id, None)


# ==================== RAPHAEL GAMING COPILOT ====================

raphael_brain = RaphaelBrain()
_copilot_event_queues: List[asyncio.Queue] = []

async def _copilot_bus_handler(event: GameEvent) -> None:
    """Dispatches GameEvent + Raphael Reaction to all connected SSE clients."""
    reaction = await raphael_brain.generate_reaction(event)
    payload = {
        "game_name": event.game_name,
        "event_type": event.event_type,
        "severity": event.severity,
        "summary": event.summary,
        "reaction": reaction,
        "details": event.details,
        "timestamp": event.timestamp,
    }
    for q in list(_copilot_event_queues):
        try:
            await q.put(payload)
        except Exception:
            pass

event_bus.subscribe(_copilot_bus_handler)


@app.get("/api/game_copilot/overlay")
async def get_game_copilot_overlay():
    """Serves the Tensura Raphael HTML5 HUD overlay."""
    hud_file = Path(__file__).resolve().parent.parent / "game_copilot" / "ui" / "static" / "raphael_hud.html"
    if hud_file.is_file():
        return FileResponse(str(hud_file), headers=NO_CACHE_HEADERS)
    raise HTTPException(status_code=404, detail="Raphael HUD overlay file not found")


@app.get("/api/game_copilot/stream")
async def stream_game_copilot_events():
    """Server-Sent Events (SSE) feed delivering live telemetry reactions to HUD overlay."""
    q = asyncio.Queue()
    _copilot_event_queues.append(q)

    async def event_generator():
        try:
            # Send initial handshake
            init_data = json.dumps({
                "game_name": "Raphael Core",
                "event_type": "SYNCHRONIZED",
                "severity": "INFO",
                "summary": "Raphael telemetry link established.",
                "reaction": "<Notice. Telemetry channel linked. Standing by for Master's gameplay.>",
                "details": {}
            })
            yield f"data: {init_data}\n\n"

            while True:
                data = await q.get()
                yield f"data: {json.dumps(data)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if q in _copilot_event_queues:
                _copilot_event_queues.remove(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/game_copilot/event")
async def publish_game_copilot_event(event_data: Dict[str, Any] = Body(...)):
    """Manually publishes a game event and returns Raphael's reaction."""
    try:
        event = GameEvent(**event_data)
        reaction = await raphael_brain.generate_reaction(event)
        await event_bus.publish(event)
        return {"status": "ok", "reaction": reaction, "event": event.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== STATIC GUI MOUNT ====================

gui_dir = Path(__file__).resolve().parent.parent / "gui"
NO_CACHE_HEADERS = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}

if gui_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(gui_dir)), name="gui_static")

    @app.get("/")
    async def serve_index():
        index_file = gui_dir / "index.html"
        if index_file.is_file():
            return FileResponse(str(index_file), headers=NO_CACHE_HEADERS)
        return JSONResponse({"message": "JARVIS API is running. index.html not found."})

    @app.get("/{file_path:path}")
    async def serve_gui_assets(file_path: str):
        asset = gui_dir / file_path
        if asset.is_file():
            return FileResponse(str(asset), headers=NO_CACHE_HEADERS)
        index_file = gui_dir / "index.html"
        if index_file.is_file():
            return FileResponse(str(index_file), headers=NO_CACHE_HEADERS)
        raise HTTPException(status_code=404, detail="File not found")
