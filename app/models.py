from datetime import datetime
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, Float,
    ForeignKey, Integer, String, Text
)
from sqlalchemy.orm import relationship
import enum
from app.database import Base


class BillingType(str, enum.Enum):
    TJM_REGIE = "TJM_REGIE"
    FORFAIT_MOIS_RPLSR = "FORFAIT_MOIS_RPLSR"
    FORFAIT_MOIS_RPLAR = "FORFAIT_MOIS_RPLAR"


class ConsumptionMode(str, enum.Enum):
    SEQUENTIEL = "SEQUENTIEL"
    POSTE_PAR_MOIS = "POSTE_PAR_MOIS"


class StatutBDL(str, enum.Enum):
    GENERE = "GENERE"
    ENVOYE = "ENVOYE"
    SIGNE = "SIGNE"


class StatutPoste(str, enum.Enum):
    NON_DEMARRE = "NON_DEMARRE"
    EN_COURS = "EN_COURS"
    TERMINE = "TERMINE"


class Mission(Base):
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    client = Column(String(200), nullable=False)
    mission_name = Column(String(200), nullable=False)
    consultant = Column(String(200), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    billing_type = Column(Enum(BillingType), nullable=False)
    tjm_or_forfait = Column(Float, nullable=False)
    nb_jours_forfait = Column(Integer, nullable=True)
    consumption_mode = Column(Enum(ConsumptionMode), nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    commandes = relationship("Commande", back_populates="mission")
    bdls = relationship("BDL", back_populates="mission")


class Commande(Base):
    __tablename__ = "commandes"

    id = Column(Integer, primary_key=True)
    numero = Column(String(50), nullable=False)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    mission = relationship("Mission", back_populates="commandes")
    postes = relationship("Poste", back_populates="commande", order_by="Poste.numero_poste")


class Poste(Base):
    __tablename__ = "postes"

    id = Column(Integer, primary_key=True)
    commande_id = Column(Integer, ForeignKey("commandes.id"), nullable=False)
    numero_poste = Column(Integer, nullable=False)
    montant_total = Column(Float, nullable=False)
    cloture_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    commande = relationship("Commande", back_populates="postes")
    bdls = relationship("BDL", back_populates="poste")

    @property
    def consomme(self):
        return sum(b.montant_effectif for b in self.bdls)

    @property
    def solde(self):
        return self.montant_total - self.consomme

    @property
    def statut(self):
        if self.cloture_admin:
            return StatutPoste.TERMINE
        if self.consomme == 0:
            return StatutPoste.NON_DEMARRE
        if self.solde <= 0:
            return StatutPoste.TERMINE
        return StatutPoste.EN_COURS

    @property
    def pct_consomme(self):
        if self.montant_total == 0:
            return 1.0
        return self.consomme / self.montant_total

    @property
    def pct_solde(self):
        return 1.0 - self.pct_consomme


class BDL(Base):
    __tablename__ = "bdls"

    id = Column(Integer, primary_key=True)
    date_bdl = Column(Date, nullable=False)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=False)
    commande_id = Column(Integer, ForeignKey("commandes.id"), nullable=True)
    poste_id = Column(Integer, ForeignKey("postes.id"), nullable=True)
    jours_mois = Column(Float, nullable=True)
    montant_calcule = Column(Float, nullable=False)
    montant_force = Column(Float, nullable=True)
    commentaire = Column(Text, nullable=True)
    statut_alerte = Column(String(50), nullable=True)
    statut_document = Column(Enum(StatutBDL), default=StatutBDL.GENERE)
    pdf_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    mission = relationship("Mission", back_populates="bdls")
    commande = relationship("Commande")
    poste = relationship("Poste", back_populates="bdls")
    email_logs = relationship("EmailLog", back_populates="bdl")

    @property
    def montant_effectif(self):
        return self.montant_force if self.montant_force is not None else self.montant_calcule


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True)
    bdl_id = Column(Integer, ForeignKey("bdls.id"), nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    recipient = Column(String(200), nullable=False)
    subject = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)

    bdl = relationship("BDL", back_populates="email_logs")


class ClientTemplate(Base):
    __tablename__ = "client_templates"

    id = Column(Integer, primary_key=True)
    client = Column(String(200), nullable=False, unique=True)
    template_path = Column(String(500), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
