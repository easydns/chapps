"""Common code between routers; mainly dependencies"""
from typing import Optional, List

async def list_query_params(skip: int = 0, limit: int = 1000, q: Optional[str] = '%'):
    return dict(q=q, skip=skip, limit=limit)
