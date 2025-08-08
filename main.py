from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, Request, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic_settings import BaseSettings, SettingsConfigDict

import stripe

from .routes import attendees

from .internal.dependencies import create_db_and_tables, insert_attendee


class Settings(BaseSettings):
    domain: str = "http://localhost:8000"
    stripe_api_key: str
    stripe_webhook_secret: str

    model_config = SettingsConfigDict(env_file=".env")


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    stripe.api_key = get_settings().stripe_api_key
    yield


@lru_cache
def get_settings():
    return Settings()  # type: ignore  # Values read from .env file


app = FastAPI(lifespan=lifespan)
app.include_router(attendees.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.post("/webhook", status_code=200)
async def handle_webhook(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError as e:
        return HTTPException(status_code=400, detail=f"Invalid payload: {e}")
    except stripe.SignatureVerificationError as e:
        return HTTPException(status_code=400, detail=f"Invalid signature: {e}")

    if (
        event["type"] == "checkout.session.completed"
        or event["type"] == "checkout.session.async_payment_succeeded"
    ):
        fulfill_checkout(event["data"]["object"]["id"])

    return {"status": "success"}


def fulfill_checkout(session_id):
    checkout_session = stripe.checkout.Session.retrieve(
        session_id,
        expand=["customer"],
    )

    if checkout_session.payment_status != "unpaid":
        details = checkout_session.customer_details
        if details and details.name and details.email:
            return insert_attendee(details.name, details.email).id


@app.post("/ticket")
async def buy_ticket(settings: Annotated[Settings, Depends(get_settings)]):
    try:
        print("Creating checkout session")
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    "price": "price_1Rs5n6CPK232icSlzHzYrnSs",
                    "quantity": 1,
                },
            ],
            mode="payment",
            success_url=settings.domain + "/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=settings.domain + "/cancel",
        )
    except Exception as e:
        print("Failed")
        return str(e)

    if checkout_session.url:
        return RedirectResponse(
            checkout_session.url, status_code=status.HTTP_303_SEE_OTHER
        )
    else:
        return RedirectResponse(settings.domain, status_code=status.HTTP_303_SEE_OTHER)


@app.get("/success")
async def success(session_id: str):
    user_id = fulfill_checkout(session_id)
    return RedirectResponse(f"/attendees/{user_id}")


@app.get("/cancel")
async def cancel():
    return "cancel"
