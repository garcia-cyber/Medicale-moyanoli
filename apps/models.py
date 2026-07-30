from django.db import models
from django.contrib.auth.models import User
import uuid
from decimal import Decimal  # Ajout crucial pour la sécurité des calculs financiers
from django.utils import timezone 
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings 
from django.db import transaction



# 1. CONFIGURATION ET BASE =============================================

class ConfigurationHopital(models.Model):
    taux_usd_en_cdf = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('2500.00'))
    derniere_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration du Taux"

    # AJOUTEZ CE BLOC ICI
    @classmethod
    def get_taux(cls):
        """Récupère le taux actuel ou renvoie 2500 par défaut si aucune config n'existe."""
        config = cls.objects.first()
        if config:
            return config.taux_usd_en_cdf
        return Decimal('2500.00')

    def __str__(self):
        return f"1 USD = {self.taux_usd_en_cdf} CDF"

# 2. ROLE =======================================================
class Role(models.Model):
    roleName = models.CharField(max_length=30)
 
    def __str__(self):
        return self.roleName

# 3. FONCTION ======================================================
class Fonction(models.Model):
    fonctionKey = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)
    userKey = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='user_fonction')
    autorisation = models.CharField(max_length=30, default='oui')

    def __str__(self):
        if self.userKey and self.fonctionKey:
            return f"{self.userKey.username} - {self.fonctionKey.roleName}"
        return f"Autorisation: {self.autorisation}"

# 4. PRESTATIONS ===================================================
class Prestation(models.Model):
    CATEGORIES = [
        ('ADM', 'Administratif'), 
        ('CONS', 'Consultation'),
        ('LABO', 'Laboratoire'), 
        ('SOIN', 'Soins'), 
        ('ECHO', 'Échographie'), 
        ('RADIO', 'Radiologie'),
        ('SCAN', 'Scanner'),
        ('IRM', 'IRM'),
        ('CARDIO', 'Cardiographie'),
        ('GYNECO', 'Gynécographie'),
        ('ONCO', 'Oncologie'),
        ('ORTHO', 'Orthopédie'),
        ('DERMA', 'Dermatologie'),
        ('OPHTA', 'Ophtalmologie'),
        ('PSY', 'Psychiatrie'),
        ('KINE', 'Rééducation / Kinésithérapie'),
        ('MED', 'Acte Médical'),       
        ('CHIR', 'Acte Chirurgical'),
        ('CONS_MAT', 'Consultation Maternité'), 
        ('MAT', 'Forfait Maternité / Accouchement'),
        ('DIALYSE', 'Dialyse'),
    ]

    libelle = models.CharField(
        max_length=200,
        verbose_name="Libellé",
    )
    code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Code de l'acte",
        help_text="Code interne ou nomenclature (ex: HD4H, DPJ, etc.)",
    )
    categorie = models.CharField(
        max_length=10,
        choices=CATEGORIES,
        verbose_name="Catégorie",
    )
    prix = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Prix (USD)",
    )

    # Valeurs de référence (uniquement pour le laboratoire)
    valeur_normale = models.CharField(
        max_length=150,
        blank=True,
        null=True, 
        verbose_name="Valeur Normale / Référence (Labo uniquement)",
        help_text="Ex: 70-110 mg/dl, Négatif, etc.",
    )

    # Durée typique de l'acte (surtout pour DIALYSE et certains actes)
    duree_typique_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Durée typique (min)",
        help_text="Durée normale de réalisation de l'acte (en minutes).",
    )

    # Paramètres de référence pour la dialyse
    debit_sang_reference_ml_min = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Débit sang de référence (ml/min)",
        help_text="Débit sanguin habituel pour cette prestation.",
    )
    debit_dialysat_reference_ml_min = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Débit dialysat de référence (ml/min)",
    )

    # Actif / inactif
    actif = models.BooleanField(
        default=True,
        verbose_name="Actif",
        help_text="Si décoché, la prestation n'apparaîtra plus dans les listes de sélection.",
    )

    def clean(self):
        # Valeur normale uniquement pour LABO
        if self.categorie != 'LABO':
            self.valeur_normale = None

        # Champs spécifiques dialyse uniquement pour DIALYSE
        if self.categorie != 'DIALYSE':
            self.duree_typique_minutes = None
            self.debit_sang_reference_ml_min = None
            self.debit_dialysat_reference_ml_min = None

        # Prix cohérent
        if self.prix < 0:
            raise ValidationError({"prix": "Le prix ne peut pas être négatif."})

    def __str__(self):
        return f"{self.libelle} ({self.get_categorie_display()}) - {self.prix} USD"

    class Meta:
        verbose_name = "Prestation"
        verbose_name_plural = "Prestations"
        ordering = ["categorie", "libelle"]


# 5. SERVICE =======================================================
class Service(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"

# 6. PATIENT =======================================================
class Patient(models.Model):
    # 1. Choix pour le type de patient
    TYPE_CHOICES = [
        ('SIMPLE', 'Patient Simple'),
        ('FIDELE', 'Patient Fidèle'),
        ('CONVENTIONNE', 'Patient Conventionné'),
    ]

    code_patient = models.CharField(max_length=20, unique=True, editable=False)
    noms = models.CharField(max_length=100)
    service = models.ForeignKey('Service', on_delete=models.PROTECT, related_name='patients', null=True)
    sexe = models.CharField(max_length=1, choices=[('M', 'Masculin'), ('F', 'Féminin')])
    age = models.CharField(max_length=30)
    adresse = models.TextField()
    telephone = models.CharField(max_length=20)
    profession = models.CharField(max_length= 30, null = True , blank= True)  
    
    # 2. Gestion financière
    type_patient = models.CharField(max_length=15, choices=TYPE_CHOICES, default='SIMPLE')
    a_carte_fidelite = models.BooleanField(default=False, verbose_name="Possède carte de fidélité")
    
    # Relation avec l'entreprise
    entreprise = models.ForeignKey(
        'Entreprise', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='patients', 
        verbose_name="Entreprise (si conventionné)"
    )
    
    fiche_payee = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='patients_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    # --- MÉTHODES ---
    def save(self, *args, **kwargs):
        if not self.code_patient:
            annee = timezone.now().year
            prefixe = f"MLY-{annee}-"
            last_patient = Patient.objects.filter(code_patient__startswith=prefixe).order_by('id').last()
            new_id = int(last_patient.code_patient.split('-')[-1]) + 1 if last_patient else 1
            self.code_patient = f"{prefixe}{new_id:04d}"
        super().save(*args, **kwargs)

    def a_deja_ete_consulte(self):
        return Consultation.objects.filter(triage__patient=self).exists()

    def a_une_consultation_en_attente(self):
        return Consultation.objects.filter(triage__patient=self, consultation_payee=False).exists()

    def est_en_regle(self):
        if not self.fiche_payee:
            return False
        if self.a_deja_ete_consulte() and self.a_une_consultation_en_attente():
            return False
        return True

    def __str__(self):
        return f"{self.noms} ({self.code_patient}) - {self.get_type_patient_display()}"
# 
# ====================================================================================================================
#  mise en jour de la dialyse 
#
class PrescriptionDialyse(models.Model):
  

    STATUT = [
        ("EN_ATTENTE_PAIEMENT", "En attente de paiement"),
        ("PAYEE", "Payée"),
        ("VALIDEE", "Validée par le médecin"),
        ("REJETEE", "Rejetée"),
        ("EN_COURS", "En cours"),
        ("TERMINEE", "Terminée"),
    ]

    patient = models.ForeignKey(
        "Patient",
        on_delete=models.CASCADE,
        related_name="prescriptions_dialyse",
        null=True,
        blank=True,
        verbose_name="Patient (système)",
        help_text="À remplir si le patient existe déjà dans le système.",
    )
    nom_patient_externe = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Nom du patient externe",
        help_text="À remplir si le patient n'existe pas dans le système (externe).",
    )

  

    # --- NOUVEAU : liaison avec Prestation ---
    prestation = models.ForeignKey(
        "Prestation",
        on_delete=models.PROTECT,
        related_name="prescriptions_dialyse",
        verbose_name="Prestation de dialyse",
        help_text="Prestation de catégorie Dialyse.",
        null=True,  # temporairement, pour migrations
        blank=True,
    )

    # --- NOUVEAU : montant total calculé ---
    montant_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Montant total (USD)",
        editable=False,
    )
    # ----------------------------------------

    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(null=True, blank=True, verbose_name="Date de fin")
    frequence_par_semaine = models.PositiveSmallIntegerField(
        help_text="Nombre de séances par semaine",
        verbose_name="Fréquence (séances/semaine)",
    )
    duree_seance_minutes = models.PositiveIntegerField(
        help_text="Durée typique d'une séance en minutes",
        verbose_name="Durée de séance (min)",
    )
    objectif_poids_sec_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Poids cible en kg",
        verbose_name="Poids sec (kg)",
    )

    sexe_patient_externe = models.CharField(
        max_length=1,
        choices=[("M", "Masculin"), ("F", "Féminin")],
        blank=True,
        null=True,
        verbose_name="Sexe (externe)",
    )
    age_patient_externe = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Âge (externe)",
    )
    telephone_patient_externe = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Téléphone (externe)",
    )

    statut = models.CharField(
        max_length=30,
        choices=STATUT,
        default="EN_ATTENTE_PAIEMENT",
        verbose_name="Statut",
    )
    remarques = models.TextField(blank=True, verbose_name="Remarques")
    active = models.BooleanField(default=True, verbose_name="Active")

    def clean(self):
        if not self.patient and not self.nom_patient_externe:
            raise ValidationError(
                "Vous devez renseigner soit un patient du système, soit le nom d'un patient externe."
            )
        if self.patient and self.nom_patient_externe:
            raise ValidationError(
                "Vous ne pouvez pas renseigner à la fois un patient du système et un patient externe."
            )

        # Optionnel : vérifier que la prestation est bien de catégorie DIALYSE
        if self.prestation and self.prestation.categorie != "DIALYSE":
            raise ValidationError(
                {"prestation": "La prestation doit appartenir à la catégorie « Dialyse »."}
            )

    def save(self, *args, **kwargs):
        # Calcul automatique du montant total à partir de la prestation
        if self.prestation:
            self.montant_total = self.prestation.prix
        else:
            self.montant_total = Decimal("0.00")
        super().save(*args, **kwargs)

    def __str__(self):
        if self.patient:
            return f"Dialyse {self.prestation} - {self.patient} (Système)"
        return f"Dialyse {self.prestation} - {self.nom_patient_externe} (Externe)"

    class Meta:
        verbose_name = "Prescription de dialyse"
        verbose_name_plural = "Prescriptions de dialyse"
