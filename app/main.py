from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.database import Base, engine
from app.routers import missions, commandes, bdl
from app.templates_config import templates

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Facturation AT", version="1.0.0")


@app.on_event("startup")
def charger_donnees_demo():
    from app.database import SessionLocal
    from app.models import Mission, Commande, Poste, BillingType, ConsumptionMode
    from datetime import date

    db = SessionLocal()
    try:
        if db.query(Mission).count() > 0:
            return
        m1 = Mission(code="MC0001", client="CLIENT Y", mission_name="MISSION B",
                     consultant="BOB MARTIN", start_date=date(2025, 1, 1),
                     billing_type=BillingType.TJM_REGIE, tjm_or_forfait=600,
                     consumption_mode=ConsumptionMode.SEQUENTIEL, active=True)
        m2 = Mission(code="MC0002", client="CLIENT Z", mission_name="MISSION A",
                     consultant="ALICE TAGLI", start_date=date(2025, 1, 1),
                     billing_type=BillingType.TJM_REGIE, tjm_or_forfait=200,
                     consumption_mode=ConsumptionMode.POSTE_PAR_MOIS, active=True)
        db.add_all([m1, m2])
        db.flush()
        cmd1 = Commande(numero="CDE-2025-001", mission_id=m1.id)
        cmd2 = Commande(numero="CDE-2025-002", mission_id=m2.id)
        db.add_all([cmd1, cmd2])
        db.flush()
        db.add_all([
            Poste(commande_id=cmd1.id, numero_poste=1, montant_total=5000),
            Poste(commande_id=cmd1.id, numero_poste=2, montant_total=5000),
            Poste(commande_id=cmd1.id, numero_poste=3, montant_total=3000),
            Poste(commande_id=cmd2.id, numero_poste=1, montant_total=5000),
            Poste(commande_id=cmd2.id, numero_poste=2, montant_total=5000),
        ])
        db.commit()
    finally:
        db.close()

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
