"""
BDL Generation Engine
Règles métier :
  - TJM_REGIE       : TJM × jours_mois
  - FORFAIT_MOIS_RPLSR : montant fixe (forçable)
  - Consommation SEQUENTIEL : postes dans l'ordre, on déborde sur le suivant si épuisé
  - Consommation POSTE_PAR_MOIS : le poste N correspond au mois N de la mission
"""
import calendar
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import ALERT_SEUIL_10, ALERT_SEUIL_30
from app.models import BDL, Commande, Mission, Poste, StatutBDL, StatutPoste


def _jours_ouvres(annee: int, mois: int) -> int:
    """Nombre de jours ouvrés (lun-ven) dans le mois."""
    _, nb_jours = calendar.monthrange(annee, mois)
    return sum(
        1
        for j in range(1, nb_jours + 1)
        if date(annee, mois, j).weekday() < 5
    )


def _poste_actif_sequentiel(postes: List[Poste]) -> Optional[Poste]:
    """Retourne le premier poste non terminé (ordre numéro_poste)."""
    for p in sorted(postes, key=lambda x: x.numero_poste):
        if p.statut != StatutPoste.TERMINE:
            return p
    return None


def _poste_actif_par_mois(postes: List[Poste], mission: Mission, annee: int, mois: int) -> Optional[Poste]:
    """
    Retourne le poste correspondant au mois N de la mission.
    Mois 1 de la mission = start_date.month / start_date.year.
    """
    start = mission.start_date
    mission_mois = (annee - start.year) * 12 + (mois - start.month) + 1  # 1-based
    sorted_postes = sorted(postes, key=lambda x: x.numero_poste)
    if 1 <= mission_mois <= len(sorted_postes):
        p = sorted_postes[mission_mois - 1]
        if p.statut != StatutPoste.TERMINE:
            return p
    return None


def _calcul_montant(mission: Mission, jours: int) -> float:
    if mission.billing_type.value == "TJM_REGIE":
        return round(mission.tjm_or_forfait * jours, 2)
    else:
        return mission.tjm_or_forfait


def _alerte(poste: Poste, montant_bdl: float) -> str:
    if poste is None:
        return ""
    solde_apres = poste.solde - montant_bdl
    pct_restant = solde_apres / poste.montant_total if poste.montant_total else 0
    if pct_restant <= ALERT_SEUIL_10:
        return "ALERTE_10"
    if pct_restant <= ALERT_SEUIL_30:
        return "ALERTE_30"
    return ""


def _bdl_existe(db: Session, mission_id: int, poste_id: Optional[int], annee: int, mois: int) -> bool:
    q = db.query(BDL).filter(
        BDL.mission_id == mission_id,
        BDL.date_bdl == date(annee, mois, 1),
    )
    if poste_id:
        q = q.filter(BDL.poste_id == poste_id)
    return q.first() is not None


def generer_bdl_mois(db: Session, annee: int, mois: int, regenerer: bool = False) -> List[BDL]:
    """
    Point d'entrée principal.
    Pour chaque mission active couvrant ce mois, génère les lignes BDL.
    """
    periode = date(annee, mois, 1)
    jours_ouvres = _jours_ouvres(annee, mois)
    missions_actives = (
        db.query(Mission)
        .filter(
            Mission.active == True,
            Mission.start_date <= periode,
        )
        .all()
    )

    bdls_crees: List[BDL] = []

    for mission in missions_actives:
        if mission.end_date and mission.end_date < periode:
            continue

        # Récupération de tous les postes actifs pour cette mission
        commandes = (
            db.query(Commande)
            .filter(Commande.mission_id == mission.id)
            .all()
        )
        postes_disponibles: List[Poste] = []
        for cmd in commandes:
            for p in cmd.postes:
                if p.statut != StatutPoste.TERMINE:
                    postes_disponibles.append(p)
        postes_disponibles.sort(key=lambda x: x.numero_poste)

        if not postes_disponibles and not commandes:
            # Pas de commande du tout
            bdl = _creer_bdl_sans_commande(db, mission, periode, jours_ouvres, regenerer)
            if bdl:
                bdls_crees.append(bdl)
            continue

        if not postes_disponibles:
            # Commandes existent mais tous les postes sont terminés
            bdl = _creer_bdl_sans_poste(db, mission, commandes, periode, jours_ouvres, regenerer)
            if bdl:
                bdls_crees.append(bdl)
            continue

        # Génération selon le mode de consommation
        if mission.consumption_mode.value == "SEQUENTIEL":
            nouveaux = _generer_sequentiel(db, mission, postes_disponibles, periode, jours_ouvres, regenerer)
        else:
            nouveaux = _generer_par_mois(db, mission, postes_disponibles, periode, jours_ouvres, annee, mois, regenerer)

        bdls_crees.extend(nouveaux)

    db.commit()
    for b in bdls_crees:
        db.refresh(b)
    return bdls_crees