#
# =============================================================================================================
class SeanceDialyse(models.Model):
    STATUT = [
        ("PLANIFIEE", "Planifiée"),
        ("EN_COURS", "En cours"),
        ("TERMINEE", "Terminée"),
        ("ANNULEE", "Annulée"),
    ]

    prescription = models.ForeignKey(
        PrescriptionDialyse,
        on_delete=models.CASCADE,
        related_name="seances",
        verbose_name="Prescription",
    )
    numero_seance = models.PositiveSmallIntegerField(
        help_text="Numéro de la séance dans la prescription",
        verbose_name="Numéro de séance",
    )
    date_heure_debut = models.DateTimeField(default=timezone.now)
    date_heure_fin = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(
        max_length=20,
        choices=STATUT,
        default="PLANIFIEE",
        verbose_name="Statut",
    )

    # Constantes de la séance (prescrites ou ajustées)
    duree_prevue_minutes = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Durée prévue (min)"
    )
    poids_cible_fin_seance_kg = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name="Poids cible fin de séance (kg)",
    )

    # Données cliniques avant
    poids_avant_kg = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name="Poids avant (kg)",
    )
    temperature_avant = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        verbose_name="Température avant (°C)",
    )
    pouls_avant = models.PositiveSmallIntegerField(null=True, blank=True)
    tension_avant = models.CharField(max_length=20, null=True, blank=True)

    # Paramètres machine
    machine = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name="Machine utilisée",
    )
    filtre = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name="Type de filtre / dialyseur",
    )
    debit_sang_ml_min = models.PositiveIntegerField(null=True, blank=True)
    debit_dialysat_ml_min = models.PositiveIntegerField(null=True, blank=True)
    anticoagulant = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="Ex: Héparine, dose",
    )

    # Données cliniques après
    poids_apres_kg = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name="Poids après (kg)",
    )
    temperature_apres = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        verbose_name="Température après (°C)",
    )
    pouls_apres = models.PositiveSmallIntegerField(null=True, blank=True)
    tension_apres = models.CharField(max_length=20, null=True, blank=True)

    # Biologie (optionnel)
    uree_avant = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    uree_apres = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    creatinine_avant = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    creatinine_apres = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    # Champs calculés
    poids_perdu_kg = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, editable=False
    )
    duree_reelle_minutes = models.PositiveIntegerField(
        null=True, blank=True, editable=False
    )

    # Facturation
    facturee = models.BooleanField(default=False, verbose_name="Facturée ?")

    def save(self, *args, **kwargs):
        # Calcul poids perdu
        if self.poids_avant_kg is not None and self.poids_apres_kg is not None:
            self.poids_perdu_kg = self.poids_avant_kg - self.poids_apres_kg

        # Calcul durée réelle
        if self.date_heure_debut and self.date_heure_fin:
            delta = self.date_heure_fin - self.date_heure_debut
            self.duree_reelle_minutes = int(delta.total_seconds() / 60)

        super().save(*args, **kwargs)

    def __str__(self):
        nom_patient = (
            str(self.prescription.patient)
            if self.prescription.patient
            else self.prescription.nom_patient_externe
        )
        return f"Séance #{self.numero_seance} - {nom_patient} - {self.date_heure_debut}"

    class Meta:
        verbose_name = "Séance de dialyse"
        verbose_name_plural = "Séances de dialyse"
        ordering = ["-date_heure_debut"]
        unique_together = ["prescription", "numero_seance"]
#
#
# =================================================================================================
#
class ConsommableDialyse(models.Model):
    nom = models.CharField(
        max_length=150,
        verbose_name="Nom du consommable",
        help_text="Ex: Ligne artério-veineuse, Filtre HF15, Aiguille 16G...",
    )
    reference = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="Référence"
    )
    categorie = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="Ex: Lignes, Filtres, Aiguilles, Kits, Autres",
    )
    actif = models.BooleanField(default=True)
    userConsommableDialyse = models.ForeignKey(User , on_delete=models.SET_NULL , null = True , blank = True , related_name="ConsommableDialyse")

    def __str__(self):
        return f"{self.nom} ({self.categorie or 'Dialyse'})"

    class Meta:
        verbose_name = "Consommable de dialyse"
        verbose_name_plural = "Consommables de dialyse"
        ordering = ["nom"]
#
#
# ======================================================================================

class ConsommationSeance(models.Model):
    """
    Consommation de matériel pour une séance donnée.
    Peut être lié à une prestation pour la facturation.
    """
    seance = models.ForeignKey(
        SeanceDialyse,
        on_delete=models.CASCADE,
        related_name="consommations",
        verbose_name="Séance",
    )
    consommable = models.ForeignKey(
        ConsommableDialyse,
        on_delete=models.CASCADE,
        related_name="consommations",
        verbose_name="Consommable",
    )
    quantite = models.PositiveSmallIntegerField(default=1)
    date_utilisation = models.DateTimeField(default=timezone.now)

    # Lien optionnel vers une prestation (si ce consommable est facturé via une prestation)
    prestation = models.ForeignKey(
        "Prestation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consommations_dialyse",
        verbose_name="Prestation associée",
    )

    @property
    def prix_unitaire(self):
        return self.prestation.prix if self.prestation else None

    @property
    def total(self):
        if self.prestation:
            return self.prestation.prix * self.quantite
        return None

    def __str__(self):
        return f"{self.consommable.nom} x{self.quantite} - {self.seance}"

    class Meta:
        verbose_name = "Consommation de séance"
        verbose_name_plural = "Consommations de séance"



