"""Public router for research, customer operations and owner administration."""
from fastapi import APIRouter
from .business_research import router as research_router
from .business_commerce import router as commerce_router

router = APIRouter()
router.include_router(research_router)
router.include_router(commerce_router)
