"""
Génération PDF des BDL.
Strategy :
  1. Cherche un template Excel spécifique au client (table client_templates)
  2. Sinon, utilise le template HTML standard
"""
import os
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import PDF_STORAGE_PATH
from app.models import BDL, ClientTemplate


def _storage_path(bdl: BDL) -> Path:
    client = bdl.mission.client.replace("/", "-").replace(" ", "_")
    annee = str(bdl.date_bdl.year)
    mois = bdl.date_bdl.strftime("%m-%B")
    folder = Path(PDF_STORAGE_PATH) / client / annee / mois
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"BDL_{bdl.mission.code}_{bdl.date_bdl.strftime('%Y%m')}_{bdl.id}.pdf"


def generer_pdf(db: Session, bdl: BDL) -> str:
    """Génère le PDF du BDL et retourne le chemin du fichier."""
    try:
        from weasyprint import HTML
    except ImportError:
        raise RuntimeError("WeasyPrint non installé")

    template_client = (
        db.query(ClientTemplate)
        .filter(ClientTemplate.client == bdl.mission.client)
        .first()
    )

    if template_client and Path(template_client.template_path).exists():
        html_content = _html_from_excel_template(template_client.template_path, bdl)
    else:
        html_content = _html_standard(bdl)

    output_path = _storage_path(bdl)
    HTML(string=html_content).write_pdf(str(output_path))

    bdl.pdf_path = str(output_path)
    db.commit()

    return str(output_path)


def _html_standard(bdl: BDL) -> str:
    mois_fr = [
        "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
    ]
    mois_label = mois_fr[bdl.date_bdl.month]
    annee = bdl.date_bdl.year
    montant = bdl.montant_effectif
    poste_num = bdl.poste.numero_poste if bdl.poste else "—"
    commande_num = bdl.commande.numero if bdl.commande else "—"
    jours = bdl.jours_mois if bdl.jours_mois else "—"

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 11pt; margin: 40px; color: #222; }}
  h1 {{ color: #1a3c6e; border-bottom: 2px solid #1a3c6e; padding-bottom: 8px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
  th {{ background: #1a3c6e; color: white; padding: 8px 12px; text-align: left; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #ddd; }}
  tr:nth-child(even) {{ background: #f5f8fc; }}
  .montant {{ font-size: 14pt; font-weight: bold; color: #1a3c6e; }}
  .footer {{ margin-top: 40px; font-size: 9pt; color: #888; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:9pt; }}
  .badge-alerte {{ background:#fff3cd; color:#856404; }}
</style>
</head>
<body>
<h1>Bon de Livraison — {mois_label} {annee}</h1>
<table>
  <tr><th colspan="2">Identification</th></tr>
  <tr><td>Client</td><td><strong>{bdl.mission.client}</strong></td></tr>
  <tr><td>Mission</td><td>{bdl.mission.mission_name}</td></tr>
  <tr><td>Consultant</td><td>{bdl.mission.consultant}</td></tr>
  <tr><td>N° Commande</td><td>{commande_num}</td></tr>
  <tr><td>N° Poste</td><td>{poste_num}</td></tr>
</table>

<table style="margin-top:20px">
  <tr><th colspan="2">Facturation — {mois_label} {annee}</th></tr>
  <tr><td>Type</td><td>{bdl.mission.billing_type.value.replace('_', ' ')}</td></tr>
  {"<tr><td>Jours travaillés</td><td>" + str(jours) + "</td></tr>" if bdl.jours_mois else ""}
  {"<tr><td>TJM</td><td>" + str(bdl.mission.tjm_or_forfait) + " €</td></tr>" if bdl.mission.billing_type.value == "TJM_REGIE" else ""}
  <tr><td><strong>Montant BDL</strong></td><td class="montant">{montant:,.2f} €</td></tr>
</table>

{"<p class='badge badge-alerte'>⚠ " + bdl.statut_alerte + "</p>" if bdl.statut_alerte and "ALERTE" in bdl.statut_alerte else ""}

<p class="footer">Document généré le {date.today().strftime('%d/%m/%Y')} — BDL #{bdl.id}</p>
</body>
</html>"""


def _html_from_excel_template(template_path: str, bdl: BDL) -> str:
    """Lecture d'un template Excel client et rendu HTML."""
    import openpyxl
    wb = openpyxl.load_workbook(template_path)
    ws = wb.active

    replacements = {
        "{{CLIENT}}": bdl.mission.client,
        "{{MISSION}}": bdl.mission.mission_name,
        "{{CONSULTANT}}": bdl.mission.consultant,
        "{{MOIS}}": bdl.date_bdl.strftime("%B %Y"),
        "{{COMMANDE}}": bdl.commande.numero if bdl.commande else "",
        "{{POSTE}}": str(bdl.poste.numero_poste) if bdl.poste else "",
        "{{MONTANT}}": f"{bdl.montant_effectif:,.2f}",
        "{{JOURS}}": str(bdl.jours_mois) if bdl.jours_mois else "",
        "{{TJM}}": str(bdl.mission.tjm_or_forfait),
    }

    rows_html = ""
    for row in ws.iter_rows(values_only=True):
        cells = ""
        for cell in row:
            val = str(cell) if cell is not None else ""
            for k, v in replacements.items():
                val = val.replace(k, v)
            cells += f"<td>{val}</td>"
        rows_html += f"<tr>{cells}</tr>"

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  body {{font-family:Arial,sans-serif;font-size:11pt;margin:40px;}}
  table {{width:100%;border-collapse:collapse;}}
  td {{padding:6px 10px;border:1px solid #ccc;}}
</style></head>
<body><table>{rows_html}</table></body></html>"""