class IncidentDialyse(models.Model):
    GRAVITE = [
        ("LEGER", "Léger"),
        ("MODERE", "Modéré"),
        ("GRAVE", "Grave"),
    ]

    seance = models.ForeignKey(
        SeanceDialyse,
        on_delete=models.CASCADE,
        related_name="incidents",
        verbose_name="Séance",
    )
    date_heure = models.DateTimeField(default=timezone.now)
    type_incident = models.CharField(
        max_length=100,
        verbose_name="Type d'incident",
        help_text="Ex: Hypotension, Crampes, Nausées, Vomissements, Malaise...",
    )
    userIncidentDialyse = models.ForeignKey(User , on_delete= models.SET_NULL , null = True , blank=True) 
    gravite = models.CharField(
        max_length=20,
        choices=GRAVITE,
        default="LEGER",
        verbose_name="Gravité",
    )
    description = models.TextField(blank=True)
    action_prise = models.TextField(blank=True)
    soignant = models.CharField(
        max_length=150, blank=True, null=True,
        verbose_name="Soignant ayant renseigné",
    )

    def __str__(self):
        return f"{self.type_incident} ({self.gravite}) - {self.seance}"

    class Meta:
        verbose_name = "Incident de dialyse"
        verbose_name_plural = "Incidents de dialyse"
        ordering = ["-date_heure"]


class ParametrageSeance(models.Model):
    seance = models.ForeignKey(
        SeanceDialyse,
        on_delete=models.CASCADE,
        related_name="parametrages",
        verbose_name="Séance",
    )
    minute_debut = models.PositiveSmallIntegerField(
        help_text="Minute de début par rapport au début de séance (0, 30, 60...)"
    )
    minute_fin = models.PositiveSmallIntegerField(
        help_text="Minute de fin par rapport au début de séance"
    )

    debit_sang_ml_min = models.PositiveIntegerField(null=True, blank=True)
    debit_dialysat_ml_min = models.PositiveIntegerField(null=True, blank=True)
    pression_arterielle = models.CharField(max_length=20, null=True, blank=True)
    pression_veineuse = models.CharField(max_length=20, null=True, blank=True)
    temperature_liquide = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True
    )
    remarques = models.TextField(blank=True)

    def __str__(self):
        return f"Paramétrage {self.minute_debit}-{self.minute_fin} - {self.seance}"

    class Meta:
        verbose_name = "Paramétrage de séance"
        verbose_name_plural = "Paramétrages de séance"
        ordering = ["seance", "minute_debut"]






