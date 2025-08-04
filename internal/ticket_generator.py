import tempfile
import qrcode
from fpdf import FPDF


class TicketPDF(FPDF):
    def header(self):
        title = "Ticket"

        self.set_font("helvetica", size=16)
        width = self.get_string_width(title) + 6

        self.set_x_to_center(width)
        self.cell(width, 9, title, new_x="LMARGIN", new_y="NEXT", align="C")

    def set_x_to_center(self, item_width: float):
        self.set_x((self.epw - item_width) / 2 + self.l_margin)


def create_ticket(username: str):
    with tempfile.NamedTemporaryFile(delete=False) as f:
        ticket = TicketPDF(format="Letter")
        ticket.add_page()
        ticket.set_title(f"Ticket | {username}")

        img = qrcode.make(f"Hello, {username}!")
        qr_height = ticket.eph / 4
        qr_width = qr_height
        ticket.set_x_to_center(qr_width)
        ticket.image(img.get_image(), h=qr_height, w=qr_width, keep_aspect_ratio=True)

        f.write(ticket.output())

    return f
