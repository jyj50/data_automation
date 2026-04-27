from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.deps import get_db
from app.schemas.documents import ChatRequest, ChatResponse
from app.services.pdf import rag_answer

router = APIRouter(tags=["chat"])


@router.post("/chat/", response_model=ChatResponse)
def chat_api(
    body: ChatRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not body.query.strip():
        raise HTTPException(400, "query is required")
    return rag_answer(db, body.query, top_k=body.top_k, settings=settings)