# 6. PATIENT =======================================================
class Paiement(models.Model):
    CURRENCY = [('USD', 'USD'), ('CDF', 'CDF')]
    SERVICES = [
        ('FICHE', 'Fiche'),
        ('CONSULTATION', 'Consultation'),
        ('LABO', 'Labo'),
        ('ECHOGRAPHIE', 'Échographie'),
        ('RADIO', 'Radiographie'),
        ('SOIN', 'Soins'),
        ('MATERNITE', 'Maternité'),
        ('DECES', 'Actes de décès'),
        ('EXAMENS', 'Examens'),
        ('CHIRURGIE', 'Chirurgie'),
        ('CARTE_FIDELITE', 'Achat Carte de Fidélité'),
        ('PHARMACIE', 'Pharmacie'),
        ('EXAMEN_EXTERNE', 'Examen Externe'),
        ('ENTREPRISE', 'Paiement Entreprise'),
        ('HOSPITALISATION', 'Hospitalisation'),
        ('DIALYSE', 'Dialyse'),
        ('SEANCE_DIALYSE', 'Séance de dialyse'),
        ('CONSOMMABLE_DIALYSE', 'Consommable dialyse'),
    ]

    bloc_op = models.ForeignKey('BlocOperatoire', on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements')
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE, null=True, blank=True)
    demande_examen_externe = models.ForeignKey('DemandeExamenExterne', on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements')
    consultation = models.ForeignKey('Consultation', on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements')
    dossier_maternite = models.ForeignKey('Maternite', on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements')
    deces = models.ForeignKey('Deces', on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements')
    session = models.ForeignKey('SessionSoins', on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements')
    entreprise = models.ForeignKey('Entreprise', on_delete=models.CASCADE, null=True, blank=True, related_name='paiements')
    hospitalisation = models.ForeignKey('Hospitalisation', on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements')
    compte_rendu = models.OneToOneField('CompteRenduAccouchement', on_delete=models.SET_NULL, null=True, blank=True, related_name='paiement')

    prescription_dialyse = models.ForeignKey(
        'PrescriptionDialyse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paiements'
    )
    seance_dialyse = models.ForeignKey(
        'SeanceDialyse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paiements'
    )
    consommation_dialyse = models.ForeignKey(
        'ConsommationSeance',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paiements'
    )

    service = models.CharField(max_length=30, choices=SERVICES)
    montant_verse = models.DecimalField(max_digits=15, decimal_places=2)
    montant_reduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    devise = models.CharField(max_length=3, choices=CURRENCY, default='USD')
    date_paiement = models.DateTimeField(default=timezone.now)
    caissier = models.ForeignKey(User, on_delete=models.PROTECT)
    reste_a_payer = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Dette / Reste à payer"
    )

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.service == 'DIALYSE' and not self.prescription_dialyse:
            raise ValidationError("Le paiement de dialyse doit être lié à une prescription de dialyse.")

        if self.service == 'SEANCE_DIALYSE' and not self.seance_dialyse:
            raise ValidationError("Le paiement de séance doit être lié à une séance de dialyse.")

        if self.service == 'CONSOMMABLE_DIALYSE' and not self.consommation_dialyse:
            raise ValidationError("Le paiement consommable doit être lié à une consommation de séance.")

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if self.service == 'FICHE' and self.patient:
            self.patient.fiche_payee = True
            self.patient.save()
        elif self.service == 'CONSULTATION' and self.consultation:
            self.consultation.consultation_payee = True
            self.consultation.save()
        elif self.service == 'CARTE_FIDELITE' and self.patient:
            self.patient.a_carte_fidelite = True
            self.patient.type_patient = 'FIDELE'
            self.patient.save()

        if self.hospitalisation:
            total_due = Decimal(str(self.hospitalisation.cout_total))
            paiements_existants = self.hospitalisation.paiements.exclude(pk=self.pk)
            total_deja_verse = paiements_existants.aggregate(Sum('montant_verse'))['montant_verse__sum'] or 0
            total_deja_reduit = paiements_existants.aggregate(Sum('montant_reduction'))['montant_reduction__sum'] or 0
            self.reste_a_payer = max(
                Decimal('0.00'),
                total_due - (total_deja_reduit + self.montant_reduction) - (total_deja_verse + self.montant_verse)
            )
            self.hospitalisation.est_payee = (self.reste_a_payer <= 0)
            self.hospitalisation.save()

        if self.session:
            tous_paiements = self.session.paiements.exclude(pk=self.pk)
            total_deja_verse = tous_paiements.aggregate(Sum('montant_verse'))['montant_verse__sum'] or 0
            total_deja_reduit = tous_paiements.aggregate(Sum('montant_reduction'))['montant_reduction__sum'] or 0
            self.reste_a_payer = max(
                Decimal('0.00'),
                self.session.total_a_payer - (total_deja_reduit + self.montant_reduction) - (total_deja_verse + self.montant_verse)
            )
            self.session.est_payee = (self.reste_a_payer <= 0)
            self.session.save()

        if self.demande_examen_externe:
            total_due = self.demande_examen_externe.total_a_payer
            paiements_existants = self.demande_examen_externe.paiements.exclude(pk=self.pk)
            total_deja_verse = paiements_existants.aggregate(Sum('montant_verse'))['montant_verse__sum'] or 0
            self.reste_a_payer = max(
                Decimal('0.00'),
                total_due - (total_deja_verse + self.montant_verse)
            )
            if self.reste_a_payer <= 0:
                self.demande_examen_externe.statut = 'PAYE'
                self.demande_examen_externe.save()

        if self.service == 'ENTREPRISE' and self.entreprise:
            montant_usd = self.montant_verse
            if self.devise == 'CDF':
                from .models import ConfigurationHopital
                taux = ConfigurationHopital.get_taux()
                montant_usd = self.montant_verse / taux
            total_a_deduire = montant_usd + self.montant_reduction
            self.entreprise.dette_mensuelle = max(Decimal('0.00'), self.entreprise.dette_mensuelle - total_a_deduire)
            self.entreprise.save()

        if self.service == 'DIALYSE' and self.prescription_dialyse:
            total_due = getattr(self.prescription_dialyse, "montant_total", Decimal("0.00"))
            paiements_existants = self.prescription_dialyse.paiements.exclude(pk=self.pk)
            total_verse = paiements_existants.aggregate(Sum('montant_verse'))['montant_verse__sum'] or Decimal('0.00')
            total_reduit = paiements_existants.aggregate(Sum('montant_reduction'))['montant_reduction__sum'] or Decimal('0.00')

            self.reste_a_payer = max(
                Decimal('0.00'),
                total_due - (total_verse + self.montant_verse) - (total_reduit + self.montant_reduction)
            )

            if self.reste_a_payer <= 0:
                self.prescription_dialyse.statut = 'PAYEE'
                self.prescription_dialyse.save(update_fields=['statut'])

        super().save(*args, **kwargs)

        if is_new:
            from .models import Facture
            Facture.objects.create(
                paiement=self,
                numero_facture=f"FAC-{timezone.now().strftime('%y%m%d')}-{self.id}"
            )

    def __str__(self):
        return f"{self.service} - {self.montant_verse} {self.devise}"

# 8. FACTURE =======================================================
class Facture(models.Model):
    paiement = models.OneToOneField(Paiement, on_delete=models.CASCADE, related_name='facture_liee')
    numero_facture = models.CharField(max_length=50, unique=True)
    date_emission = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Facture {self.numero_facture} ({self.paiement.get_service_display()})"



# =================================================================================================================
class SessionSoins(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    date_creation = models.DateTimeField(auto_now_add=True)
    est_payee = models.BooleanField(default=False)
    
    @property
    def total_a_payer(self):
        return sum(item.prix_facture for item in self.items.all())

    def __str__(self):
        return f"Session de {self.patient.noms} du {self.date_creation.strftime('%d/%m/%Y')}"

class LigneFacture(models.Model):
    session = models.ForeignKey(SessionSoins, related_name="items", on_delete=models.CASCADE)
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField(default=1)
    prix_facture = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        if not self.prix_facture:
            self.prix_facture = self.prestation.prix * self.quantite
        super().save(*args, **kwargs)
        
# 9. SIGNES VITAUX ==================================================
class SigneVital(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    temperature = models.DecimalField(max_digits=4, decimal_places=1) 
    poids = models.DecimalField(max_digits=5, decimal_places=2) 
    tension_arterielle = models.CharField(max_length=10) 
    frequence_cardiaque = models.IntegerField()
    frequence_respiratoire = models.IntegerField(null=True, blank=True)
    saturation_oxygene = models.IntegerField(null=True, blank=True) 
    date_prelevement = models.DateTimeField(default=timezone.now)
    infirmier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    est_consulte = models.BooleanField(default=False)
    session = models.ForeignKey(SessionSoins, on_delete=models.CASCADE, related_name='signes_vitaux', null=True)

    def __str__(self):
        return f"Signes vitaux de {self.patient.noms} le {self.date_prelevement}"



# 10. CONSULTATION ==================================================
class Consultation(models.Model):
    # Propriété pour accéder facilement au patient
    @property
    def patient(self):
        return self.triage.patient

    triage = models.OneToOneField(SigneVital, db_index=True, on_delete=models.CASCADE)
    medecin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    motif_consultation = models.TextField(verbose_name="Motif")
    antecedent = models.CharField(max_length  = 30 , null = True , blank = True)
    histoire_maladie = models.TextField(verbose_name="Histoire de la maladie")
    examen_physique = models.TextField(verbose_name="Examen physique")
    complement_d_anamnese = models.CharField(max_length=200, null=True)
    hypothese_diagnostique = models.TextField(verbose_name="Hypothèse diagnostique")
    date_creation = models.DateTimeField(default=timezone.now)
    
    consultation_payee = models.BooleanField(default=False, verbose_name="Consultation payée")

    session = models.OneToOneField(SessionSoins, on_delete=models.CASCADE, null=True)
    

    @property
    def est_accessible(self):
        return self.session.est_payee if self.session else False

    def __str__(self):
        return f"Consultation de {self.triage.patient.noms} le {self.date_creation.strftime('%d/%m/%Y')}"

    @property
    def total_examens_a_payer(self):
        examens_lies = self.examens.all()
        return sum((ex.prestation.prix * ex.quantite) for ex in examens_lies if ex.prestation and ex.prestation.prix)

    @property
    def est_accessible(self):
        return self.consultation_payee

# 11. DEMANDE EXAMEN ===============================================
class DemandeExamen(models.Model):
    STATUT = [
        ('EN_ATTENTE', 'En attente'),
        ('TERMINE', 'Terminé'),
        ('ANNULE', 'Annulé'),
    ]
    
    consultation = models.ForeignKey(Consultation, related_name='examens', on_delete=models.CASCADE)
    prestation = models.ForeignKey(Prestation, on_delete=models.PROTECT)
    indication = models.TextField(blank=True, help_text="Note du médecin pour le technicien")
    resultat = models.TextField(blank=True, null=True)
    image_resultat = models.ImageField(upload_to='resultats_examens/', blank=True, null=True)
    
    # Informations sur la réalisation de l'examen
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        related_name='examens_realises', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    statut = models.CharField(max_length=20, choices=STATUT, default='EN_ATTENTE')
    date_demande = models.DateTimeField(default=timezone.now)
    date_realisation = models.DateTimeField(null=True, blank=True)
    quantite = models.PositiveIntegerField(default=1)

    def __str__(self):
        # Utilisation d'une structure sécurisée pour éviter les erreurs si la relation est nulle
        try:
            nom_patient = self.consultation.triage.patient.noms
        except (AttributeError, ObjectDoesNotExist):
            nom_patient = "Patient inconnu"
            
        return f"{self.prestation.libelle} pour {nom_patient}"

class Ordonnance(models.Model):
    TYPE_CHOICES = [('URGENCE', 'Ordonnance d’Urgence'), ('DEFINITIVE', 'Ordonnance Définitive')]
    
    consultation = models.ForeignKey('Consultation', on_delete=models.CASCADE)
    date_prescrite = models.DateTimeField(default=timezone.now)
    type_ordonnance = models.CharField(max_length=20, choices=TYPE_CHOICES, default='URGENCE')
    diagnostic = models.CharField(max_length=255, blank=True)
    observation = models.TextField(blank=True)

    def __str__(self):
        # Utilisation d'une structure sécurisée pour éviter les erreurs de type DoesNotExist
        try:
            nom_patient = self.consultation.triage.patient.noms
        except (AttributeError, ObjectDoesNotExist):
            nom_patient = "Patient non identifié"
            
        return f"Ordonnance {self.get_type_ordonnance_display()} - {nom_patient}"

class Medicament(models.Model):
    # Utilisation des guillemets pour éviter l'erreur de référence circulaire
    ordonnance = models.ForeignKey('Ordonnance', on_delete=models.CASCADE, related_name='medicaments')
    nom = models.CharField(max_length=255)
    posologie = models.CharField(max_length=255)
    duree = models.CharField(max_length=100)
    
    STATUT_CHOICES = [('EN_COURS', 'En cours'), ('STOPPE', 'Stoppé')]
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_COURS')

    def __str__(self):
        return f"{self.nom} ({self.statut})"





# 13. LIGNE MEDICAMENT =============================================
class LigneMedicament(models.Model):
    STATUT_MEDOC = [
        ('EN_COURS', 'En cours'),
        ('STOPPE', 'Stoppé / Changé'),
    ]
    
    # Utilisez un related_name unique pour éviter les conflits
    ordonnance = models.ForeignKey(
        'Ordonnance', 
        related_name='lignes_medicaments', 
        on_delete=models.CASCADE
    )
    
    nom_medicament = models.CharField(max_length=200)
    posologie = models.CharField(max_length=200, help_text="ex: 1 tab 3 fois par jour")
    duree = models.CharField(max_length=100, help_text="ex: 5 jours")
    statut = models.CharField(max_length=20, choices=STATUT_MEDOC, default='EN_COURS')
    motif_arret = models.TextField(blank=True, null=True, help_text="Pourquoi le médecin a changé ce médicament")
    date_modification = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.nom_medicament} - {self.statut}"

# 14. DEPENSE ======================================================
class Depense(models.Model):
    CURRENCY = [('USD', 'USD'), ('CDF', 'CDF')]
    CATEGORIES = [
        ('LABO_REACTIF', 'Réactifs & Matériel Labo'),
        ('PHARMA_STOCK', 'Achat Stock Pharmacie'),
        ('CARBURANT', 'Carburant Générateur'),
        ('MAINTENANCE', 'Maintenance & Réparations'),
        ('ADMIN', 'Frais Administratifs & Bureau'),
        ('SALAIRE', 'Avances & Salaires Personnel'),
        ('AUTRE', 'Autre dépense'),
    ]

    motif = models.CharField(max_length=50, choices=CATEGORIES, verbose_name="Motif")
    description = models.TextField(blank=True, null=True)
    montant = models.DecimalField(max_digits=15, decimal_places=2)
    devise = models.CharField(max_length=3, choices=CURRENCY, default='USD')
    date_depense = models.DateTimeField(default=timezone.now)
    auteur = models.ForeignKey('auth.User', on_delete=models.PROTECT, verbose_name="Enregistré par")
    beneficiaire = models.CharField(max_length=150, blank=True, null=True, verbose_name="Bénéficiaire")

    class Meta:
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"

    def clean(self):
        # Correction 1 : Retrait de l'import circulaire de Paiement (on l'appelle directement)
        # Correction 2 : Utilisation d'un entier 0 à la place du float 0.0 pour éviter le TypeError avec Decimal
        total_entrees = Paiement.objects.filter(devise=self.devise).aggregate(
            total=Sum('montant_verse')
        )['total'] or 0

        toutes_les_depenses = Depense.objects.filter(devise=self.devise)
        if self.pk:
            toutes_les_depenses = toutes_les_depenses.exclude(pk=self.pk)
            
        total_sorties = toutes_les_depenses.aggregate(total=Sum('montant'))['total'] or 0

        solde_disponible = total_entrees - total_sorties

        if self.montant > solde_disponible:
            raise ValidationError(
                f"Opération refusée. Solde de caisse insuffisant en {self.devise}. "
                f"Disponible : {solde_disponible:.2f} {self.devise}. "
                f"Montant demandé : {self.montant:.2f} {self.devise}."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Dépense {self.id} - {self.montant} {self.devise} ({self.get_motif_display()})"

# 15. HOSPITALISATION ET CHAMBRES ==================================
class TypeChambre(models.Model):
    libelle = models.CharField(max_length=100)
    # Utilisation de DecimalField pour la précision monétaire
    prix_nuitée = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return self.libelle

class Chambre(models.Model):
    # En ajoutant default="", Django ne vous posera plus la question
    nom = models.CharField(max_length=50, default="Sans nom") 
    type_chambre = models.ForeignKey(TypeChambre, on_delete=models.CASCADE)
    est_active = models.BooleanField(default=True)

    def __str__(self):
        return self.nom

class Lit(models.Model):
    chambre = models.ForeignKey(Chambre, related_name='lits', on_delete=models.CASCADE)
    nom_lit = models.CharField(max_length=50)
    est_occupe = models.BooleanField(default=False)
    est_actif = models.BooleanField(default=True)


    def __str__(self) :
        return self.nom_lit

# =====================================================================
# hospitalisation 


class Hospitalisation(models.Model):
    # Statuts de l'hospitalisation
    STATUT_CHOICES = [
        ('EN_COURS', 'En cours'),
        ('TERMINE', 'Terminé'),
        ('ANNULE', 'Annulé'),
    ]

    patient = models.ForeignKey('Patient', on_delete=models.CASCADE, related_name='sejours')
    lit = models.ForeignKey('Lit', on_delete=models.PROTECT, related_name='occupations')
    date_entree = models.DateTimeField(default=timezone.now)
    date_sortie = models.DateTimeField(null=True, blank=True)
    motif_admission = models.TextField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_COURS')
    observations = models.TextField(blank=True, null=True)
    est_actif = models.BooleanField(default=True)
    
    # Champ pour suivre l'état de paiement en base
    est_payee = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """
        Logique automatique : met à jour l'état du lit lors de l'enregistrement.
        """
        if self.statut == 'EN_COURS':
            self.lit.est_occupe = True
        elif self.statut == 'TERMINE' or self.statut == 'ANNULE':
            self.lit.est_occupe = False
            
        self.lit.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Hosp. {self.patient.noms} - Lit {self.lit.nom_lit}"

    @property
    def prix_par_jour(self):
        # Accède au prix défini dans le TypeChambre via la chambre du lit
        return self.lit.chambre.type_chambre.prix_nuitée

    @property
    def nombre_jours(self):
        """Calcule la durée de l'hospitalisation."""
        date_fin = self.date_sortie.date() if self.date_sortie else timezone.now().date()
        date_deb = self.date_entree.date()
        delta = date_fin - date_deb
        return max(1, delta.days)

    @property
    def cout_total(self):
        """Calcule le coût total basé sur le nombre de jours."""
        return Decimal(str(self.nombre_jours)) * Decimal(str(self.prix_par_jour))

    def get_reste_a_payer(self):
        """
        Calcule le reste à payer en tenant compte des paiements et réductions.
        L'utilisation de quantize(Decimal('0.01')) garantit une précision monétaire.
        """
        total_paye = self.paiements.aggregate(Sum('montant_verse'))['montant_verse__sum'] or 0
        total_reduit = self.paiements.aggregate(Sum('montant_reduction'))['montant_reduction__sum'] or 0
        
        reste = self.cout_total - (Decimal(str(total_paye)) + Decimal(str(total_reduit)))
        
        # On retourne max 0.00 et on arrondit à 2 décimales
        return max(Decimal('0.00'), reste.quantize(Decimal('0.01')))

    class Meta:
        verbose_name = "Hospitalisation"
        verbose_name_plural = "Hospitalisations"


# ==============================================================================================
# 
class SuiviQuotidien(models.Model):
    hospitalisation = models.ForeignKey(Hospitalisation, on_delete=models.CASCADE, related_name='suivis_journaliers')
    infirmier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    # Évolution quotidienne
    date_suivi = models.DateTimeField(auto_now_add=True)
    etat_general = models.TextField(verbose_name="État général du patient")
    constantes_du_jour = models.TextField(verbose_name="Constantes (TA, Pouls, Temp...)")
    soins_effectues = models.TextField(verbose_name="Soins et médicaments administrés")
    ta = models.CharField(max_length=20, verbose_name="TA", default="N/A")
    pouls = models.CharField(max_length=20, verbose_name="Pouls", default="N/A")
    temp = models.CharField(max_length=20, verbose_name="Temp (°C)", default="N/A")
    class Meta:
        verbose_name = "Suivi Quotidien"
        verbose_name_plural = "Suivis Quotidiens"
        ordering = ['-date_suivi']

    def __str__(self):
        return f"Suivi de {self.hospitalisation.patient.noms} le {self.date_suivi.strftime('%d/%m/%Y')}"


# =============================================================================================
#
class Kardex(models.Model):
    hospitalisation = models.ForeignKey('Hospitalisation', on_delete=models.CASCADE, related_name='kardex_items')
    medicament = models.CharField(max_length=200 , null = True)
    posologie = models.CharField(max_length=100 , null = True)
    voie_administration = models.CharField(max_length=50 , null = True)
    date_prescription = models.DateTimeField(auto_now_add=True , null = True)
    est_actif = models.BooleanField(default=True , null = True)

    def __str__(self):
        return f"{self.medicament} - {self.hospitalisation.patient.noms}"

    def get_admin_pour_jour(self, date):
        return self.administrations.filter(date_admin=date).first()

class AdministrationKardex(models.Model):
    """Ce modèle enregistre si le médicament a été administré pour une date donnée"""
    kardex = models.ForeignKey(Kardex, on_delete=models.CASCADE, related_name='administrations')
    date_admin = models.DateField() # Exemple : 23/06/2026
    
    matin = models.BooleanField(default=False)
    midi = models.BooleanField(default=False)
    soir = models.BooleanField(default=False)

    class Meta:
        # Empêche d'avoir deux fois la même date pour le même médicament
        unique_together = ('kardex', 'date_admin')

# =======================================================================================
#
class RendezVous(models.Model):
    hospitalisation = models.ForeignKey('Hospitalisation', on_delete=models.CASCADE)
    date_rdv = models.DateTimeField()
    motif = models.CharField(max_length=200)
    note = models.TextField(blank=True, null=True)
    
    # Nouveau champ pour enregistrer l'utilisateur
    enregistre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )

    def est_urgent(self):
        # On calcule la différence entre la date du RDV et maintenant
        delta = self.date_rdv - timezone.now()
        # Alerte si le rendez-vous est dans moins de 24h (86400 secondes) 
        # et qu'il n'est pas encore passé
        return 0 < delta.total_seconds() < 86400

    def __str__(self):
        return f"RDV pour {self.hospitalisation.patient.noms} le {self.date_rdv}"

# =======================================================================================
# Entreprise
# =======================================================================================
class Entreprise(models.Model):
    nom = models.CharField(max_length=255, verbose_name="Nom de l'entreprise")
    contact_responsable = models.CharField(max_length=100, verbose_name="Numéro du responsable")
    date_enregistrement = models.DateTimeField(default=timezone.now, verbose_name="Date d'enregistrement")
    dette_mensuelle = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Dette mensuelle", 
        null = True , 
        blank = True
    )

    def __str__(self):
        return self.nom



## ==================================================================================
# model maternite 
class Maternite(models.Model):
    # Liste des groupes sanguins autorisés
    GROUPE_SANGUIN_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='dossiers_maternite')
    date_admission = models.DateTimeField(auto_now_add=True)
    terme_prevu = models.DateField()
    
    # Utilisation des 'choices' ici
    groupe_sanguin = models.CharField(
        max_length=3, 
        choices=GROUPE_SANGUIN_CHOICES,
        default='O+'
    )
    
    enregistre_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    est_paye = models.BooleanField(default=False, verbose_name="Frais d'ouverture réglés")

    def __str__(self):
        return f"Maternité de {self.patient.noms} - {self.date_admission.strftime('%d/%m/%Y')}"


# =======================================================================================
#
# model ConsultationMaternite 
class ConsultationMaternite(models.Model):
    # Lien vers le dossier de maternité spécifique
    dossier_maternite = models.ForeignKey(Maternite, on_delete=models.CASCADE, related_name='consultations')
    
    date_consultation = models.DateTimeField(auto_now_add=True)
    poids = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Poids (kg)")
    tension_arterielle = models.CharField(max_length=10, verbose_name="Tension artérielle")
    hauteur_uterine = models.IntegerField(verbose_name="Hauteur utérine (cm)")
    bruits_cardiaques_foetaux = models.CharField(max_length=20, verbose_name="BCF")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes médicales")
    
    # Médecin/Infirmier ayant fait la consultation
    effectue_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Consultation du {self.date_consultation.strftime('%d/%m/%Y')} pour {self.dossier_maternite.patient.noms}"

    # Pour facturer automatiquement la consultation lors de sa saisie
    prestation = models.ForeignKey(
        Prestation, 
        on_delete=models.SET_NULL, 
        null=True, 
        limit_choices_to={'categorie': 'CONS_MAT'}
    )



# =======================================================================================================
#
class Deces(models.Model):
    # Gestion de l'identité du défunt
    patient = models.ForeignKey('Patient', on_delete=models.SET_NULL, null=True, blank=True)
    nom_patient_externe = models.CharField(max_length=255, null=True, blank=True)
    
    # Informations biographiques (du certificat)
    date_naissance = models.DateField(verbose_name="Date de naissance")
    lieu_naissance = models.CharField(max_length=100, verbose_name="Lieu de naissance")
    
    # Adresse du défunt
    adresse_avenue = models.CharField(max_length=100, verbose_name="Avenue")
    adresse_numero = models.CharField(max_length=20, verbose_name="Numéro")
    adresse_quartier = models.CharField(max_length=100, verbose_name="Quartier")
    adresse_commune = models.CharField(max_length=100, verbose_name="Commune")
    
    # Informations sur le décès
    date_deces = models.DateTimeField(verbose_name="Date et heure du décès")
    cause_deces = models.TextField(verbose_name="Cause du décès")
    
    # Informations médicales et certification
    etablissement = models.CharField(max_length=255, default="Hôpital Paradis Center")
    certifie_par = models.CharField(max_length=255, verbose_name="Nom du médecin")
    numero_cnom = models.CharField(max_length=50, verbose_name="Numéro CNOM du médecin")
    
    # Métadonnées
    notes = models.TextField(blank=True)
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        nom = self.patient.nom if self.patient else self.nom_patient_externe
        return f"Décès : {nom} - {self.date_deces.strftime('%d/%m/%Y')}"

    class Meta:
        verbose_name = "Certificat de décès"
        verbose_name_plural = "Certificats de décès"



# ====================================================================
# ORIENTATION 
class Orientation(models.Model):
    DESTINATIONS = (
        ('PHARMACIE', 'Pharmacie'),
        ('HOSPITALISATION', 'Hospitalisation'),
        ('SALLE_SOINS', 'Salle de Soins'),
        ('BLOC_OPERATOIRE', 'Bloc Opératoire'),
        ('ACCOUCHEMENT', 'Accouchement'),  # Ajout de l'option ici
        ('SORTIE', 'Sortie/Retour à domicile'),
    )

    consultation = models.OneToOneField(
        Consultation, 
        on_delete=models.CASCADE, 
        related_name='orientation'
    )
    # QUI oriente ?
    medecin_orientateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='orientations_effectuees'
    )
    destination = models.CharField(max_length=50, choices=DESTINATIONS)
    observation = models.TextField(blank=True, null=True)
    date_orientation = models.DateTimeField(auto_now_add=True)
    est_admis = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.consultation.triage.patient.noms} orienté vers {self.get_destination_display()} par Dr. {self.medecin_orientateur.username}"



# ============================================================================================
#
#
class SoinOccasionnel(models.Model):
    paiement = models.ForeignKey(
        'Paiement', 
        on_delete=models.CASCADE, 
        related_name="soins_lies" # Permet de faire paiement.soins_lies.all()
    )
    nom_patient = models.CharField(max_length=200)
    prestation = models.ForeignKey('Prestation', on_delete=models.CASCADE)
    date_soin = models.DateTimeField(auto_now_add=True)
    effectue_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    est_effectue = models.BooleanField(default=False)

    def __str__(self):
        return f"Soin: {self.nom_patient} - {self.prestation.libelle}"


# =======================================================================================================================
#
# GESTION DE PHARMACIE 
#
# =======================================================================================================================

class ProduitPharmacie(models.Model):
    DEVISE_CHOICES = [('USD', 'USD'), ('CDF', 'CDF')]
    
    nom = models.CharField(max_length=200, verbose_name="Nom commercial / DCI")
    forme = models.CharField(max_length=100)
    dosage = models.CharField(max_length=50)
    categorie = models.CharField(max_length=100)
    unites_par_carton = models.PositiveIntegerField(default=1)
    devise = models.CharField(max_length=3, choices=DEVISE_CHOICES, default='USD')
    prix_achat_unitaire = models.DecimalField(max_digits=12, decimal_places=2)
    prix_vente_unitaire = models.DecimalField(max_digits=12, decimal_places=2)
    enregistre_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    date_enregistrement = models.DateTimeField(auto_now_add=True)
    stock_initial = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('nom', 'forme', 'dosage')

    def __str__(self):
        return f"{self.nom} - {self.dosage}"

    @property
    def prix_vente_cdf(self):
        return self.prix_vente_unitaire * ConfigurationHopital.get_taux()

# --- 3. LOT ---
class LotPharmacie(models.Model):
    produit = models.ForeignKey('ProduitPharmacie', related_name='les_lots', on_delete=models.CASCADE)
    numero_lot = models.CharField(max_length=100)
    quantite_initiale = models.PositiveIntegerField(default=0)
    quantite_actuelle = models.PositiveIntegerField(default=0)
    date_peremption = models.DateField()
    date_entree = models.DateField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.quantite_actuelle = self.quantite_initiale
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['date_peremption']

    def __str__(self):
        return f"{self.produit.nom} | Lot: {self.numero_lot} | Stock: {self.quantite_actuelle}"


# --- 4. MOUVEMENT DE STOCK ---
class MouvementStock(models.Model):
    TYPE_MOUVEMENT = (('ENTREE', 'Entrée'), ('SORTIE', 'Sortie'), ('AJUSTEMENT', 'Ajustement'))
    
    lot = models.ForeignKey(LotPharmacie, on_delete=models.PROTECT, related_name='mouvements')
    type_mouvement = models.CharField(max_length=20, choices=TYPE_MOUVEMENT)
    quantite_unites = models.IntegerField()
    effectue_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    date_mouvement = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # CORRECTION : On ne modifie plus le stock ici.
        # Le mouvement est juste un historique.
        super().save(*args, **kwargs)

# --- 5. SORTIE PHARMACIE ---
class SortiePharmacie(models.Model):
    paiement = models.ForeignKey('Paiement', on_delete=models.CASCADE, related_name='les_sorties')
    lot = models.ForeignKey('LotPharmacie', on_delete=models.PROTECT, related_name='sorties')
    quantite_vendue = models.PositiveIntegerField()
    date_sortie = models.DateTimeField(auto_now_add=True)
    vendu_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    def save(self, *args, **kwargs):
        # Utilisation de transaction pour éviter les erreurs de concurrence
        with transaction.atomic():
            # On récupère le lot à jour avec verrouillage (select_for_update)
            lot_verrouille = LotPharmacie.objects.select_for_update().get(pk=self.lot.pk)
            
            # Vérification de sécurité
            if lot_verrouille.quantite_actuelle < self.quantite_vendue:
                raise ValueError(f"Stock insuffisant pour le lot {self.lot.numero_lot}.")

            # Décrémentation unique
            lot_verrouille.quantite_actuelle -= self.quantite_vendue
            lot_verrouille.save(update_fields=['quantite_actuelle'])

            # Sauvegarde de la sortie
            super().save(*args, **kwargs)

            # Création du mouvement d'historique
            MouvementStock.objects.create(
                lot=self.lot, 
                type_mouvement='SORTIE', 
                quantite_unites=-self.quantite_vendue, 
                effectue_par=self.vendu_par
            )


# ******************************************************************************************************************** 
# 
# FIN DE LA PARTIE PHARMACIE 
#
# *********************************************************************************************************************


class BlocOperatoire(models.Model):
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('EN_COURS', 'En cours'),
        ('TERMINE', 'Terminé'),
        ('ANNULE', 'Annulé'),
    ]

    # Relation avec la consultation pour garder l'historique médical
    consultation = models.OneToOneField('Consultation', on_delete=models.CASCADE, related_name='bloc_op')
    
    # Informations pré-opératoires
    constantes_pre_op = models.TextField(verbose_name="Constantes pré-opératoires")
    date_programmee = models.DateTimeField(default=timezone.now)
    
    # Informations opératoires (remplies après l'acte)
    acte_realise = models.TextField(blank=True, null=True, verbose_name="Compte-rendu opératoire")
    chirurgien = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='chirurgies_realisees')
    
    # Suivi
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    date_fin = models.DateTimeField(null=True, blank=True)

    prestation = models.ForeignKey(
        'Prestation', 
        on_delete=models.SET_NULL, 
        null=True, 
        limit_choices_to={'categorie': 'CHIR'},
        verbose_name="Type d'intervention"
    )

    def __str__(self):
        return f"Bloc: {self.consultation.triage.patient.noms} - {self.statut}"

