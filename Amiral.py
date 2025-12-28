# -*- coding: utf-8 -*-
"""
V37 — MOTEUR PAR RÈGLES SYNTAXIQUES (PATCH “anti-fragments” + accords + anti-bégaiements + possessifs)
Objectifs :
- Éliminer les sorties du type "Nous." / "Il." / "Par ailleurs il." (phrases coupées)
- Verrouiller la présence d’un GV fini (sinon régénération en amont)
- Corriger des GN de base fautifs (principe/principes ; cycles d'information genre/nombre)
- Réduire les bégaiements de syntagmes du type "du X du X", "de la X de la X", etc.
- Ajouter des déterminants possessifs (mon, ma, mes, etc.) dans les GN
"""

import random
import re

# =============================================================================
# PARAMÈTRES
# =============================================================================

NOMBRE_DE_PHRASES_SOUHAITE = 120
MAX_PROFONDEUR_RECURSIVITE_CN = 4
MAX_PROFONDEUR_RECURSIVITE_SUB = 3
MAX_EXPANSION_DEPTH = 60

# Anti-fragments : nombre de tentatives max pour obtenir une phrase valide
MAX_RETRY_SENTENCE = 30

# Probabilité d'introduire un déterminant possessif (mon/ma/mes)
POSSESSIVE_DET_PROB = 0.22

# =============================================================================
# SECTION 1 — VOCABULAIRE (patché)
# =============================================================================

GN_MS_BASE = [
    "médium", "imaginaire", "support", "sujet", "geste", "protocole",
    "dispositif", "écart", "signal", "format", "vecteur", "schème", "contexte",
    "diagramme", "médioscope", "robot-orchestre", "flux", "champ", "prisme", "opérateur",
    "régime", "artefact", "réseau", "corps", "palimpseste", "sillage", "décentrement",
    "horizon d'attente", "simulacre", "moment", "temps réel",
    # PATCH: "principes" -> "principe" (évite "le principes")
    "principe",
    "interstice", "paradigme", "substrat", "référentiel", "effet-mémoire", "système",
    "seuil", "rapport au monde", "mythe", "appareil conceptuel", "temps-image",
    "devenir-machine", "impératif", "cycle", "espace",
    "signifié", "processus", "mode d'existence", "espace discursif", "chiffre de l'oubli",
    "terrain", "concept", "référentiel ontologique", "modèle", "flux de données", "territoire affectif",
    "langage machinique", "horizon phénoménologique", "cadre d'interprétation", "préalable",
    "objet-frontière", "code source", "protocole d'échange", "fétichisme du médium", "mécanisme de visée",
    "temps hétérogène", "imaginaire", "potentiel ontologique", "geste d'inscription", "récepteur", "savoir-faire", "temps sériel"
]

GN_FS_BASE = [
    "sphère", "trace", "médiatisation", "technologie", "médiologie", "médiation",
    "transmission", "instance", "opération", "structure", "circulation", "interface", "occurrence", "archive",
    "sémiose", "texture", "matrice", "surface", "stabilisation", "condition",
    "boucle de rétroaction", "strate", "situation", "neurosphère", "réversibilité", "rupture",
    "dimension", "réflexivité", "échelle", "vérité du sujet", "condition de possibilité",
    "infrastructure", "logique interne", "puissance d'agir", "forme-mémoire", "tension",
    "sémantique de l'objet", "historicité", "grammaire du visible", "phénoménologie de l'écran", "temporalité",
    "dérive", "chimère", "hégémonie de l'image", "cartographie", "posture",
    "contingence", "dématérialisation", "évidence", "réappropriation", "force-travail",
    "esthétique", "agence", "problématique", "dynamique", "fiction théorique",
    "modalité d'accès", "pratique curatoriale", "économie de l'attention", "zone de friction", "poétique de l'archive",
    "surface d'inscription", "mémoire", "fiction", "catégorie", "critique",
    "structure d'accueil", "potentialité", "connaissance", "puissance de déconstruction",
    "condition liminale", "matrice d'interférence", "pratique de l'écart",
    "politique du code", "visée", "structure de pouvoir", "rhétorique du flux", "relation de tension", "dynamique d'obsolescence"
]

GN_MP_BASE = [
    "rituels", "systèmes d'encodage", "appareils", "matériaux et outils", "régimes de visibilité", "protocoles",
    "dispositifs", "réseaux de neurones", "affects", "objets", "figures de l'altérité", "modes de présence",
    "gestes de déconstruction", "processus d'indexation", "mécanismes de contrôle",
    "énoncés", "supports d'enregistrement", "modes d'intermédiation", "acteurs", "codes binaires",
    "espaces de projection", "indices", "concepts", "régimes d'historicité", "corps",
    "paradoxes", "schèmes perceptifs", "outils d'analyse", "moments", "vecteurs",
    # PATCH: "cycles d'information" = masculin pluriel (cycle -> m) ; ici on le met côté MP
    "cycles d'information",
]

GN_FP_BASE = [
    "narrations", "données", "archéologies", "dynamiques", "temporalités",
    "frontières", "conditions de production",
    # PATCH: retiré d'ici: "cycles d'information"
    "écritures", "séries",
    "instances", "traces", "postures", "logiques", "puissances",
    "matrices", "conditions d'apparition", "ruptures", "stratégies", "conditions de réception",
]

GN_BASE_MAP = {}
def map_gn_bases(gn_list, g, n):
    for gn in gn_list:
        GN_BASE_MAP[gn] = {'g': g, 'n': n}

map_gn_bases(GN_MS_BASE, 'm', 's')
map_gn_bases(GN_FS_BASE, 'f', 's')
map_gn_bases(GN_MP_BASE, 'm', 'p')
map_gn_bases(GN_FP_BASE, 'f', 'p')

GNDefini = list(GN_BASE_MAP.keys())
GNIndefini_Singulier = [gn for gn, info in GN_BASE_MAP.items() if info['n'] == 's']
GNIndefini_Pluriel = [gn for gn, info in GN_BASE_MAP.items() if info['n'] == 'p']
GNIndefini = GNIndefini_Singulier + GNIndefini_Pluriel
GNComplexe = GNDefini

GNPersonnel = [{"v": "nous", "n": "p", "g": "m"}, {"v": "on", "n": "s", "g": "m"}]
GNImpersonnel = [{"v": "il", "n": "s", "g": "m"}]

# =============================================================================
# VERBES
# =============================================================================

