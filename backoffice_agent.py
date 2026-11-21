from datetime import date, timedelta
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/backoffice", tags=["small-business-back-office"])


class Customer(BaseModel):
    id: str
    name: str
    email: str = ""
    phone: str = ""


class CustomerCreate(BaseModel):
    name: str
    email: str = ""
    phone: str = ""


class InvoiceCreate(BaseModel):
    customer_id: str
    description: str
    amount: float = Field(gt=0)
    due_date: date


class Invoice(BaseModel):
    id: str
    customer_id: str
    customer_name: str
    description: str
    amount: float
    due_date: date
    status: Literal["draft", "sent", "paid", "overdue"]
    sent_date: date | None = None
    paid_date: date | None = None


class PaymentCreate(BaseModel):
    paid_date: date | None = None


class AgentRequest(BaseModel):
    message: str


customers = {
    "c1": Customer(id="c1", name="Northstar Cafe", email="accounts@northstar.example", phone="555-0101"),
    "c2": Customer(id="c2", name="Maya Yoga Studio", email="maya@studio.example", phone="555-0102"),
    "c3": Customer(id="c3", name="Bright Books", email="hello@brightbooks.example", phone="555-0103"),
}

_today = date.today()
invoices = {
    "i1": Invoice(id="i1", customer_id="c1", customer_name="Northstar Cafe", description="Brand identity refresh", amount=4800, due_date=_today - timedelta(days=18), status="overdue", sent_date=_today - timedelta(days=32)),
    "i2": Invoice(id="i2", customer_id="c2", customer_name="Maya Yoga Studio", description="Social campaign graphics", amount=2200, due_date=_today - timedelta(days=6), status="overdue", sent_date=_today - timedelta(days=20)),
    "i3": Invoice(id="i3", customer_id="c3", customer_name="Bright Books", description="Website homepage design", amount=1500, due_date=_today + timedelta(days=12), status="sent", sent_date=_today - timedelta(days=2)),
    "i4": Invoice(id="i4", customer_id="c1", customer_name="Northstar Cafe", description="Menu and signage design", amount=950, due_date=_today - timedelta(days=2), status="paid", sent_date=_today - timedelta(days=16), paid_date=_today - timedelta(days=2)),
}

bills = [
    {"id": "b1", "name": "Studio rent", "amount": 1800, "due_date": (_today + timedelta(days=5)).isoformat()},
    {"id": "b2", "name": "Adobe subscriptions", "amount": 120, "due_date": (_today + timedelta(days=11)).isoformat()},
    {"id": "b3", "name": "Freelancer contractor", "amount": 900, "due_date": (_today + timedelta(days=28)).isoformat()},
]


def refresh_overdue():
    for invoice in invoices.values():
        if invoice.status == "sent" and invoice.due_date < date.today():
            invoice.status = "overdue"


def make_reminder(invoice: Invoice) -> str:
    days_late = (date.today() - invoice.due_date).days
    if days_late > 0:
        return (
            f"Hi {invoice.customer_name}, a friendly reminder that invoice {invoice.id} for "
            f"₹{invoice.amount:,.0f} was due {days_late} day"
            f"{'s' if days_late != 1 else ''} ago. Could you please let us know when payment will be made?"
        )
    return (
        f"Hi {invoice.customer_name}, invoice {invoice.id} for ₹{invoice.amount:,.0f} is due "
        f"on {invoice.due_date.strftime('%d %b %Y')}. Please let me know if you need anything else."
    )


@router.get("/customers")
def list_customers():
    return list(customers.values())


@router.post("/customers", status_code=201)
def create_customer(payload: CustomerCreate):
    customer = Customer(id=f"c{uuid4().hex[:8]}", **payload.model_dump())
    customers[customer.id] = customer
    return customer


@router.get("/invoices")
def list_invoices():
    refresh_overdue()
    return list(invoices.values())


