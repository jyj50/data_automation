from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.models.db import Article
from app.schemas.documents import ArticleUpdateRequest

router = APIRouter(tags=["articles"])


@router.put("/articles/{article_id}/")
def update_article(
    article_id: int,
    body: ArticleUpdateRequest,
    db: Session = Depends(get_db),
):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found.")
    if body.full_title is not None:
        article.full_title = body.full_title
    if body.content is not None:
        article.content = body.content
    if body.chapter_title is not None:
        article.chapter_title = body.chapter_title
    if body.section_title is not None:
        article.section_title = body.section_title
    if body.order is not None:
        article.order = body.order
    article.user_edited = True
    article.version += 1
    db.commit()
    return {"status": "ok"}