GVTransitif = {
    "réorganiser": {"s": "réorganise", "p": "réorganisent"}, "interroger": {"s": "interroge", "p": "interrogent"},
    "activer": {"s": "active", "p": "activent"}, "configurer": {"s": "configure", "p": "configurent"},
    "articuler": {"s": "articule", "p": "articulent"}, "conditionner": {"s": "conditionne", "p": "conditionnent"},
    "inscrire": {"s": "inscrit", "p": "inscrivent"}, "déplacer": {"s": "déplace", "p": "déplacent"},
    "générer": {"s": "génère", "p": "génèrent"}, "produire": {"s": "produit", "p": "produisent"},
    "moduler": {"s": "module", "p": "modulent"}, "stabiliser": {"s": "stabilise", "p": "stabilisent"},
    "indexer": {"s": "indexe", "p": "indexent"}, "transférer": {"s": "transfère", "p": "transfèrent"},
    "reformuler": {"s": "reformule", "p": "reformulent"},
    "encadrer": {"s": "encadre", "p": "encadrent"},
    "intégrer": {"s": "intègre", "p": "intègrent"}, "traduire": {"s": "traduit", "p": "traduisent"},
    "lier": {"s": "lie", "p": "lient"}, "distribuer": {"s": "distribue", "p": "distribuent"},
    "manifester": {"s": "manifeste", "p": "manifestent"}, "saisir": {"s": "saisit", "p": "saisissent"},
    "gérer": {"s": "gère", "p": "gèrent"}, "fonder": {"s": "fonde", "p": "fondent"},
    "actualiser": {"s": "actualise", "p": "actualisent"}, "déconstruire": {"s": "déconstruit", "p": "déconstruisent"},
    "circonscrire": {"s": "circonscrit", "p": "circonscrivent"}, "opacifier": {"s": "opacifie", "p": "opacifient"},
    "contingenter": {"s": "contingente", "p": "contingentent"},
    "médiatiser": {"s": "médiatise", "p": "médiatisent"}, "historiciser": {"s": "historicise", "p": "historicisent"},
    "cartographier": {"s": "cartographie", "p": "cartographient"}, "dévoiler": {"s": "dévoile", "p": "dévoilent"},
    "interpeller": {"s": "interpelle", "p": "interpellent"}, "formaliser": {"s": "formalise", "p": "formalisent"},
    "essentialiser": {"s": "essentialise", "p": "essentialisent"}, "paradoxaliser": {"s": "paradoxalise", "p": "paradoxalisent"},
    "subjectiviser": {"s": "subjectivise", "p": "subjectivisent"},
    "reconfigurer": {"s": "reconfigure", "p": "reconfigurent"},
    "subvertir": {"s": "subvertit", "p": "subvertissent"}, "encrypter": {"s": "encrypte", "p": "encryptent"},
    "potentialiser": {"s": "potentialise", "p": "potentialisent"}, "problématiser": {"s": "problématise", "p": "problématisent"},
    "réifier": {"s": "réifie", "p": "réifient"}, "dénaturaliser": {"s": "dénaturalise", "p": "dénaturalisent"},
    "soutenir": {"s": "soutient", "p": "soutiennent"},
    "affirmer": {"s": "affirme", "p": "affirment"}, "montrer": {"s": "montre", "p": "montrent"},
    "postuler": {"s": "postule", "p": "postulent"}, "suggérer": {"s": "suggère", "p": "suggèrent"},
    "démontrer": {"s": "démontre", "p": "démontrent"},
}

GVAttributif = {
    "être": {"s": "est", "p": "sont"}, "sembler": {"s": "semble", "p": "semblent"},
    "apparaître": {"s": "apparaît", "p": "apparaissent"}, "demeurer": {"s": "demeure", "p": "demeurent"},
    "rester": {"s": "reste", "p": "restent"}, "devenir": {"s": "devient", "p": "deviennent"},
}

GVIntransitif = {
    "émerger": {"s": "émerge", "p": "émergent"}, "persister": {"s": "persiste", "p": "persistent"},
    "circuler": {"s": "circule", "p": "circulent"}, "résider": {"s": "réside", "p": "résident"},
    "advenir": {"s": "advient", "p": "adviennent"}, "se déployer": {"s": "se déploie", "p": "se déploient"},
    "subsister": {"s": "subsiste", "p": "subsistent"}, "opérer": {"s": "opère", "p": "opèrent"},
}

GVIntroductif = GVTransitif

GVModalPersonal = {"devoir": {"s": "doit", "p": "doivent"}, "pouvoir": {"s": "peut", "p": "peuvent"}}
GVModalImpersonal = {"falloir": {"s": "faut", "p": "faut"}}

GVReflexifAttributif = {
    "se constituer": {"s": "se constitue", "p": "se constituent"},
    "se définir": {"s": "se définit", "p": "se définissent"},
    "se manifester": {"s": "se manifeste", "p": "se manifestent"},
    "se reconfigurer": {"s": "se reconfigure", "p": "se reconfigurent"},
    "s'inscrire": {"s": "s'inscrit", "p": "s'inscrivent"},
    "s'avérer": {"s": "s'avère", "p": "s'avèrent"},
    "se déployer": GVIntransitif["se déployer"],
}

VERBES_PASSIFS = {
    "conditionner": "conditionné", "intégrer": "intégré", "structurer": "structuré", "archiver": "archivé", "analyser": "analysé",
    "transférer": "transféré", "distribuer": "distribué", "moduler": "modulé", "gérer": "géré",
    "produire": "produit", "lier": "lié", "médiatiser": "médiatisé", "historiciser": "historicisé",
    "cartographier": "cartographié", "dévoiler": "dévoilé", "formaliser": "formalisé",
    "problématiser": "problématisé", "réifier": "réifié",
    "circonscrire": "circonscrit",
    "déconstruire": "déconstruit",
    "subvertir": "subverti",
}
GVPassif = {k: v for k, v in VERBES_PASSIFS.items()}

GVInfinitifTransitif = list(GVTransitif.keys())
GVInfinitifIntransitif = list(GVIntransitif.keys())
GVInfinitif = GVInfinitifTransitif + GVInfinitifIntransitif

GV_PERSONNEL_NOUS_EXPLICIT = {
    "réorganiser": "réorganisons", "interroger": "interrogeons", "activer": "activons", "configurer": "configurons",
    "articuler": "articulons", "conditionner": "conditionnons", "inscrire": "inscrivons", "déplacer": "déplaçons",
    "générer": "générons", "produire": "produisons", "moduler": "modulons", "stabiliser": "stabilisons",
    "indexer": "indexons", "transférer": "transférons", "reformuler": "reformulons", "encadrer": "encadrons",
    "intégrer": "intégrons", "traduire": "traduisons", "lier": "lions", "distribuer": "distribuons",
    "manifester": "manifestons", "saisir": "saisissons", "gérer": "gérons", "fonder": "fondons",
    "actualiser": "actualisons", "déconstruire": "déconstruisons", "circonscrire": "circonscrivons",
    "opacifier": "opacifions", "contingenter": "contingentons", "médiatiser": "médiatisons",
    "historiciser": "historicisons", "cartographier": "cartographions", "dévoiler": "dévoilons",
    "interpeller": "interpellons", "formaliser": "formalisons", "essentialiser": "essentialisons",
    "paradoxaliser": "paradoxalisons", "subjectiviser": "subjectivisons", "reconfigurer": "reconfigurons",
    "subvertir": "subvertissons", "encrypter": "encryptons", "potentialiser": "potentialisons",
    "problématiser": "problématisons", "réifier": "réifions", "dénaturaliser": "dénaturalisons",
    "soutenir": "soutenons", "affirmer": "affirmons", "montrer": "montrons", "postuler": "postulons",
    "suggérer": "suggérons", "démontrer": "démontrons",
    "devoir": "devons", "pouvoir": "pouvons",
    "être": "sommes", "sembler": "semblons", "apparaître": "apparaissons", "demeurer": "demeurons",
    "rester": "restons", "devenir": "devenons",
    "émerger": "émergeons", "persister": "persistons", "circuler": "circulons", "résider": "résidons",
    "advenir": "advenons", "subsister": "subsistons", "opérer": "opérons",
}

# =============================================================================
# ADJECTIFS (identique + participes auto)
# =============================================================================

