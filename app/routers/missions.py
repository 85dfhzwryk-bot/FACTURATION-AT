from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BillingType, ConsumptionMode, Mission
from app.templates_config import templates

router = APIRouter(prefix="/missions", tags=["missions"])


@router.get("/", response_class=HTMLResponse)
def list_missions(request: Request, db: Session = Depends(get_db)):
    missions = db.query(Mission).order_by(Mission.client, Mission.mission_name).all()
    return templates.TemplateResponse(
        "missions/list.html", {"request": request, "missions": missions}
    )


@router.get("/new", response_class=HTMLResponse)
def new_mission_form(request: Request):
    return templates.TemplateResponse(
        "missions/form.html",
        {
            "request": request,
            "mission": None,
            "billing_types": [e.value for e in BillingType],
            "consumption_modes": [e.value for e in ConsumptionMode],
        },
    )


@router.post("/new")
def create_mission(
    request: Request,
    client: str = Form(...),
    mission_name: str = Form(...),
    consultant: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(None),
    billing_type: str = Form(...),
    tjm_or_forfait: float = Form(...),
    nb_jours_forfait: int = Form(None),
    consumption_mode: str = Form(...),
    active: bool = Form(True),
    db: Session = Depends(get_db),
):
    from datetime import date

    last = db.query(Mission).order_by(Mission.id.desc()).first()
    next_num = (int(last.code[2:]) + 1) if last else 1
    code = f"MC{next_num:04d}"

    mission = Mission(
        code=code,
        client=client,
        mission_name=mission_name,
        consultant=consultant,
        start_date=date.fromisoformat(start_date),
        end_date=date.fromisoformat(end_date) if end_date else None,
        billing_type=BillingType(billing_type),
        tjm_or_forfait=tjm_or_forfait,
        nb_jours_forfait=nb_jours_forfait,
        consumption_mode=ConsumptionMode(consumption_mode),
        active=active,
    )
    db.add(mission)
    db.commit()
    return RedirectResponse("/missions/", status_code=303)


@router.get("/{mission_id}", response_class=HTMLResponse)
def detail_mission(request: Request, mission_id: int, db: Session = Depends(get_db)):
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(404)
    return templates.TemplateResponse(
        "missions/detail.html", {"request": request, "mission": mission}
    )


@router.get("/{mission_id}/edit", response_class=HTMLResponse)
def edit_mission_form(request: Request, mission_id: int, db: Session = Depends(get_db)):
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(404)
    return templates.TemplateResponse(
        "missions/form.html",
        {
            "request": request,
            "mission": mission,
            "billing_types": [e.value for e in BillingType],
            "consumption_modes": [e.value for e in ConsumptionMode],
        },
    )


@router.post("/{mission_id}/edit")
def update_mission(
    mission_id: int,
    client: str = Form(...),
    mission_name: str = Form(...),
    consultant: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(None),
    billing_type: str = Form(...),
    tjm_or_forfait: float = Form(...),
    nb_jours_forfait: int = Form(None),
    consumption_mode: str = Form(...),
    active: str = Form("off"),
    db: Session = Depends(get_db),
):
    from datetime import date

    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(404)

    mission.client = client
    mission.mission_name = mission_name
    mission.consultant = consultant
    mission.start_date = date.fromisoformat(start_date)
    mission.end_date = date.fromisoformat(end_date) if end_date else None
    mission.billing_type = BillingType(billing_type)
    mission.tjm_or_forfait = tjm_or_forfait
    mission.nb_jours_forfait = nb_jours_forfait
    mission.consumption_mode = ConsumptionMode(consumption_mode)
    mission.active = active == "on"
    db.commit()
    return RedirectResponse(f"/missions/{mission_id}", status_code=303)
