import smtplib
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER
from app.models import BDL, EmailLog, StatutBDL


def envoyer_bdl(db: Session, bdl: BDL, destinataire: str) -> EmailLog:
    """Envoie le PDF du BDL par email et journalise."""
    mois_fr = [
        "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
    ]
    mois_label = mois_fr[bdl.date_bdl.month]
    sujet = (
        f"Bon de Livraison {mois_label} {bdl.date_bdl.year} — "
        f"{bdl.mission.client} / {bdl.mission.mission_name}"
    )

    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = destinataire
    msg["Subject"] = sujet

    corps = f"""Bonjour,

Veuillez trouver ci-joint le Bon de Livraison pour :
  - Client   : {bdl.mission.client}
  - Mission  : {bdl.mission.mission_name}
  - Période  : {mois_label} {bdl.date_bdl.year}
  - Montant  : {bdl.montant_effectif:,.2f} €

Merci de nous retourner ce BDL signé.

Cordialement,
"""
    msg.attach(MIMEText(corps, "plain", "utf-8"))

    if bdl.pdf_path and Path(bdl.pdf_path).exists():
        with open(bdl.pdf_path, "rb") as f:
            attach = MIMEApplication(f.read(), _subtype="pdf")
            attach.add_header(
                "Content-Disposition",
                "attachment",
                filename=Path(bdl.pdf_path).name,
            )
            msg.attach(attach)

    status = "OK"
    error_msg = None
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [destinataire], msg.as_string())
        bdl.statut_document = StatutBDL.ENVOYE
        db.commit()
    except Exception as e:
        status = "ERREUR"
        error_msg = str(e)

    log = EmailLog(
        bdl_id=bdl.id,
        sent_at=datetime.utcnow(),
        recipient=destinataire,
        subject=sujet,
        status=status,
        error_message=error_msg,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
