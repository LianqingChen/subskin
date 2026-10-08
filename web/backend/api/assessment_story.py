"""Authenticated creative captions for saved, reviewed journal entries."""
import logging
from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from web.backend.database.database import get_db
from web.backend.database.models import User
from web.backend.exceptions import StoryGenerationError
from web.backend.services.auth import get_current_user
from web.backend.services.assessment_story import create_story

router = APIRouter()
logger = logging.getLogger(__name__)


class StoryRequest(BaseModel):
    theme: Optional[Literal["sky", "island", "stars"]] = None
    retry: bool = False
    revision: str = Field(..., min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")


@router.post("/assess/{assessment_id}/story")
def story(assessment_id: int, body: StoryRequest, response: Response,
          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return create_story(db, assessment_id, user.id, body.revision, theme=body.theme)
    except StoryGenerationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_status, detail=str(exc))
    except Exception:
        db.rollback()
        logger.exception("Journal creative generation failed")
        raise HTTPException(status_code=503, detail="创意暂未生成，请稍后重试")


@router.post("/assess/{assessment_id}/story/art")
def start_artwork(assessment_id: int, body: StoryRequest, response: Response,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from web.backend.services.assessment_art import start_art
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return start_art(db, assessment_id, user.id, body.revision, retry=body.retry, theme=body.theme)
    except StoryGenerationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_status, detail=str(exc))
    except Exception:
        db.rollback()
        logger.error("Journal artwork admission failed")
        raise HTTPException(status_code=503, detail="艺术画面暂未生成，请稍后重试")


@router.get("/assess/{assessment_id}/story/art")
def artwork_status(assessment_id: int, revision: str, response: Response,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db),
                   theme: Optional[Literal["sky", "island", "stars"]] = None):
    from web.backend.services.assessment_art import read_art
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return read_art(db, assessment_id, user.id, revision, theme=theme)
    except StoryGenerationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http_status, detail=str(exc))
    except Exception:
        db.rollback()
        logger.error("Journal artwork polling failed")
        raise HTTPException(status_code=503, detail="艺术画面仍在准备，请稍后重试")