@router.post("/invoices", status_code=201)
def create_invoice(payload: InvoiceCreate):
    customer = customers.get(payload.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    invoice = Invoice(
        id=f"i{uuid4().hex[:8]}",
        customer_id=customer.id,
        customer_name=customer.name,
        description=payload.description,
        amount=payload.amount,
        due_date=payload.due_date,
        status="draft",
    )
    invoices[invoice.id] = invoice
    return invoice


@router.post("/invoices/{invoice_id}/send")
def send_invoice(invoice_id: str):
    invoice = invoices.get(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice.status = "sent" if invoice.due_date >= date.today() else "overdue"
    invoice.sent_date = date.today()
    return {"invoice": invoice, "reminder": make_reminder(invoice)}


@router.post("/invoices/{invoice_id}/pay")
def record_payment(invoice_id: str, payload: PaymentCreate):
    invoice = invoices.get(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice.status = "paid"
    invoice.paid_date = payload.paid_date or date.today()
    return invoice


@router.get("/invoices/{invoice_id}/reminder")
def invoice_reminder(invoice_id: str):
    invoice = invoices.get(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"message": make_reminder(invoice)}


@router.get("/dashboard")
def dashboard():
    refresh_overdue()
    outstanding = [i for i in invoices.values() if i.status in {"sent", "overdue"}]
    overdue = [i for i in outstanding if i.status == "overdue"]
    today = date.today()
    alerts = []
    for invoice in overdue:
        days_overdue = (today - invoice.due_date).days
        alerts.append({
            "invoice_id": invoice.id,
            "customer": invoice.customer_name,
            "amount": invoice.amount,
            "days_overdue": days_overdue,
            "action": "Chase this invoice today" if days_overdue >= 14 else "Send a reminder today",
            "priority": "urgent" if days_overdue >= 14 else "today",
        })

    return {
        "today": today.isoformat(),
        "outstanding_total": sum(i.amount for i in outstanding),
        "overdue_total": sum(i.amount for i in overdue),
        "outstanding_count": len(outstanding),
        "overdue_count": len(overdue),
        "who_owes": [
            {
                "customer": i.customer_name,
                "invoice_id": i.id,
                "amount": i.amount,
                "due_date": i.due_date.isoformat(),
                "days_late": max(0, (today - i.due_date).days),
                "status": i.status,
            }
            for i in sorted(outstanding, key=lambda invoice: invoice.due_date)
        ],
        "alerts": alerts,
        "bills": bills,
    }


def _cash_events(horizon_days: int, customer_name: str | None = None, delay_days: int = 0):
    today = date.today()
    end_date = today + timedelta(days=horizon_days)
    customer = next(
        (c for c in customers.values() if customer_name and c.name.lower() == customer_name.lower()),
        None,
    )
    events = []
    for invoice in invoices.values():
        if invoice.status not in {"sent", "overdue"}:
            continue
        expected_date = max(invoice.due_date, today)
        if customer and invoice.customer_id == customer.id:
            expected_date += timedelta(days=delay_days)
        if expected_date <= end_date:
            events.append({
                "date": expected_date.isoformat(),
                "type": "invoice",
                "amount": invoice.amount,
                "name": invoice.customer_name,
            })
    for bill in bills:
        due_date = date.fromisoformat(bill["due_date"])
        if due_date <= end_date:
            events.append({
                "date": bill["due_date"],
                "type": "bill",
                "amount": -bill["amount"],
                "name": bill["name"],
            })
    return sorted(events, key=lambda event: event["date"])


@router.get("/forecast")
def forecast(horizon_days: int = 60):
    horizon_days = max(30, min(horizon_days, 90))
    today = date.today()
    opening_cash = 5200
    events = _cash_events(horizon_days)
    balance = opening_cash
    cash_points = [{"date": today.isoformat(), "balance": balance}]
    for event in events:
        balance += event["amount"]
        cash_points.append({"date": event["date"], "balance": round(balance, 2)})
    return {
        "horizon_days": horizon_days,
        "opening_cash": opening_cash,
        "ending_cash": round(balance, 2),
        "lowest_point": min(cash_points, key=lambda point: point["balance"]),
        "events": events,
        "cash_points": cash_points,
    }


@router.post("/scenario")
def late_payment_scenario(customer_name: str = "Northstar Cafe", delay_days: int = 15):
    delay_days = max(0, min(delay_days, 90))
    today = date.today()
    opening_cash = 5200
    events = _cash_events(90, customer_name, delay_days)
    balance = opening_cash
    lowest = {"date": today.isoformat(), "balance": opening_cash}
    for event in events:
        balance += event["amount"]
        if balance < lowest["balance"]:
            lowest = {"date": event["date"], "balance": balance}
    return {
        "scenario": f"{customer_name} pays {delay_days} days late",
        "opening_cash": opening_cash,
        "ending_cash": round(balance, 2),
        "lowest_point": lowest,
        "events": events,
        "action": (
            "Move the studio rent payment or chase this customer before month-end."
            if lowest["balance"] < 0
            else "No cash shortfall expected; send a reminder before the delay."
        ),
    }


@router.post("/agent")
def backoffice_agent(request: AgentRequest):
    message = request.message.lower().strip()
    if any(word in message for word in ("owe", "outstanding", "unpaid", "late", "dashboard", "who")):
        data = dashboard()
        names = ", ".join(
            f"{item['customer']} ₹{item['amount']:,.0f} ({item['days_late']} days late)"
            for item in data["who_owes"]
        )
        return {
            "reply": f"₹{data['outstanding_total']:,.0f} is outstanding. {names or 'No unpaid invoices.'}",
            "data": data,
        }
    if any(word in message for word in ("forecast", "cash", "months", "next 60", "next 30")):
        data = forecast(60)
        return {
            "reply": (
                f"The 60-day forecast ends at ₹{data['ending_cash']:,.0f}. "
                f"Lowest cash point: ₹{data['lowest_point']['balance']:,.0f} on "
                f"{data['lowest_point']['date']}."
            ),
            "data": data,
        }
    if any(word in message for word in ("scenario", "what if", "delay")):
        data = late_payment_scenario()
        return {"reply": f"{data['scenario']}. {data['action']}", "data": data}
    if any(word in message for word in ("remind", "chase", "follow up", "reminder")):
        overdue = sorted(
            (i for i in invoices.values() if i.status == "overdue"),
            key=lambda invoice: invoice.due_date,
        )
        if not overdue:
            return {"reply": "There are no overdue invoices to chase."}
        invoice = overdue[0]
        return {"reply": make_reminder(invoice), "invoice_id": invoice.id}
    return {
        "reply": (
            "I can help with unpaid invoices, overdue reminders, the 60-day cash forecast, "
            "or a late-payment scenario. What would you like to see?"
        )
    }
