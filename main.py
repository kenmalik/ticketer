import os

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

import stripe

from internal import db
from internal.ticket_generator import create_ticket

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")


users = db.Users()


DOMAIN = os.environ["DOMAIN"]
stripe.api_key = os.environ["STRIPE_API_KEY"]
WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]


@app.post("/webhook", status_code=200)
async def handle_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
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

    user_id = -1

    if checkout_session.payment_status != "unpaid":
        details = checkout_session.customer_details
        if details and details.name and details.email:
            user_id = users.insert(details.name, details.email)

    return user_id


@app.post("/ticket")
async def buy_ticket():
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    "price": "price_1Rs5n6CPK232icSlzHzYrnSs",
                    "quantity": 1,
                },
            ],
            mode="payment",
            success_url=DOMAIN + "/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=DOMAIN + "/cancel",
        )
    except Exception as e:
        return str(e)

    if checkout_session.url:
        return RedirectResponse(checkout_session.url, status_code=303)
    else:
        return "Error getting checkout session"


@app.get("/success")
async def success(session_id: str):
    user_id = fulfill_checkout(session_id)
    return RedirectResponse(f"/users/{user_id}")


@app.get("/cancel")
async def cancel():
    return "cancel"


@app.get("/users/{user_id}")
async def get_ticket(user_id: int, background_tasks: BackgroundTasks):
    user = users.get(user_id)
    if not user:
        return HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    ticket_file = create_ticket(user.name)

    background_tasks.add_task(lambda file: os.remove(file.name), ticket_file)
    return FileResponse(ticket_file.name, media_type="application/pdf")