ADJ_MORPHOLOGY = {
    "ambivalent": {"m": {"s": "ambivalent", "p": "ambivalents"}, "f": {"s": "ambivalente", "p": "ambivalentes"}},
    "latent": {"m": {"s": "latent", "p": "latents"}, "f": {"s": "latente", "p": "latentes"}},
    "contingent": {"m": {"s": "contingent", "p": "contingents"}, "f": {"s": "contingente", "p": "contingentes"}},
    "convergent": {"m": {"s": "convergent", "p": "convergents"}, "f": {"s": "convergente", "p": "convergentes"}},
    "signifiant": {"m": {"s": "signifiant", "p": "signifiants"}, "f": {"s": "signifiante", "p": "signifiantes"}},
    "critique": {"m": {"s": "critique", "p": "critiques"}, "f": {"s": "critique", "p": "critiques"}},
    "dialectique": {"m": {"s": "dialectique", "p": "dialectiques"}, "f": {"s": "dialectique", "p": "dialectiques"}},
    "heuristique": {"m": {"s": "heuristique", "p": "heuristiques"}, "f": {"s": "heuristique", "p": "heuristiques"}},
    "technique": {"m": {"s": "technique", "p": "techniques"}, "f": {"s": "technique", "p": "techniques"}},
    "paradoxal": {"m": {"s": "paradoxal", "p": "paradoxaux"}, "f": {"s": "paradoxale", "p": "paradoxales"}},
    "transcendantal": {"m": {"s": "transcendantal", "p": "transcendantaux"}, "f": {"s": "transcendantale", "p": "transcendantales"}},
    "structurel": {"m": {"s": "structurel", "p": "structurels"}, "f": {"s": "structurelle", "p": "structurelles"}},
    "idéel": {"m": {"s": "idéel", "p": "idéels"}, "f": {"s": "idéelle", "p": "idéelles"}},
    "fragmenté": {"m": {"s": "fragmenté", "p": "fragmentés"}, "f": {"s": "fragmentée", "p": "fragmentées"}},
    "complet": {"m": {"s": "complet", "p": "complets"}, "f": {"s": "complète", "p": "complètes"}},
    "décentré": {"m": {"s": "décentré", "p": "décentrés"}, "f": {"s": "décentrée", "p": "décentrées"}},
    "sous-jacent": {"m": {"s": "sous-jacent", "p": "sous-jacents"}, "f": {"s": "sous-jacente", "p": "sous-jacentes"}},
    "opératoire": {"m": {"s": "opératoire", "p": "opératoires"}, "f": {"s": "opératoire", "p": "opératoires"}},
    "instable": {"m": {"s": "instable", "p": "instables"}, "f": {"s": "instable", "p": "instables"}},
    "matriciel": {"m": {"s": "matriciel", "p": "matriciels"}, "f": {"s": "matricielle", "p": "matricielles"}},
    "invisible": {"m": {"s": "invisible", "p": "invisibles"}, "f": {"s": "invisible", "p": "invisibles"}},
    "omniprésent": {"m": {"s": "omniprésent", "p": "omniprésents"}, "f": {"s": "omniprésente", "p": "omniprésentes"}},
    "réversible": {"m": {"s": "réversible", "p": "réversibles"}, "f": {"s": "réversible", "p": "réversibles"}},
    "virtuel": {"m": {"s": "virtuel", "p": "virtuels"}, "f": {"s": "virtuelle", "p": "virtuelles"}},
    "essentiel": {"m": {"s": "essentiel", "p": "essentiels"}, "f": {"s": "essentielle", "p": "essentielles"}},
    "systémique": {"m": {"s": "systémique", "p": "systémiques"}, "f": {"s": "systémique", "p": "systémiques"}},
    "performant": {"m": {"s": "performant", "p": "performants"}, "f": {"s": "performante", "p": "performantes"}},
    "sémantique": {"m": {"s": "sémantique", "p": "sémantiques"}, "f": {"s": "sémantique", "p": "sémantiques"}},
    "herméneutique": {"m": {"s": "herméneutique", "p": "herméneutiques"}, "f": {"s": "herméneutique", "p": "herméneutiques"}},
    "ontologique": {"m": {"s": "ontologique", "p": "ontologiques"}, "f": {"s": "ontologique", "p": "ontologiques"}},
    "paradigmatique": {"m": {"s": "paradigmatique", "p": "paradigmatiques"}, "f": {"s": "paradigmatique", "p": "paradigmatiques"}},
    "opératif": {"m": {"s": "opératif", "p": "opératifs"}, "f": {"s": "opérative", "p": "opératives"}},
    "rhizomatique": {"m": {"s": "rhizomatique", "p": "rhizomatiques"}, "f": {"s": "rhizomatique", "p": "rhizomatiques"}},
    "dénaturalisé": {"m": {"s": "dénaturalisé", "p": "dénaturalisés"}, "f": {"s": "dénaturalisée", "p": "dénaturalisées"}},
    "chiffré": {"m": {"s": "chiffré", "p": "chiffrés"}, "f": {"s": "chiffrée", "p": "chiffrées"}},
    "spectral": {"m": {"s": "spectral", "p": "spectraux"}, "f": {"s": "spectrale", "p": "spectrales"}},
    "archivistique": {"m": {"s": "archivistique", "p": "archivistiques"}, "f": {"s": "archivistique", "p": "archivistiques"}},
    "curatorial": {"m": {"s": "curatorial", "p": "curatoriaux"}, "f": {"s": "curatoriale", "p": "curatoriales"}},
    "intermédié": {"m": {"s": "intermédié", "p": "intermédiés"}, "f": {"s": "intermédiée", "p": "intermédiées"}},
    "bio-politique": {"m": {"s": "bio-politique", "p": "bio-politiques"}, "f": {"s": "bio-politique", "p": "bio-politiques"}},
    "subjectif": {"m": {"s": "subjectif", "p": "subjectifs"}, "f": {"s": "subjective", "p": "subjectives"}},
    "fragmentaire": {"m": {"s": "fragmentaire", "p": "fragmentaires"}, "f": {"s": "fragmentaire", "p": "fragmentaires"}},
    "historique": {"m": {"s": "historique", "p": "historiques"}, "f": {"s": "historique", "p": "historiques"}},
    "spéculatif": {"m": {"s": "spéculatif", "p": "spéculatifs"}, "f": {"s": "spéculative", "p": "spéculatives"}},
    "réifié": {"m": {"s": "réifié", "p": "réifiés"}, "f": {"s": "réifiée", "p": "réifiées"}},
    "liminal": {"m": {"s": "liminal", "p": "liminaux"}, "f": {"s": "liminale", "p": "liminales"}},
    "haptique": {"m": {"s": "haptique", "p": "haptiques"}, "f": {"s": "haptique", "p": "haptiques"}},
    "produit": {"m": {"s": "produit", "p": "produits"}, "f": {"s": "produite", "p": "produites"}},
    "circonscrit": {"m": {"s": "circonscrit", "p": "circonscrits"}, "f": {"s": "circonscrite", "p": "circonscrites"}},
    "déconstruit": {"m": {"s": "déconstruit", "p": "déconstruits"}, "f": {"s": "déconstruite", "p": "déconstruites"}},
    "subverti": {"m": {"s": "subverti", "p": "subvertis"}, "f": {"s": "subvertie", "p": "subverties"}},
    "lié": {"m": {"s": "lié", "p": "liés"}, "f": {"s": "liée", "p": "liées"}},
}