# ===============================================================================
# ACCOUCHEMENT 


class CompteRenduAccouchement(models.Model):
    consultation = models.OneToOneField(Consultation, on_delete=models.CASCADE, related_name='cr_accouchement')
    
    # Liaison avec la prestation (Forfait Maternité)
    prestation = models.ForeignKey(
        Prestation, 
        on_delete=models.SET_NULL, 
        null=True, 
        limit_choices_to={'categorie': 'MAT'},
        verbose_name="Forfait / Prestation Maternité"
    )
    
    type_accouchement = models.CharField(
        max_length=20, 
        choices=[('NATUREL', 'Accouchement Simple (Voie basse)'), ('CESARIENNE', 'Accouchement par Césarienne')]
    )
    details_acte = models.TextField(verbose_name="Détails de l'intervention / Rapport")
    date_creation = models.DateTimeField(auto_now_add=True)
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"CR Accouchement - {self.consultation.triage.patient.noms}"
# ===================================================================================================

class FicheAccouchement(models.Model):
    consultation = models.ForeignKey(
        'Consultation',
        on_delete=models.CASCADE,
        related_name='fiches_accouchement'
    )
    prestation = models.ForeignKey(
        'Prestation',
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'categorie': 'MAT'},
        verbose_name="Forfait Maternité"
    )
    type_accouchement = models.CharField(
        max_length=20,
        choices=[('NATUREL', 'Accouchement Naturel'), ('CESARIENNE', 'Césarienne')],
        verbose_name="Type d'accouchement"
    )
    sexe_bebe = models.CharField(
        max_length=1,
        choices=[('M', 'Masculin'), ('F', 'Féminin')],
        verbose_name="Sexe du bébé"
    )
    poids_bebe = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Poids du bébé (kg)"
    )
    score_apgar = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Score Apgar"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notes / Complications"
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Auteur de la fiche"
    )

    def __str__(self):
        return f"Fiche Accouchement - {self.consultation.triage.patient.noms}"


