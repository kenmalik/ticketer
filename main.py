from dataclasses import dataclass
import os

import tempfile
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

import qrcode

from fpdf import FPDF

import stripe

from pydantic import BaseModel

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")


DOMAIN = os.environ["DOMAIN"]
stripe.api_key = os.environ["STRIPE_API_KEY"]
WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]


@dataclass
class InternalUser:
    name: str
    email: str


users: dict[int, InternalUser] = {}
users[0] = InternalUser("Joe", "test_email@email.com")
current_id = 1


class User(BaseModel):
    id: str
    name: str
    email: str


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
            global current_id
            users[current_id] = InternalUser(details.name, details.email)
            user_id = current_id
            current_id += 1

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


class TicketPDF(FPDF):
    def header(self):
        title = "Ticket"

        self.set_font("helvetica", size=16)
        width = self.get_string_width(title) + 6

        self.set_x_to_center(width)
        self.cell(width, 9, title, new_x="LMARGIN", new_y="NEXT", align="C")

    def set_x_to_center(self, item_width: float):
        self.set_x((self.epw - item_width) / 2 + self.l_margin)


def create_ticket(user: InternalUser):
    with tempfile.NamedTemporaryFile(delete=False) as f:
        ticket = TicketPDF(format="Letter")
        ticket.add_page()
        ticket.set_title(f"Ticket | {user.name}")

        img = qrcode.make(f"Hello, {user.name}!")
        qr_height = ticket.eph / 4
        qr_width = qr_height
        ticket.set_x_to_center(qr_width)
        ticket.image(img.get_image(), h=qr_height, w=qr_width, keep_aspect_ratio=True)

        f.write(ticket.output())

    return f


@app.get("/users/{user_id}")
async def get_ticket(user_id: int, background_tasks: BackgroundTasks):
    user = users.get(user_id)
    if not user:
        return HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    ticket_file = create_ticket(user)

    background_tasks.add_task(lambda file: os.remove(file.name), ticket_file)
    return FileResponse(ticket_file.name, media_type="application/pdf")
