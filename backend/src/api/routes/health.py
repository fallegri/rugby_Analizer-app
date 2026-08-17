"""Health check endpoint.

Returns system status including GPU availability, loaded models,
and active session information.
"""

import platform
import sys
from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


def _check_gpu_availability() -> dict:
    """Check if GPU/CUDA is available."""
    try:
        import torch

        cuda_available = torch.cuda.is_available()
        if cuda_available:
            props = torch.cuda.get_device_properties(0)
            return {
                "available": True,
                "device_name": torch.cuda.get_device_name(0),
                "device_count": torch.cuda.device_count(),
                "memory_total": getattr(props, "total_memory", getattr(props, "total_mem", 0)),
            }
        return {"available": False, "reason": "CUDA not available"}
    except (ImportError, Exception) as e:
        return {"available": False, "reason": str(e)}


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint returning system status.

    Returns:
        JSON with system status, GPU availability, and service info.
    """
    return {
        "status": "healthy",
        "service": "rugby-analyzer",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": {
            "python_version": sys.version,
            "platform": platform.system(),
            "architecture": platform.machine(),
        },
        "gpu": _check_gpu_availability(),
        "models_loaded": [],
        "active_sessions": 0,
    }