for base, pp in VERBES_PASSIFS.items():
    if pp not in ADJ_MORPHOLOGY:
        ADJ_MORPHOLOGY[pp] = {
            "m": {"s": pp, "p": pp + ("s" if not pp.endswith("s") else "")},
            "f": {"s": pp + "e", "p": pp + "es"},
        }

ADJECTIFS_DISPONIBLES = list(ADJ_MORPHOLOGY.keys())
ADJ_MS, ADJ_FS, ADJ_MP, ADJ_FP = [], [], [], []
for base, forms in ADJ_MORPHOLOGY.items():
    ADJ_MS.append(forms["m"]["s"])
    ADJ_FS.append(forms["f"]["s"])
    ADJ_MP.append(forms["m"]["p"])
    ADJ_FP.append(forms["f"]["p"])

AdvConnecteur = ["De plus", "Par ailleurs", "En outre", "Dès lors", "Toutefois", "Néanmoins",
                 "De surcroît", "Nonobstant", "Ainsi", "Également"]
Coordination = ["Or", "De fait", "Aussi", "Cependant", "Inversement", "De ce fait"]
AdvArgumentatif = ["En définitive", "Fondamentalement", "En ce sens", "De manière intrinsèque",
                   "Subsidiairement", "Globalement", "Épistémologiquement parlant"]
AdjDetache = ["Concrètement", "Historiquement", "Logiquement", "Philosophiquement",
              "Conceptuellement", "Sémiotiquement", "Typiquement"]
Gerondif = ["En analysant le flux", "En interrogeant l'archive", "En configurant le dispositif",
            "En déconstruisant le support", "En historicisant l'instance", "En formalisant le protocole"]

# =============================================================================
# OUTILS GRAMMATICAUX
# =============================================================================

VOWELS = ('a','e','i','o','u','h','y','é','è','à','ô','ê','ï','ù','û','ü','œ')

def _starts_with_vowel(s: str) -> bool:
    s = (s or "").strip()
    if not s:
        return False
    return s[0].lower() in VOWELS

def _select_pronoun_from_info(g: str, n: str) -> str:
    if n == "p":
        return "ils" if g == "m" else "elles"
    return "il" if g == "m" else "elle"

def accorder_attribut(attribut_base, sujet_g, sujet_n):
    if attribut_base in ADJ_MORPHOLOGY:
        return ADJ_MORPHOLOGY[attribut_base][sujet_g][sujet_n]

    attribut = attribut_base.strip()

    if sujet_g == 'f' and not attribut.endswith(('e', 'x', 's', 't')):
        attribut += 'e'

    if sujet_n == 'p' and not attribut.endswith(('s', 'x', 'aux')):
        if attribut.endswith('al'):
            attribut = attribut[:-2] + 'aux'
        else:
            attribut += 's'

    return attribut.strip()

def conjuguer_verbe(verbe_dict, sujet_n, sujet_g="m", verbe_cle=None, voix='active', sujet_v=None):
    if verbe_cle is None:
        verbe_cle = random.choice(list(verbe_dict.keys()))

    if sujet_v:
        sv = sujet_v.lower().strip()

        if sv == "nous":
            base_inf = verbe_cle
            if base_inf.startswith("se ") or base_inf.startswith("s'"):
                base_inf = re.sub(r"^s'|^se\s", "", base_inf)
            if base_inf in GV_PERSONNEL_NOUS_EXPLICIT:
                return GV_PERSONNEL_NOUS_EXPLICIT[base_inf]
            if base_inf.endswith("er"):
                return base_inf[:-2] + "ons"
            if base_inf.endswith("ir"):
                return base_inf[:-2] + "issons"
            if base_inf.endswith("re"):
                return base_inf[:-2] + "ons"
            return base_inf

        if sv == "on":
            sujet_n = "s"

        if sv == "il" and verbe_cle == "falloir":
            sujet_n = "s"

    if verbe_cle == 'falloir':
        return verbe_dict[verbe_cle]['s']

    if voix == 'passive' and verbe_cle in VERBES_PASSIFS:
        pp = VERBES_PASSIFS[verbe_cle]
        pp_acc = accorder_attribut(pp, sujet_g, sujet_n)
        etre = GVAttributif["être"][sujet_n]
        return f"{etre} {pp_acc}"

    if verbe_cle in verbe_dict and sujet_n in verbe_dict[verbe_cle]:
        return verbe_dict[verbe_cle][sujet_n]

    if verbe_cle in GVTransitif and sujet_n in GVTransitif[verbe_cle]:
        return GVTransitif[verbe_cle][sujet_n]
    if verbe_cle in GVIntransitif and sujet_n in GVIntransitif[verbe_cle]:
        return GVIntransitif[verbe_cle][sujet_n]

    return ""