# ====================================================================
class ClientExterne(models.Model):
    # Juste le nécessaire pour identifier la personne de passage
    noms = models.CharField(max_length=150, verbose_name="Nom complet")
    TYPESEXE = [
        ('M', 'Masculin') , 
        ('F' , 'Feminin')
    ]
    sexe = models.CharField(max_length = 20 , choices = TYPESEXE , blank=True, null=True)
    poids = models.CharField(max_length = 15 , blank=True, null=True)
    age = models.CharField(max_length = 15 , blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    date_enregistrement = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.noms} (Externe)"

class DemandeExamenExterne(models.Model):
    STATUT_CHOICES = [('EN_ATTENTE', 'En attente'), ('PAYE', 'Payé'), ('TERMINE', 'Terminé')]
    
    # On lie à la personne de passage, pas au Patient du système
    client = models.ForeignKey(ClientExterne, on_delete=models.CASCADE, related_name='demandes')
    prestations = models.ManyToManyField('Prestation', verbose_name="Examens choisis")
    
    total_a_payer = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    statut = models.CharField(max_length=15, choices=STATUT_CHOICES, default='EN_ATTENTE')
    date_demande = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Demande pour {self.client.noms} - {self.statut}"



class ExamenExterneResultat(models.Model):
    # Lien vers la demande globale (le contenant principal)
    demande = models.ForeignKey(
        'DemandeExamenExterne', 
        on_delete=models.CASCADE, 
        related_name='resultats_examens'
    )
    # L'examen spécifique (ex: Hémogramme, Échographie abdominale)
    prestation = models.ForeignKey('Prestation', on_delete=models.CASCADE)
    
    # Détails du résultat
    statut = models.CharField(
        max_length=20, 
        default='EN_ATTENTE', 
        choices=[('EN_ATTENTE', 'En attente'), ('TERMINE', 'Terminé')]
    )
    rapport = models.TextField(verbose_name="Résultat / Rapport d'examen")
    date_resultat = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Résultat: {self.prestation.libelle} - {self.demande.client.noms}"

    class Meta:
        verbose_name = "Résultat d'examen externe"
        verbose_name_plural = "Résultats des examens externes"





