import os

from fastapi import BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter

from ..internal.dependencies import SessionDep, Attendee
from ..internal.ticket_generator import create_ticket

router = APIRouter(prefix="/attendees")

@router.get("/{user_id}")
async def get_attendee(user_id: int, session: SessionDep, background_tasks: BackgroundTasks):
    user = session.get(Attendee, user_id)
    if not user:
        return HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    ticket_file = create_ticket(user.name)

    background_tasks.add_task(lambda file: os.remove(file.name), ticket_file)
    return FileResponse(ticket_file.name, media_type="application/pdf")