def eliminer_article_devant_voyelle(text):
    text = re.sub(r'\b(le|la)\s+([aeiouyéèàôêïh])', r"l'\2", text, flags=re.IGNORECASE)
    text = re.sub(r'\bde\s+([aeiouyéèàôêïh])', r"d'\1", text, flags=re.IGNORECASE)
    text = re.sub(r'\bque\s+([aeiouyéèàôêïh])', r"qu'\1", text, flags=re.IGNORECASE)
    text = re.sub(r'\bse\s+([aeiouyéèàôêïh])', r"s'\1", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()

def _get_base_gn_info(gn_base_str):
    return GN_BASE_MAP.get(gn_base_str, {'g': 'm', 'n': 's'})

def select_determinant(g, n, type='defini'):
    if type == 'defini':
        if n == 's': return 'le ' if g == 'm' else 'la '
        return 'les '
    if type == 'indefini':
        if n == 's': return 'un ' if g == 'm' else 'une '
        return 'des '
    return ''

def _apply_determinant_and_elision(gn_bare, g, n, type):
    det = select_determinant(g, n, type)
    first = gn_bare.split()[0] if gn_bare else ""
    if det in ('le ', 'la ') and first and _starts_with_vowel(first):
        det = "l'"
    return (det + gn_bare).strip()

def get_random_adjective_form_from_category(g, n):
    if g == 'm' and n == 's': return random.choice(ADJ_MS)
    if g == 'f' and n == 's': return random.choice(ADJ_FS)
    if g == 'm' and n == 'p': return random.choice(ADJ_MP)
    if g == 'f' and n == 'p': return random.choice(ADJ_FP)
    return ""

def formatter_sp_gn_fixed(preposition, gn_info):
    gn_str_bare = gn_info['v_bare']
    gn_g, gn_n = gn_info['g'], gn_info['n']
    starts = _starts_with_vowel(gn_str_bare)

    p_raw = (preposition or "").strip()
    p = p_raw.lower()

    if p == "au moyen de":
        if starts and gn_n == "s":
            return f"au moyen de l'{gn_str_bare}"
        if gn_n == "s" and gn_g == "m":
            return f"au moyen du {gn_str_bare}"
        if gn_n == "s" and gn_g == "f":
            return f"au moyen de la {gn_str_bare}"
        return f"au moyen des {gn_str_bare}"

    if p == "grâce à":
        if starts:
            return f"grâce à l'{gn_str_bare}"
        if gn_n == "s" and gn_g == "m":
            return f"grâce au {gn_str_bare}"
        if gn_n == "s" and gn_g == "f":
            return f"grâce à la {gn_str_bare}"
        return f"grâce aux {gn_str_bare}"

    if p == "de":
        if starts and gn_n == "s":
            return f"de l'{gn_str_bare}"
        if gn_n == "s" and gn_g == "m":
            return f"du {gn_str_bare}"
        if gn_n == "s" and gn_g == "f":
            return f"de la {gn_str_bare}"
        return f"des {gn_str_bare}"

    if p == "à":
        if starts:
            return f"à l'{gn_str_bare}"
        if gn_n == "s" and gn_g == "m":
            return f"au {gn_str_bare}"
        if gn_n == "s" and gn_g == "f":
            return f"à la {gn_str_bare}"
        return f"aux {gn_str_bare}"

    full_gn = _apply_determinant_and_elision(gn_str_bare, gn_g, gn_n, type='defini')
    return eliminer_article_devant_voyelle(f"{p_raw} {full_gn}")

def construire_sp_locatif():
    prepo = random.choice(["dans", "sur", "par", "via"])
    gn_base = random.choice([b for b, i in GN_BASE_MAP.items() if i['n'] == 's'])
    gn_info = get_gn_info(gn_base, n='s', role='complement')
    return formatter_sp_gn_fixed(prepo, gn_info)

def construire_sp_moyen():
    prepo = random.choice(["au moyen de", "grâce à", "via", "par"])
    gn_base = random.choice([b for b, i in GN_BASE_MAP.items() if i['n'] == 's'])
    gn_info = get_gn_info(gn_base, n='s', role='complement')
    return formatter_sp_gn_fixed(prepo, gn_info)

def construire_sp():
    choice = random.random()
    if choice < 0.40:
        return construire_sp_locatif()
    if choice < 0.85:
        return construire_sp_moyen()
    gn = get_gn_info(GNIndefini, role="complement")
    return f"comme {gn['v']}"

# =============================================================================
# Génération GN (récursif + relatives + possessifs)
# =============================================================================

LAST_GN_INFO = None

def generer_ps_relative(gn_antecedent_info):
    ant_n = gn_antecedent_info['n']
    ant_g = gn_antecedent_info['g']

    ant_surface = (gn_antecedent_info.get('v_bare') or gn_antecedent_info.get('v') or "").strip().lower()
    ant_is_pron = gn_antecedent_info.get("is_pronoun", False) or ant_surface in {"nous", "on", "il", "elle", "ils", "elles"}
    sujet_v_for_person = ant_surface if ant_is_pron else None

    if random.random() < 0.65:
        verbe = conjuguer_verbe(GVTransitif, ant_n, sujet_g=ant_g, sujet_v=sujet_v_for_person)
        obj = get_gn_info(GNIndefini, role='object')
        return f"qui {verbe} {obj['v']}"

    sujet2 = get_gn_info(GNDefini, n=random.choice(['s','p']), role='subject')
    verbe = conjuguer_verbe(GVTransitif, sujet2['n'], sujet_g=sujet2['g'], sujet_v=(sujet2['v'] if sujet2.get("is_pronoun") else None))
    return f"que {sujet2['v']} {verbe}"

def construire_ps_initiale_clause():
    clause_type = random.choice(['causale', 'temporelle', 'gerondif', 'detache'])
    sujet_nom = get_gn_info(GNDefini, role='subject')
    verbe = conjuguer_verbe(GVTransitif, sujet_nom['n'], sujet_g=sujet_nom["g"], sujet_v=(sujet_nom["v"] if sujet_nom.get("is_pronoun") else None))
    objet = get_gn_info(GNIndefini, role='object')

    if clause_type == 'causale':
        return f"{random.choice(['parce que','puisque','comme'])} {sujet_nom['v']} {verbe} {objet['v']}"
    if clause_type == 'temporelle':
        return f"{random.choice(['lorsque','quand','dès que','alors que'])} {sujet_nom['v']} {verbe} {objet['v']}"
    if clause_type == 'gerondif':
        return random.choice(Gerondif)
    return random.choice(AdjDetache)

def generer_ps_finale_simple():
    if random.random() < 0.7:
        prefixe = random.choice(["afin de", "pour"])
        infinitive = random.choice(GVInfinitifTransitif)
        objet = get_gn_info(GNDefini, role='object')
        if prefixe == "afin de":
            if _starts_with_vowel(infinitive):
                return f"afin d'{infinitive} {objet['v']}".strip()
            return f"afin de {infinitive} {objet['v']}".strip()
        return f"pour {infinitive} {objet['v']}".strip()

    prefixe = random.choice(["pour que", "afin que"])
    sujet_sub = get_gn_info(GNDefini, role='subject')
    verbe = conjuguer_verbe(GVTransitif, sujet_sub['n'], sujet_g=sujet_sub["g"], sujet_v=(sujet_sub["v"] if sujet_sub.get("is_pronoun") else None))
    objet = get_gn_info(GNIndefini, role='object')
    return f"{prefixe} {sujet_sub['v']} {verbe} {objet['v']}"

def construire_ps_finale():
    return generer_ps_finale_simple()

def construire_attribut_correct(sujet_info, _verbe_key=None):
    attribut_type = random.choice(['adj','gn'])
    n_cible, g_cible = sujet_info['n'], sujet_info['g']
    if attribut_type == 'adj':
        base = random.choice(ADJECTIFS_DISPONIBLES)
        return accorder_attribut(base, g_cible, n_cible)
    gn_base = random.choice([gn for gn, info in GN_BASE_MAP.items() if info['n'] == n_cible])
    gn_attr = get_gn_info(gn_base, type='indefini', n=n_cible)['v']
    return gn_attr

def construire_opposition(sujet_info):
    adj_base = random.choice(ADJECTIFS_DISPONIBLES)
    adj_acc = accorder_attribut(adj_base, sujet_info['g'], sujet_info['n'])
    sujet_v = sujet_info["v"] if sujet_info.get("is_pronoun") else None
    verbe_etre = conjuguer_verbe(GVAttributif, sujet_info['n'], verbe_cle='être', sujet_v=sujet_v)
    neg = "n'" if verbe_etre and _starts_with_vowel(verbe_etre) else "ne "
    return f"mais {neg}{verbe_etre} pas {adj_acc}"

def generer_gn_recursif_fixed(base_gn_str, type, profondeur=0, allow_recursion=True):
    gn_info_base = _get_base_gn_info(base_gn_str)
    g, n = gn_info_base['g'], gn_info_base['n']

    adjs_post = []
    if random.random() < 0.40:
        adj = get_random_adjective_form_from_category(g, n)
        if adj:
            adjs_post.append(adj)

    gn_final_bare = f"{base_gn_str} {' '.join(adjs_post)}".strip()

    if allow_recursion and profondeur < MAX_PROFONDEUR_RECURSIVITE_CN:
        if random.random() < 0.30:
            cn_base = random.choice(GNDefini)
            cn_rec = generer_gn_recursif_fixed(cn_base, type='defini', profondeur=profondeur+1)
            cn_final = formatter_sp_gn_fixed("de", cn_rec)
            gn_final_bare = f"{gn_final_bare} {cn_final}".strip()

        if random.random() < 0.22:
            ant = {
                'v': _apply_determinant_and_elision(gn_final_bare, g, n, "defini"),
                'g': g, 'n': n, 'v_bare': gn_final_bare,
                'is_pronoun': False
            }
            relative = generer_ps_relative(ant)
            gn_final_bare = f"{gn_final_bare} {relative}".strip()

    full = gn_final_bare if type == "aucun" else _apply_determinant_and_elision(gn_final_bare, g, n, type)
    return {"v": full.strip(), "g": g, "n": n, "v_bare": gn_final_bare.strip()}

def generer_gn_coordonne(liste_gn_bases, coord='et'):
    n_choice = random.choice(['s', 'p'])
    candidates = [b for b in liste_gn_bases if GN_BASE_MAP.get(b, {}).get('n') == n_choice]
    if len(candidates) < 2:
        candidates = liste_gn_bases[:]

    base1, base2 = random.sample(candidates, 2)
    gn1 = generer_gn_recursif_fixed(base1, type='defini', profondeur=0)
    gn2 = generer_gn_recursif_fixed(base2, type='defini', profondeur=0)

    g = 'm' if ('m' in (gn1.get('g'), gn2.get('g'))) else 'f'
    v = f"{gn1['v']} {coord} {gn2['v']}"
    v_bare = f"{gn1['v_bare']} {coord} {gn2['v_bare']}"
    return {"v": v, "v_bare": v_bare, "g": g, "n": "p", "coord": True}

def _apply_possessive_determiner(gn_info):
    """
    Transforme éventuellement 'le/la/les/un/une/des X' en 'mon/ma/mes X'
    en respectant genre/nombre et élision minimale.
    """
    v = gn_info.get("v", "")
    if not v:
        return gn_info

    # On ne touche pas aux pronoms purs
    if gn_info.get("is_pronoun"):
        return gn_info

    # Cherche un déterminant au début
    m = re.match(r"^(l'|le|la|les|un|une|des)\s+(.*)$", v, flags=re.IGNORECASE)
    if not m:
        return gn_info

    det_orig = m.group(1)
    reste = m.group(2)
    g = gn_info.get("g", "m")
    n = gn_info.get("n", "s")

    # Choix mon/ma/mes
    # Règle : si singulier masculin OU singulier féminin devant voyelle -> "mon"
    #         si singulier féminin devant consonne       -> "ma"
    #         si pluriel                                 -> "mes"
    first_bare = ""
    if gn_info.get("v_bare"):
        first_bare = gn_info["v_bare"].split()[0]
    else:
        first_bare = reste.split()[0] if reste else ""

    if n == "s":
        if g == "m" or _starts_with_vowel(first_bare):
            det_new = "mon"
        else:
            det_new = "ma"
    else:
        det_new = "mes"

    gn_info["v"] = f"{det_new} {reste}".strip()
    return gn_info

def maybe_apply_possessive(gn_info, role, ctx=None):
    """
    Applique avec une certaine probabilité un déterminant possessif
    (mon/ma/mes) sur les GN non pronominaux (sujet, objet, complément).
    """
    if role not in ("subject", "object", "complement"):
        return gn_info

    # Pas de possessif si déjà un pronom pur
    if gn_info.get("is_pronoun"):
        return gn_info

    # Tirage aléatoire
    if random.random() >= POSSESSIVE_DET_PROB:
        return gn_info

    return _apply_possessive_determiner(gn_info)

def get_gn_info(gn_list_or_key=None, type='defini', n=None, g=None, role='subject', ctx=None):
    global LAST_GN_INFO

    if role == 'subject' and ctx and ctx.get('person_policy') is None and LAST_GN_INFO and not LAST_GN_INFO.get('is_pronoun') and random.random() < 0.13:
        pron = _select_pronoun_from_info(LAST_GN_INFO['g'], LAST_GN_INFO['n'])
        result = {"v": pron, "g": LAST_GN_INFO['g'], "n": LAST_GN_INFO['n'], "v_bare": pron, "is_pronoun": True}
        LAST_GN_INFO = result
        return result

    if role == 'subject' and ctx and ctx.get('person_policy') == "nous":
        result = {"v": "nous", "g": "m", "n": "p", "v_bare": "nous", "is_pronoun": True}
        LAST_GN_INFO = result
        return result

    if role == 'subject' and ctx and ctx.get('person_policy') == "impersonal":
        result = {"v": "il", "g": "m", "n": "s", "v_bare": "il", "is_pronoun": True}
        LAST_GN_INFO = result
        return result

    if gn_list_or_key == 'GNPersonnel':
        if ctx and ctx.get('person_policy') == "nous":
            chosen = {"v": "nous", "n": "p", "g": "m"}
        else:
            chosen = random.choice(GNPersonnel)
        result = {"v": chosen["v"], "g": chosen["g"], "n": chosen["n"], "v_bare": chosen["v"], "is_pronoun": True}

    elif gn_list_or_key == 'GNImpersonnel':
        chosen = random.choice(GNImpersonnel)
        result = {"v": chosen["v"], "g": chosen["g"], "n": chosen["n"], "v_bare": chosen["v"], "is_pronoun": True}

    elif gn_list_or_key == 'Coordination':
        result = generer_gn_coordonne(GNDefini)

    else:
        if isinstance(gn_list_or_key, list):
            base = random.choice(gn_list_or_key)
            type = 'defini' if gn_list_or_key in [GNDefini, GNComplexe] else 'indefini'
        else:
            base = gn_list_or_key if gn_list_or_key in GNDefini else random.choice(GNDefini)

        info = _get_base_gn_info(base)
        if n is None: n = info['n']
        if g is None: g = info['g']
        result = generer_gn_recursif_fixed(base, type=type, profondeur=0)

    # Injection éventuelle de mon/ma/mes
    result = maybe_apply_possessive(result, role, ctx)

    if role == 'subject' and not result.get('is_pronoun', False) and type == 'defini':
        LAST_GN_INFO = result
    else:
        LAST_GN_INFO = None

    return result

# =============================================================================
# GRAMMAIRE
# =============================================================================

GRAMMAR = {
    "PHRASE": [
        ["PREFIXE", "PROPOSITION", "SUFFIXE"],
        ["PROPOSITION"],
    ],
    "PREFIXE": [
        [],
        ["PS_INIT"],
        ["ADV_DETACHE"],
    ],
    "SUFFIXE": [
        [],
        ["PS_FINALE"],
        ["OPPOSITION"],
    ],
    "PROPOSITION": [
        ["SUJET", "GV"],
        ["SUJET", "GV", "SUB_EMBED"],
    ],
    "SUB_EMBED": [
        [],
        ["INTRO_SUB", "QUE", "PROPOSITION_SUB"],
    ],
    "PROPOSITION_SUB": [
        ["SUJET_SUB", "GV_SUB"],
        ["SUJET_SUB", "GV_SUB", "SUB_EMBED"],
    ],
    "GV": [
        ["GV_TRANS"],
        ["GV_ATTR"],
        ["GV_INTRANS"],
        ["GV_PASSIF"],
        ["GV_MODAL"],
        ["GV_REFLEXIF"],
    ],
    "GV_SUB": [
        ["GV_TRANS_SUB"],
        ["GV_ATTR_SUB"],
        ["GV_INTRANS_SUB"],
        ["GV_PASSIF_SUB"],
        ["GV_MODAL_SUB"],
        ["GV_REFLEXIF_SUB"],
    ],
    "GV_TRANS": [["VERBE_TRANS", "OBJET", "SP_CHAIN", "REL_OPT"]],
    "GV_ATTR": [["VERBE_ATTR", "ATTRIBUT", "SP_CHAIN"]],
    "GV_INTRANS": [["VERBE_INTRANS", "SP_CHAIN"]],
    "GV_PASSIF": [["VERBE_PASSIF", "AGENT_OPT", "SP_CHAIN"]],
    "GV_MODAL": [["VERBE_MODAL", "INFINITIF_NU", "OBJET_OPT", "SP_CHAIN"]],
    "GV_REFLEXIF": [["VERBE_REFLEXIF", "SP_CHAIN", "PS_FINALE_OPT"]],

    "GV_TRANS_SUB": [["VERBE_TRANS_SUB", "OBJET", "SP_CHAIN", "REL_OPT"]],
    "GV_ATTR_SUB": [["VERBE_ATTR_SUB", "ATTRIBUT_SUB", "SP_CHAIN"]],
    "GV_INTRANS_SUB": [["VERBE_INTRANS_SUB", "SP_CHAIN"]],
    "GV_PASSIF_SUB": [["VERBE_PASSIF_SUB", "AGENT_OPT", "SP_CHAIN"]],
    "GV_MODAL_SUB": [["VERBE_MODAL_SUB", "INFINITIF_NU", "OBJET_OPT", "SP_CHAIN"]],
    "GV_REFLEXIF_SUB": [["VERBE_REFLEXIF_SUB", "SP_CHAIN", "PS_FINALE_OPT"]],

    "OBJET_OPT": [[], ["OBJET"]],
    "SP_CHAIN": [[], ["SP", "SP_CHAIN"]],
    "REL_OPT": [[], ["RELATIVE"]],
    "AGENT_OPT": [[], ["SP_AGENT"]],
    "PS_FINALE_OPT": [[], ["PS_FINALE"]],
    "QUE": [["que"]],
}

# =============================================================================
# Réalisation / Expansion
# =============================================================================

def realize(symbol, ctx):
    if symbol == "PS_INIT":
        return construire_ps_initiale_clause()
    if symbol == "ADV_DETACHE":
        return random.choice(AdjDetache + Gerondif + AdvConnecteur + Coordination)
    if symbol == "PS_FINALE":
        return construire_ps_finale()

    if symbol == "INTRO_SUB":
        s = ctx["sujet"]
        sujet_v = s["v"] if s.get("is_pronoun") else None
        v = conjuguer_verbe(
            GVIntroductif,
            s["n"],
            sujet_g=s["g"],
            verbe_cle=random.choice(["affirmer","montrer","démontrer","suggérer"]),
            sujet_v=sujet_v,
        )
        return "et " + v

    if symbol == "SUJET":
        if ctx.get("person_policy") is None:
            r = random.random()
            if r < 0.10:
                ctx["person_policy"] = "impersonal"
            elif r < 0.22:
                ctx["person_policy"] = "nous"
            else:
                ctx["person_policy"] = None

        pick = random.random()
        if ctx.get("person_policy") == "nous":
            s = get_gn_info(role="subject", ctx=ctx)
        elif ctx.get("person_policy") == "impersonal":
            s = get_gn_info("GNImpersonnel", role="subject", ctx=ctx)
        else:
            if pick < 0.10:
                s = get_gn_info("GNImpersonnel", role="subject", ctx=ctx)
            elif pick < 0.24:
                s = get_gn_info("GNPersonnel", role="subject", ctx=ctx)
            elif pick < 0.38:
                s = get_gn_info("Coordination", role="subject", ctx=ctx)
            else:
                s = get_gn_info(GNDefini, n=random.choice(['s','p']), role="subject", ctx=ctx)

        ctx["sujet"] = s
        return s["v"]

    if symbol == "SUJET_SUB":
        s = get_gn_info(GNDefini, n=random.choice(['s','p']), role='subject', ctx=ctx)
        if ctx.get("person_policy") == "nous" and s["v"] in ("il", "on"):
            s = get_gn_info(GNDefini, n=random.choice(['s','p']), role='subject', ctx=ctx)
        ctx["sujet_sub"] = s
        return s["v"]

    if symbol == "OBJET":
        return (get_gn_info(GNIndefini, role='object', ctx=ctx) if random.random() < 0.7
                else get_gn_info(GNDefini, role='object', ctx=ctx))["v"]

    if symbol == "VERBE_TRANS":
        s = ctx["sujet"]
        return conjuguer_verbe(GVTransitif, s["n"], s["g"], sujet_v=(s["v"] if s.get("is_pronoun") else None))
    if symbol == "VERBE_ATTR":
        s = ctx["sujet"]
        key = random.choice(list(GVAttributif.keys()))
        ctx["verbe_attr"] = key
        return conjuguer_verbe(GVAttributif, s["n"], verbe_cle=key, sujet_v=(s["v"] if s.get("is_pronoun") else None))
    if symbol == "VERBE_INTRANS":
        s = ctx["sujet"]
        return conjuguer_verbe(GVIntransitif, s["n"], sujet_g=s["g"], sujet_v=(s["v"] if s.get("is_pronoun") else None))
    if symbol == "VERBE_PASSIF":
        s = ctx["sujet"]
        key = random.choice(list(VERBES_PASSIFS.keys()))
        return conjuguer_verbe(GVPassif, s["n"], s["g"], verbe_cle=key, voix="passive", sujet_v=(s["v"] if s.get("is_pronoun") else None))
    if symbol == "VERBE_MODAL":
        s = ctx["sujet"]
        key = random.choice(["devoir", "pouvoir"])
        ctx["modal_key"] = key
        return conjuguer_verbe(GVModalPersonal, s["n"], sujet_g=s["g"], verbe_cle=key, sujet_v=(s["v"] if s.get("is_pronoun") else None))
    if symbol == "VERBE_REFLEXIF":
        s = ctx["sujet"]
        key = random.choice(list(GVReflexifAttributif.keys()))
        return conjuguer_verbe(GVReflexifAttributif, s["n"], verbe_cle=key, sujet_v=(s["v"] if s.get("is_pronoun") else None))
    if symbol == "ATTRIBUT":
        return construire_attribut_correct(ctx["sujet"], ctx.get("verbe_attr"))

    if symbol == "VERBE_TRANS_SUB":
        s = ctx["sujet_sub"]
        return conjuguer_verbe(GVTransitif, s["n"], s["g"], sujet_v=(s["v"] if s.get("is_pronoun") else None))
    if symbol == "VERBE_ATTR_SUB":
        s = ctx["sujet_sub"]
        key = random.choice(list(GVAttributif.keys()))
        ctx["verbe_attr_sub"] = key
        return conjuguer_verbe(GVAttributif, s["n"], verbe_cle=key, sujet_v=(s["v"] if s.get("is_pronoun") else None))
    if symbol == "VERBE_INTRANS_SUB":
        s = ctx["sujet_sub"]
        return conjuguer_verbe(GVIntransitif, s["n"], sujet_g=s["g"], sujet_v=(s["v"] if s.get("is_pronoun") else None))
    if symbol == "VERBE_PASSIF_SUB":
        s = ctx["sujet_sub"]
        key = random.choice(list(VERBES_PASSIFS.keys()))
        return conjuguer_verbe(GVPassif, s["n"], s["g"], verbe_cle=key, voix="passive", sujet_v=(s["v"] if s.get("is_pronoun") else None))
    if symbol == "VERBE_MODAL_SUB":
        s = ctx["sujet_sub"]
        key = random.choice(["devoir", "pouvoir"])
        return conjuguer_verbe(GVModalPersonal, s["n"], sujet_g=s["g"], verbe_cle=key, sujet_v=(s["v"] if s.get("is_pronoun") else None))
    if symbol == "VERBE_REFLEXIF_SUB":
        s = ctx["sujet_sub"]
        key = random.choice(list(GVReflexifAttributif.keys()))
        return conjuguer_verbe(GVReflexifAttributif, s["n"], verbe_cle=key, sujet_v=(s["v"] if s.get("is_pronoun") else None))
    if symbol == "ATTRIBUT_SUB":
        return construire_attribut_correct(ctx["sujet_sub"], ctx.get("verbe_attr_sub"))

    if symbol == "SP_AGENT":
        agent = get_gn_info(GNIndefini, role='complement', ctx=ctx)
        return formatter_sp_gn_fixed("par", agent)
    if symbol == "INFINITIF_NU":
        return random.choice(GVInfinitifTransitif)
    if symbol == "SP":
        return construire_sp()
    if symbol == "RELATIVE":
        return generer_ps_relative(ctx["sujet"])
    if symbol == "OPPOSITION":
        return construire_opposition(ctx["sujet"])
    if symbol in ("QUE", "que"):
        return "que"

    return ""

def expand(symbol, ctx, depth=0, sub_depth=0):
    if depth > MAX_EXPANSION_DEPTH:
        return ""

    if symbol not in GRAMMAR:
        return realize(symbol, ctx)

    if symbol in ("SUB_EMBED", "PROPOSITION_SUB") and sub_depth >= MAX_PROFONDEUR_RECURSIVITE_SUB:
        return ""

    rule = random.choice(GRAMMAR[symbol])
    if not rule:
        return ""

    parts = []
    for sym in rule:
        next_sub_depth = sub_depth
        if sym in ("SUB_EMBED", "PROPOSITION_SUB"):
            next_sub_depth = sub_depth + 1
        chunk = expand(sym, ctx, depth=depth+1, sub_depth=next_sub_depth)
        if chunk:
            parts.append(chunk)

    return " ".join(parts).strip()

# =============================================================================
# Post-traitement (ponctuation + nettoyages + anti-bégaiements)
# =============================================================================

_WORD = r"[a-zàâçéèêëîïôûùüÿœ\-]+"
_PHRASE_N = rf"{_WORD}(?:\s+{_WORD}){{0,4}}"

def _collapse_repeated_prep_phrases(txt: str) -> str:
    """
    Réduit :
      "du médioscope du médioscope" -> "du médioscope"
      "de la condition liminale de la condition liminale" -> "de la condition liminale"
      "de l'archive de l'archive" -> "de l'archive"
    """
    patterns = [
        rf"\b(du)\s+({_PHRASE_N})\s+\1\s+\2\b",
        rf"\b(des)\s+({_PHRASE_N})\s+\1\s+\2\b",
        rf"\b(de la)\s+({_PHRASE_N})\s+\1\s+\2\b",
        rf"\b(de l')\s*({_PHRASE_N})\s+\1\s*\2\b",
        rf"\b(au)\s+({_PHRASE_N})\s+\1\s+\2\b",
        rf"\b(aux)\s+({_PHRASE_N})\s+\1\s+\2\b",
        rf"\b(à la)\s+({_PHRASE_N})\s+\1\s+\2\b",
        rf"\b(à l')\s*({_PHRASE_N})\s+\1\s*\2\b",
        rf"\b(d')\s*({_PHRASE_N})\s+\1\s*\2\b",
    ]
    prev = None
    cur = txt
    for _ in range(3):  # itérations pour enchaînements
        prev = cur
        for pat in patterns:
            cur = re.sub(pat, r"\1 \2", cur, flags=re.IGNORECASE)
        cur = re.sub(r"\s+", " ", cur).strip()
        if cur == prev:
            break
    return cur

def post_process_phrase(phrase):
    phrase = re.sub(r'\s+', ' ', phrase).strip()
    phrase = re.sub(r'\s([,.:;?!])', r'\1', phrase)

    phrase = eliminer_article_devant_voyelle(phrase)

    phrase = re.sub(r"\b([dlmnstcquj]')\s+", r"\1", phrase, flags=re.IGNORECASE)
    phrase = re.sub(r"\bde\s+le\b", "du", phrase, flags=re.IGNORECASE)
    phrase = re.sub(r"\bde\s+les\b", "des", phrase, flags=re.IGNORECASE)
    phrase = re.sub(r"\bà\s+le\b", "au", phrase, flags=re.IGNORECASE)
    phrase = re.sub(r"\bà\s+les\b", "aux", phrase, flags=re.IGNORECASE)

    phrase = re.sub(r'\b(et)\s+(affirme|suggère|montre|démontre)\s*,\s*que\b', r'\1 \2 que', phrase, flags=re.IGNORECASE)

    phrase = re.sub(r'\b(doit|peut|devons|pouvons|doivent|peuvent)\s+\1\b', r'\1', phrase, flags=re.IGNORECASE)
    phrase = re.sub(r'\b(\w+)\s+\1\b', r'\1', phrase, flags=re.IGNORECASE)

    # PATCH: anti-bégaiements structurés (du X du X, etc.)
    phrase = _collapse_repeated_prep_phrases(phrase)

    phrase = phrase.strip().rstrip(',')
    if phrase and not phrase.endswith(('.', '?', '!', ':')):
        phrase += '.'

    if phrase and phrase[0].isalpha():
        phrase = phrase[0].upper() + phrase[1:]
    return phrase

# =============================================================================
# Validation “anti-coupure” (en amont) : on refuse les fragments
# =============================================================================

def _finite_verb_forms_set():
    forms = set()
    for d in (GVTransitif, GVAttributif, GVIntransitif, GVModalPersonal, GVReflexifAttributif):
        for base, m in d.items():
            if isinstance(m, dict):
                if "s" in m: forms.add(m["s"])
                if "p" in m: forms.add(m["p"])
    # formes "nous" explicites
    for f in GV_PERSONNEL_NOUS_EXPLICIT.values():
        forms.add(f)
    # passif = "est/sont + pp" (on ne liste pas tout, mais "est"/"sont" aide)
    forms.add("est")
    forms.add("sont")
    return forms

FINITE_FORMS = _finite_verb_forms_set()

def _looks_like_fragment(s: str) -> bool:
    s = (s or "").strip()
    if not s:
        return True

    # "Nous." / "Il." / "On."
    if re.fullmatch(r"(?i)(nous|il|on)\.?", s):
        return True

    # Trop court, sans verbe visible
    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿœ']+", s.lower())
    if len(tokens) < 3:
        return True

    # Doit contenir au moins un verbe fini connu (heuristique robuste ici)
    has_finite = any(tok in FINITE_FORMS for tok in tokens)
    if not has_finite:
        return True

    # Empêche des enchaînements du type "Il via ..." (préposition juste après pronom)
    if re.match(r"(?i)^(il|nous|on)\s+(via|par|dans|sur|au)\b", s):
        return True

    return False

# =============================================================================
# Génération
# =============================================================================

def generate_sentence():
    global LAST_GN_INFO
    for _ in range(MAX_RETRY_SENTENCE):
        LAST_GN_INFO = None
        ctx = {"person_policy": None}
        raw = expand("PHRASE", ctx)
        s = post_process_phrase(raw)

        # PATCH: si fragment -> on régénère (au lieu de “nettoyer”)
        if _looks_like_fragment(s):
            continue

        return s

    # Ultime secours : une phrase minimale toujours grammaticale
    return "Nous formulons une hypothèse."

def generate_prose_block(n=NOMBRE_DE_PHRASES_SOUHAITE):
    out = []
    for _ in range(n):
        s = generate_sentence()
        if s:
            out.append(s)
    return " ".join(out)

if __name__ == "__main__":
    print(generate_prose_block())