class OrdonnanceExterne(models.Model):
    """Ordonnance destinée à un client externe"""
    # Liaison avec le client externe au lieu du patient interne
    client = models.ForeignKey(ClientExterne, on_delete=models.CASCADE, related_name='ordonnances_externes')
    medecin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    note_globale = models.TextField(blank=True, null=True, help_text="Instructions générales")
    
    class Meta:
        verbose_name = "Ordonnance Client Externe"
        ordering = ['-date_creation']

    def __str__(self):
        return f"Ordonnance #{self.id} - {self.client.noms}"

class OrdonnanceItem(models.Model):
    """Détails des médicaments ou examens"""
    ordonnance = models.ForeignKey(OrdonnanceExterne, on_delete=models.CASCADE, related_name='items')
    designation = models.CharField(max_length=255, verbose_name="Médicament ou Examen")
    posologie = models.TextField(verbose_name="Posologie / Instructions")
    quantite = models.CharField(max_length=50, blank=True, null=True, verbose_name="Quantité")

    def __str__(self):
        return f"{self.designation} pour {self.ordonnance.client.noms}"


# ========================================================================================
#
class OrdonnanceSortie(models.Model):
    hospitalisation = models.OneToOneField(
        Hospitalisation, 
        on_delete=models.CASCADE, 
        related_name='ordonnance_sortie'
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    
    # Contenu détaillé
    prescriptions = models.TextField(verbose_name="Médicaments prescrits")
    recommandations = models.TextField(verbose_name="Conseils et hygiène de vie")
    date_prochain_rdv = models.DateField(null=True, blank=True, verbose_name="Date de suivi")
    
    # Médecin émetteur (optionnel, selon votre gestion des utilisateurs)
    medecin_nom = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Sortie - {self.hospitalisation.patient.noms}"

    class Meta:
        verbose_name = "Ordonnance de Sortie"
        verbose_name_plural = "Ordonnances de Sortie"



# ==============================================================================
#
#
class CategorieEquipement(models.Model):
    """Ex: Lits, Respirateurs, Moniteurs"""
    nom = models.CharField(max_length=100)

    def __str__(self):
        return self.nom

class Equipement(models.Model):
    ETAT_CHOICES = [
        ('bon', 'En bon état'),
        ('panne', 'En panne'),
        ('maintenance', 'En maintenance'),
        ('reforme', 'À réformer'),
    ]

    nom = models.CharField(max_length=100)
    numero_serie = models.CharField(max_length=100, unique=True)
    categorie = models.ForeignKey(CategorieEquipement, on_delete=models.CASCADE)
    etat = models.CharField(max_length=20, choices=ETAT_CHOICES, default='bon')
    
    # Lien vers votre Service existant (en supposant qu'il soit importé)
    # Remplacez 'votre_app.Service' par le chemin réel de votre modèle
    service = models.ForeignKey('Service', on_delete=models.SET_NULL, null=True, blank=True)
    
    date_acquisition = models.DateField()
    date_derniere_maintenance = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.nom} - {self.numero_serie}"

    class Meta:
        verbose_name = "Équipement"
        verbose_name_plural = "Équipements"

