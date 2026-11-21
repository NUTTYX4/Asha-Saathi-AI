from fastapi import APIRouter, Request

from app.schemas.visit import FollowUpItem, SavedVisit

router = APIRouter(tags=["visits"])


@router.get("/visits", response_model=list[SavedVisit])
def list_visits(request: Request) -> list[SavedVisit]:
    return request.app.state.repo.list_visits()


@router.get("/followups", response_model=list[FollowUpItem])
def list_followups(request: Request) -> list[FollowUpItem]:
    return request.app.state.repo.list_followups()