def _creer_bdl_sans_commande(db, mission, periode, jours, regenerer):
    if not regenerer and _bdl_existe(db, mission.id, None, periode.year, periode.month):
        return None
    montant = _calcul_montant(mission, jours)
    bdl = BDL(
        date_bdl=periode,
        mission_id=mission.id,
        commande_id=None,
        poste_id=None,
        jours_mois=jours if mission.billing_type.value == "TJM_REGIE" else None,
        montant_calcule=montant,
        statut_alerte="COMMANDE_MANQUANTE",
        statut_document=StatutBDL.GENERE,
        commentaire="Aucune commande enregistrée pour cette mission",
    )
    db.add(bdl)
    return bdl


def _creer_bdl_sans_poste(db, mission, commandes, periode, jours, regenerer):
    if not regenerer and _bdl_existe(db, mission.id, None, periode.year, periode.month):
        return None
    montant = _calcul_montant(mission, jours)
    bdl = BDL(
        date_bdl=periode,
        mission_id=mission.id,
        commande_id=commandes[-1].id if commandes else None,
        poste_id=None,
        jours_mois=jours if mission.billing_type.value == "TJM_REGIE" else None,
        montant_calcule=montant,
        statut_alerte="TOUS_POSTES_TERMINES",
        statut_document=StatutBDL.GENERE,
        commentaire="Tous les postes de commande sont terminés",
    )
    db.add(bdl)
    return bdl


def _generer_sequentiel(db, mission, postes, periode, jours_total, regenerer) -> List[BDL]:
    """
    Répartit les jours du mois sur les postes dans l'ordre.
    Quand un poste est épuisé, on déborde sur le suivant.
    """
    bdls = []
    jours_restants = jours_total if mission.billing_type.value == "TJM_REGIE" else None

    for poste in postes:
        if mission.billing_type.value == "TJM_REGIE":
            if jours_restants <= 0:
                break
            # Combien de jours peut-on consommer sur ce poste ?
            jours_max_poste = poste.solde / mission.tjm_or_forfait if mission.tjm_or_forfait else jours_restants
            jours_bdl = min(jours_restants, jours_max_poste)
            jours_bdl = round(jours_bdl, 2)
            montant = round(mission.tjm_or_forfait * jours_bdl, 2)
            jours_restants -= jours_bdl
        else:
            jours_bdl = None
            montant = min(mission.tjm_or_forfait, poste.solde)

        if montant <= 0:
            continue

        if not regenerer and _bdl_existe(db, mission.id, poste.id, periode.year, periode.month):
            continue

        alerte = _alerte(poste, montant)
        bdl = BDL(
            date_bdl=periode,
            mission_id=mission.id,
            commande_id=poste.commande_id,
            poste_id=poste.id,
            jours_mois=jours_bdl,
            montant_calcule=montant,
            statut_alerte=alerte,
            statut_document=StatutBDL.GENERE,
        )
        db.add(bdl)
        bdls.append(bdl)

    return bdls


def _generer_par_mois(db, mission, postes, periode, jours, annee, mois, regenerer) -> List[BDL]:
    """
    Chaque mois de la mission consomme son poste dédié (poste N → mois N).
    Si le poste est presque épuisé, on le finalise et on ouvre le suivant.
    """
    bdls = []
    poste = _poste_actif_par_mois(postes, mission, annee, mois)
    if not poste:
        return bdls

    if mission.billing_type.value == "TJM_REGIE":
        montant = round(mission.tjm_or_forfait * jours, 2)
        # Cap sur le solde restant
        if montant > poste.solde:
            montant = poste.solde
    else:
        montant = min(mission.tjm_or_forfait, poste.solde)

    if montant <= 0:
        return bdls

    if not regenerer and _bdl_existe(db, mission.id, poste.id, periode.year, periode.month):
        return bdls

    alerte = _alerte(poste, montant)
    bdl = BDL(
        date_bdl=periode,
        mission_id=mission.id,
        commande_id=poste.commande_id,
        poste_id=poste.id,
        jours_mois=jours if mission.billing_type.value == "TJM_REGIE" else None,
        montant_calcule=montant,
        statut_alerte=alerte,
        statut_document=StatutBDL.GENERE,
    )
    db.add(bdl)
    bdls.append(bdl)
    return bdls
