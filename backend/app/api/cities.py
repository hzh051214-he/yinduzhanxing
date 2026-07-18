"""城市搜索 API。"""
from fastapi import APIRouter, Query
from app.services.geocoding import search_city

router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("/search")
async def search_cities(q: str = Query(..., min_length=1, description="城市名关键字")):
    """城市搜索自动补全接口。"""
    results = search_city(q, limit=8)
    return {"results": results}
