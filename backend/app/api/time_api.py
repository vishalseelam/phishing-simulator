"""
Time Control API

Endpoints for controlling simulation time.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
import logging

from app.services.time_controller import time_controller

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/time", tags=["time"])


class SetTimeRequest(BaseModel):
    """Request to set simulation time."""
    time: str  # ISO format


@router.get("/current")
async def get_current_time():
    """Get current simulation time."""
    current = await time_controller.get_current_time()
    
    return {
        "current_time": current.isoformat(),
        "is_simulation": time_controller.is_simulation_mode,
        "multiplier": time_controller.time_multiplier
    }


@router.post("/set")
async def set_time(request: SetTimeRequest):
    """
    Set simulation time.
    
    Processes all messages up to this time.
    """
    try:
        new_time = datetime.fromisoformat(request.time)
        result = await time_controller.set_time(new_time)
        
        return {
            "success": True,
            **result
        }
    
    except Exception as e:
        logger.error(f"set_time_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skip_to_next")
async def skip_to_next():
    """
    Skip to next scheduled message time.
    
    Delivers that message immediately.
    """
    try:
        result = await time_controller.skip_to_next_message()
        
        if "error" in result:
            return {"success": False, "error": result["error"]}
        
        return {
            "success": True,
            **result
        }
    
    except Exception as e:
        logger.error(f"skip_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fast_forward")
async def fast_forward(minutes: int):
    """
    Fast forward by N minutes.
    
    Processes all messages in that time range.
    """
    try:
        result = await time_controller.fast_forward(minutes)
        
        return {
            "success": True,
            **result
        }
    
    except Exception as e:
        logger.error(f"fast_forward_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset_realtime")
async def reset_to_realtime():
    """Switch back to real-time mode."""
    result = await time_controller.reset_to_realtime()
    
    return {
        "success": True,
        **result
    }

