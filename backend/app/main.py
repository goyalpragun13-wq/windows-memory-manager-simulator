"""
FastAPI application entrypoint for the Windows Memory Manager Simulator.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.v1.simulation import router as sim_router
from app.api.v1.mmu import router as mmu_router
from app.api.v1.scenarios import router as scenarios_router
from app.api.v1.algorithms import router as algorithms_router
from app.api.v1.telemetry import router as telemetry_router

app = FastAPI(
    title="Windows Memory Manager Simulator API",
    description=(
        "Academic Operating Systems Capstone: Windows NT/10/11 PFN Database, "
        "Working Set Management, Soft Page Faults, MMU Address Translation, "
        "and Replacement Algorithm Lab."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for flexible development and decoupling
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 Routers
app.include_router(sim_router, prefix="/api/v1")
app.include_router(mmu_router, prefix="/api/v1")
app.include_router(scenarios_router, prefix="/api/v1")
app.include_router(algorithms_router, prefix="/api/v1")
app.include_router(telemetry_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
def health_check():
    """Health check probe."""
    return {"status": "ok", "service": "Windows Memory Manager Simulator API"}


@app.get("/report", tags=["System"], include_in_schema=False)
def get_project_report():
    """Serve the academic project report."""
    report_file = os.path.join(os.path.dirname(__file__), "static", "PROJECT_REPORT.html")
    if os.path.exists(report_file):
        return FileResponse(report_file)
    return {"detail": "Project report file not found"}


# Serve built frontend static files if present
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file_path = os.path.join(static_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        index_file = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        return {"detail": "Static frontend index not found"}
