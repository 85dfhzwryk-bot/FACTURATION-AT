from pathlib import Path
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def format_montant(value):
    if value is None:
        return "—"
    return f"{value:,.2f} €".replace(",", " ").replace(".", ",")


def format_date(value):
    if value is None:
        return "—"
    return value.strftime("%d/%m/%Y")


def pct(value):
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


templates.env.filters["montant"] = format_montant
templates.env.filters["date_fr"] = format_date
templates.env.filters["pct"] = pct
