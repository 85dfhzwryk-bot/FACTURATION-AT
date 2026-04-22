from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Commande, Mission, Poste
from app.templates_config import templates

router = APIRouter(prefix="/commandes", tags=["commandes"])


@router.get("/", response_class=HTMLResponse)
def list_commandes(request: Request, db: Session = Depends(get_db)):
    commandes = (
        db.query(Commande)
        .join(Mission)
        .order_by(Mission.client, Commande.numero)
        .all()
    )
    return templates.TemplateResponse(
        "commandes/list.html", {"request": request, "commandes": commandes}
    )


@router.get("/new", response_class=HTMLResponse)
def new_commande_form(request: Request, db: Session = Depends(get_db)):
    missions = db.query(Mission).filter(Mission.active == True).order_by(Mission.client).all()
    return templates.TemplateResponse(
        "commandes/form.html",
        {"request": request, "commande": None, "missions": missions},
    )


@router.post("/new")
def create_commande(
    numero: str = Form(...),
    mission_id: int = Form(...),
    postes_numeros: list[int] = Form(...),
    postes_montants: list[float] = Form(...),
    db: Session = Depends(get_db),
):
    commande = Commande(numero=numero, mission_id=mission_id)
    db.add(commande)
    db.flush()

    for num, montant in zip(postes_numeros, postes_montants):
        poste = Poste(
            commande_id=commande.id,
            numero_poste=num,
            montant_total=montant,
        )
        db.add(poste)

    db.commit()
    return RedirectResponse("/commandes/", status_code=303)


@router.get("/{commande_id}", response_class=HTMLResponse)
def detail_commande(request: Request, commande_id: int, db: Session = Depends(get_db)):
    commande = db.query(Commande).filter(Commande.id == commande_id).first()
    if not commande:
        raise HTTPException(404)
    return templates.TemplateResponse(
        "commandes/detail.html", {"request": request, "commande": commande}
    )


@router.get("/{commande_id}/edit", response_class=HTMLResponse)
def edit_commande_form(request: Request, commande_id: int, db: Session = Depends(get_db)):
    commande = db.query(Commande).filter(Commande.id == commande_id).first()
    if not commande:
        raise HTTPException(404)
    missions = db.query(Mission).filter(Mission.active == True).order_by(Mission.client).all()
    return templates.TemplateResponse(
        "commandes/form.html",
        {"request": request, "commande": commande, "missions": missions},
    )


@router.post("/{commande_id}/edit")
def update_commande(
    commande_id: int,
    numero: str = Form(...),
    mission_id: int = Form(...),
    db: Session = Depends(get_db),
):
    commande = db.query(Commande).filter(Commande.id == commande_id).first()
    if not commande:
        raise HTTPException(404)
    commande.numero = numero
    commande.mission_id = mission_id
    db.commit()
    return RedirectResponse(f"/commandes/{commande_id}", status_code=303)


@router.post("/{commande_id}/postes/add")
def add_poste(
    commande_id: int,
    numero_poste: int = Form(...),
    montant_total: float = Form(...),
    db: Session = Depends(get_db),
):
    commande = db.query(Commande).filter(Commande.id == commande_id).first()
    if not commande:
        raise HTTPException(404)
    poste = Poste(
        commande_id=commande_id,
        numero_poste=numero_poste,
        montant_total=montant_total,
    )
    db.add(poste)
    db.commit()
    return RedirectResponse(f"/commandes/{commande_id}", status_code=303)


@router.post("/{commande_id}/postes/{poste_id}/cloture")
def cloture_poste(commande_id: int, poste_id: int, db: Session = Depends(get_db)):
    poste = db.query(Poste).filter(Poste.id == poste_id).first()
    if not poste:
        raise HTTPException(404)
    poste.cloture_admin = True
    db.commit()
    return RedirectResponse(f"/commandes/{commande_id}", status_code=303)
