from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.database import Base, engine
from app.routers import missions, commandes, bdl
from app.templates_config import templates

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Facturation AT", version="1.0.0")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(missions.router)
app.include_router(commandes.router)
app.include_router(bdl.router)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    from app.database import SessionLocal
    from app.models import BDL, Mission, Poste, StatutBDL
    from datetime import date

    db = SessionLocal()
    try:
        nb_missions = db.query(Mission).filter(Mission.active == True).count()
        nb_bdl_en_attente = db.query(BDL).filter(BDL.statut_document == StatutBDL.GENERE).count()
        nb_bdl_envoye = db.query(BDL).filter(BDL.statut_document == StatutBDL.ENVOYE).count()

        alertes = (
            db.query(BDL)
            .filter(BDL.statut_alerte.in_(["ALERTE_10", "ALERTE_30"]))
            .filter(BDL.statut_document != StatutBDL.SIGNE)
            .order_by(BDL.statut_alerte)
            .limit(10)
            .all()
        )

        derniers_bdl = (
            db.query(BDL)
            .order_by(BDL.created_at.desc())
            .limit(5)
            .all()
        )

        today = date.today()
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "nb_missions": nb_missions,
                "nb_bdl_en_attente": nb_bdl_en_attente,
                "nb_bdl_envoye": nb_bdl_envoye,
                "alertes": alertes,
                "derniers_bdl": derniers_bdl,
                "mois_courant": today.month,
                "annee_courante": today.year,
            },
        )
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}
