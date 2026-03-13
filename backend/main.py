import os
import asyncio
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Gamma API Proxy Service")

# Allow CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GAMMA_API_KEY = os.getenv("GAMMA_API_KEY")
GAMMA_BASE_URL = "https://public-api.gamma.app/v1.0"
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

def get_headers():
    return {
        "X-API-KEY": GAMMA_API_KEY,
        "Content-Type": "application/json"
    }

class GenerateRequest(BaseModel):
    # Mapping to Gamma API parameters
    format: str # 'presentation' or 'document'
    dimensions: str # '16x9', '4x3', 'a4'
    textMode: str # 'generate', 'condense', 'preserve'
    inputText: str
    numCards: int = Field(ge=1, le=60)
    additionalInstructions: Optional[str] = Field(None, max_length=2000)
    amount: str # 'brief', 'medium', 'detailed', 'extensive'
    tone: Optional[str] = None
    audience: Optional[str] = None
    language: str = "ru"
    themeId: Optional[str] = None
    exportAs: str # 'pdf' or 'pptx'

@app.get("/api/themes")
async def get_themes():
    if MOCK_MODE:
        return {
            "themes": [
                {"id": "theme1", "name": "Dark Elegance"},
                {"id": "theme2", "name": "Light Corporate"},
                {"id": "theme3", "name": "Playful Creative"}
            ]
        }

    response = None
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{GAMMA_BASE_URL}/themes", headers=get_headers())
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            if response and response.status_code == 401:
                # Return mock data if token is invalid, to not block the frontend entirely during testing
                print(f"Failed to fetch themes from Gamma API: {e}")
                return {
                    "themes": [
                        {"id": "theme1", "name": "Dark Elegance (Mock)"},
                        {"id": "theme2", "name": "Light Corporate (Mock)"},
                        {"id": "theme3", "name": "Playful Creative (Mock)"}
                    ]
                }
            raise HTTPException(status_code=500, detail=f"Error fetching themes: {str(e)}")

async def poll_generation(generation_id: str, export_as: str):
    """
    Polls the generation status every 5 seconds until completed.
    Returns ONLY the download link for the requested format.
    """
    max_retries = 100 # Adjust as needed

    async with httpx.AsyncClient() as client:
        for _ in range(max_retries):
            try:
                response = await client.get(f"{GAMMA_BASE_URL}/generations/{generation_id}", headers=get_headers())
                response.raise_for_status()
                data = response.json()

                status = data.get("status")
                if status == "completed":
                    export_links = data.get("exportLinks", {})
                    # Critical: Extract ONLY the requested format link
                    if export_as == "pdf" and "pdf" in export_links:
                        return {"downloadUrl": export_links["pdf"]}
                    elif export_as == "pptx" and "pptx" in export_links:
                        return {"downloadUrl": export_links["pptx"]}
                    else:
                        raise HTTPException(status_code=500, detail="Requested export format not found in completed generation.")
                elif status in ["failed", "cancelled", "error"]:
                    raise HTTPException(status_code=500, detail=f"Generation failed with status: {status}")

                # Status is pending/in-progress, wait and poll again
                await asyncio.sleep(5)

            except httpx.HTTPError as e:
                 raise HTTPException(status_code=500, detail=f"Error polling generation: {str(e)}")

        raise HTTPException(status_code=504, detail="Generation polling timed out.")


@app.post("/api/generate")
async def generate_document(req: GenerateRequest):
    if MOCK_MODE:
        # Simulate delay
        await asyncio.sleep(2)
        return {"downloadUrl": f"https://mock-download.example.com/mock_file.{req.exportAs}"}

    payload = {
        "format": req.format,
        "textMode": req.textMode,
        "inputText": req.inputText,
        "numCards": req.numCards,
        "cardOptions": {
            "dimensions": req.dimensions
        },
        "textOptions": {
            "amount": req.amount,
            "language": req.language
        },
        "imageOptions": {
            "source": "aiGenerated",
            "model": "flux-2-klein" # Hardcoded cheapest model
        }
    }

    # Optional fields
    if req.additionalInstructions:
        payload["additionalInstructions"] = req.additionalInstructions
    if req.tone:
         payload["textOptions"]["tone"] = req.tone
    if req.audience:
         payload["textOptions"]["audience"] = req.audience
    if req.themeId:
        payload["themeId"] = req.themeId

    response = None
    async with httpx.AsyncClient() as client:
        try:
            # Step 1: Start the generation
            response = await client.post(
                f"{GAMMA_BASE_URL}/generations",
                headers=get_headers(),
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            generation_id = data.get("id")

            if not generation_id:
                raise HTTPException(status_code=500, detail="No generation ID returned from Gamma API.")

            # Step 2: Poll for completion and return ONLY the download URL
            return await poll_generation(generation_id, req.exportAs)

        except httpx.HTTPError as e:
            error_detail = str(e)
            if response is not None:
                if response.status_code == 401:
                    raise HTTPException(status_code=401, detail="Недействительный или просроченный API-ключ Gamma")
                try:
                    error_detail = response.json()
                except:
                    pass
            raise HTTPException(status_code=500, detail=f"Gamma API Error: {error_detail}")

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

# Mount the static frontend files
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
if not os.path.exists(STATIC_DIR):
    # Fallback to local 'static' if running directly in the container
    STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    if not os.path.exists(STATIC_DIR) and os.path.exists("/app/static"):
        STATIC_DIR = "/app/static"

# When building locally without Docker, the static folder might not exist yet,
# so we don't strictly require it on app startup. However, in production (Docker)
# it will be mounted at /app/static
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = "/app/static" # Force for docker env

# Add route for the root of the app
@app.get("/")
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend not found"}

# Attempt to mount /assets if they exist
try:
    if os.path.exists(os.path.join(STATIC_DIR, "assets")):
        app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")
except Exception as e:
    print(f"Warning: Could not mount static assets: {e}")

# Catch-all route to serve index.html for client-side routing
@app.get("/{full_path:path}")
async def serve_frontend_catchall(full_path: str):
    # Allow API routes to fall through to their 404s if not matched
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")

    # Also handle things like favicon or other files in the root of dist
    file_path = os.path.join(STATIC_DIR, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend not found"}