class InterventionMaintenance(models.Model):
    """Historique des pannes et réparations"""
    equipement = models.ForeignKey(Equipement, on_delete=models.CASCADE, related_name='maintenances')
    description_panne = models.TextField()
    date_panne = models.DateTimeField(auto_now_add=True)
    date_reparation = models.DateTimeField(null=True, blank=True)
    repare = models.BooleanField(default=False)
    technicien = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Maintenance sur {self.equipement.nom} - {'Réparé' if self.repare else 'En cours'}"
    


# ================================================================================
#
# archivage des informations 
class PatientArchive(models.Model):
    """
    Modèle gérant l'historique d'archivage des dossiers patients en format PDF.
    Chaque fois qu'un utilisateur archive un dossier, une nouvelle instance
    est enregistrée ici avec le document PDF associé.
    """
    # Liaison avec le patient existant (Clé étrangère)
    patient = models.ForeignKey(
        'Patient', # Utilisez la chaîne 'Patient' ou le modèle importé
        on_delete=models.CASCADE, 
        related_name='archives',
        verbose_name="Patient concerné"
    )
    
    # Date et heure de la création de l'archive (automatique)
    archived_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Date d'archivage"
    )
    
    # Le fichier PDF sauvegardé physiquement sur le serveur
    # Les fichiers seront rangés dans un dossier 'patient_archives' au sein de votre dossier MEDIA_ROOT
    pdf_file = models.FileField(
        upload_to='patient_archives/', 
        verbose_name="Fichier PDF de l'archive"
    )
    
    # L'utilisateur (médecin, secrétaire...) ayant déclenché l'archivage
    archived_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Archivé par"
    )

    class Meta:
        verbose_name = "Archive de Patient"
        verbose_name_plural = "Archives de Patients"
        ordering = ['-archived_at'] # Affiche les archives de la plus récente à la plus ancienne

    def __str__(self):
        return f"Archive de {self.patient.noms} - {self.archived_at.strftime('%d/%m/%Y %H:%M')}"


# ==========================================
# 1. LES SHIFTS (QUARTS DE TRAVAIL)
# ==========================================
class Shift(models.Model):
    libelle = models.CharField(max_length=100, verbose_name="Nom du shift") # ex: Matin, Après-midi, Garde Nuit
    heure_debut = models.TimeField(verbose_name="Heure de début attendue")
    heure_fin = models.TimeField(verbose_name="Heure de fin attendue")
    marge_retard = models.IntegerField(default=15, verbose_name="Marge de retard (en minutes)")

    def __str__(self):
        return f"{self.libelle} ({self.heure_debut.strftime('%H:%M')} - {self.heure_fin.strftime('%H:%M')})"


# ==========================================
# 2. LE PLANNING (HORAIRE ATTENDU)
# ==========================================
class Planning(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="plannings", verbose_name="Agent")
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, verbose_name="Shift")
    date = models.DateField(verbose_name="Date planifiée")

    class Meta:
        unique_together = ('user', 'date') # Un agent ne peut avoir qu'un seul shift par jour
        ordering = ['-date', 'user']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.date} ({self.shift.libelle})"


# ==========================================
# 3. LE POINTAGE / PRÉSENCE (RÉEL)
# ==========================================
class Presence(models.Model):
    STATUT_CHOICES = [
        ('PRESENT', 'Présent (À l\'heure)'),
        ('RETARD', 'En Retard'),
        ('ABSENT', 'Absent'),
    ]

    planning = models.OneToOneField(Planning, on_delete=models.CASCADE, related_name="presence", verbose_name="Planning associé")
    heure_arrivee = models.TimeField(null=True, blank=True, verbose_name="Heure d'arrivée réelle")
    heure_depart = models.TimeField(null=True, blank=True, verbose_name="Heure de départ réelle")
    statut = models.CharField(max_length=15, choices=STATUT_CHOICES, default='ABSENT')
    note = models.TextField(blank=True, null=True, verbose_name="Commentaires/Justifications")

    def __str__(self):
        return f"Présence de {self.planning.user.username} le {self.planning.date} - {self.get_statut_display()}"

    def calculer_statut(self):
        """
        Calcule automatiquement si l'agent est à l'heure ou en retard 
        par rapport à l'heure de début de son shift et la marge autorisée.
        """
        if not self.heure_arrivee:
            self.statut = 'ABSENT'
            return

        # On compare l'heure réelle d'arrivée avec l'heure théorique du shift
        heure_theorique = self.planning.shift.heure_debut
        marge = self.planning.shift.marge_retard

        # Conversion en minutes pour simplifier le calcul
        minutes_theorique = heure_theorique.hour * 60 + heure_theorique.minute
        minutes_reelle = self.heure_arrivee.hour * 60 + self.heure_arrivee.minute

        limite_retard = minutes_theorique + marge

        if minutes_reelle > limite_retard:
            self.statut = 'RETARD'
        else:
            self.statut = 'PRESENT'