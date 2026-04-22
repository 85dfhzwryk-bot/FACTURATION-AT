import os
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BDL, ClientTemplate, Mission, StatutBDL
from app.services.bdl_generator import generer_bdl_mois
from app.services.email_service import envoyer_bdl
from app.services.pdf_service import generer_pdf
from app.templates_config import templates

router = APIRouter(prefix="/bdl", tags=["bdl"])


@router.get("/", response_class=HTMLResponse)
def list_bdl(request: Request, mois: int = None, annee: int = None, db: Session = Depends(get_db)):
    from datetime import date
    if not annee:
        annee = date.today().year
    if not mois:
        mois = date.today().month

    bdls = (
        db.query(BDL)
        .filter(
            BDL.date_bdl >= date(annee, mois, 1),
            BDL.date_bdl < date(annee + (mois // 12), (mois % 12) + 1, 1),
        )
        .order_by(BDL.mission_id)
        .all()
    )
    return templates.TemplateResponse(
        "bdl/list.html",
        {
            "request": request,
            "bdls": bdls,
            "mois": mois,
            "annee": annee,
            "mois_fr": ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"],
        },
    )


@router.post("/generer")
def generer(mois: int = Form(...), annee: int = Form(...), db: Session = Depends(get_db)):
    generer_bdl_mois(db, annee, mois)
    return RedirectResponse(f"/bdl/?mois={mois}&annee={annee}", status_code=303)


@router.post("/regenerer")
def regenerer(mois: int = Form(...), annee: int = Form(...), db: Session = Depends(get_db)):
    generer_bdl_mois(db, annee, mois, regenerer=True)
    return RedirectResponse(f"/bdl/?mois={mois}&annee={annee}", status_code=303)


@router.get("/{bdl_id}", response_class=HTMLResponse)
def detail_bdl(request: Request, bdl_id: int, db: Session = Depends(get_db)):
    bdl = db.query(BDL).filter(BDL.id == bdl_id).first()
    if not bdl:
        raise HTTPException(404)
    return templates.TemplateResponse("bdl/detail.html", {"request": request, "bdl": bdl})


@router.post("/{bdl_id}/edit")
def update_bdl(
    bdl_id: int,
    jours_mois: float = Form(None),
    montant_force: float = Form(None),
    commentaire: str = Form(None),
    db: Session = Depends(get_db),
):
    bdl = db.query(BDL).filter(BDL.id == bdl_id).first()
    if not bdl:
        raise HTTPException(404)
    if jours_mois is not None:
        bdl.jours_mois = jours_mois
        if bdl.mission.billing_type.value == "TJM_REGIE":
            bdl.montant_calcule = round(bdl.mission.tjm_or_forfait * jours_mois, 2)
    if montant_force is not None and montant_force > 0:
        bdl.montant_force = montant_force
    elif montant_force == 0:
        bdl.montant_force = None
    if commentaire is not None:
        bdl.commentaire = commentaire
    db.commit()
    return RedirectResponse(f"/bdl/{bdl_id}", status_code=303)


@router.post("/{bdl_id}/generer-pdf")
def generer_pdf_route(bdl_id: int, db: Session = Depends(get_db)):
    bdl = db.query(BDL).filter(BDL.id == bdl_id).first()
    if not bdl:
        raise HTTPException(404)
    generer_pdf(db, bdl)
    return RedirectResponse(f"/bdl/{bdl_id}", status_code=303)


@router.get("/{bdl_id}/pdf")
def telecharger_pdf(bdl_id: int, db: Session = Depends(get_db)):
    bdl = db.query(BDL).filter(BDL.id == bdl_id).first()
    if not bdl or not bdl.pdf_path or not Path(bdl.pdf_path).exists():
        raise HTTPException(404, "PDF non généré")
    return FileResponse(bdl.pdf_path, media_type="application/pdf", filename=Path(bdl.pdf_path).name)


@router.post("/{bdl_id}/envoyer")
def envoyer(
    bdl_id: int,
    destinataire: str = Form(...),
    db: Session = Depends(get_db),
):
    bdl = db.query(BDL).filter(BDL.id == bdl_id).first()
    if not bdl:
        raise HTTPException(404)
    if not bdl.pdf_path:
        generer_pdf(db, bdl)
    envoyer_bdl(db, bdl, destinataire)
    return RedirectResponse(f"/bdl/{bdl_id}", status_code=303)


@router.post("/{bdl_id}/signer")
def marquer_signe(bdl_id: int, db: Session = Depends(get_db)):
    bdl = db.query(BDL).filter(BDL.id == bdl_id).first()
    if not bdl:
        raise HTTPException(404)
    bdl.statut_document = StatutBDL.SIGNE
    db.commit()
    return RedirectResponse(f"/bdl/{bdl_id}", status_code=303)


@router.post("/{bdl_id}/upload-signe")
async def upload_signe(
    bdl_id: int,
    fichier: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    bdl = db.query(BDL).filter(BDL.id == bdl_id).first()
    if not bdl:
        raise HTTPException(404)

    from app.config import PDF_STORAGE_PATH
    client = bdl.mission.client.replace("/", "-").replace(" ", "_")
    folder = Path(PDF_STORAGE_PATH) / client / str(bdl.date_bdl.year) / bdl.date_bdl.strftime("%m-%B") / "signes"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"SIGNE_BDL_{bdl.id}_{fichier.filename}"

    content = await fichier.read()
    with open(dest, "wb") as f:
        f.write(content)

    bdl.statut_document = StatutBDL.SIGNE
    bdl.pdf_path = str(dest)
    db.commit()
    return RedirectResponse(f"/bdl/{bdl_id}", status_code=303)


# --- Templates client ---

@router.get("/templates/", response_class=HTMLResponse)
def list_templates(request: Request, db: Session = Depends(get_db)):
    tpls = db.query(ClientTemplate).order_by(ClientTemplate.client).all()
    return templates.TemplateResponse("bdl/templates.html", {"request": request, "tpls": tpls})


@router.post("/templates/upload")
async def upload_template(
    client: str = Form(...),
    fichier: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    from app.config import PDF_STORAGE_PATH
    folder = Path(PDF_STORAGE_PATH) / "_templates"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"template_{client.replace(' ', '_')}.xlsx"

    content = await fichier.read()
    with open(dest, "wb") as f:
        f.write(content)

    existing = db.query(ClientTemplate).filter(ClientTemplate.client == client).first()
    if existing:
        existing.template_path = str(dest)
    else:
        db.add(ClientTemplate(client=client, template_path=str(dest)))
    db.commit()
    return RedirectResponse("/bdl/templates/", status_code=303)
