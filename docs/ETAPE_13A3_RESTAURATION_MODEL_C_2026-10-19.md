# Étape 13A.3 — restauration MODEL_C — 19 octobre 2026

## Résultat

Recherche locale effectuée avant tout téléchargement dans les copies GeoRaster extraites présentes sous le dossier de travail, les répertoires `backend/data/models/` pertinents, les dossiers expérimentaux, les archives GeoRaster locales consultables et `Downloads`. La seule copie GeoRaster antérieure extraite disponible est `Georaster-03-10`; `Georaster-18-10` n'existe pas à l'emplacement des versions locales. Aucun fichier `best_deeplab.pth` ni metadata JSON correspondant n'a été trouvé. Les archives inspectables n'ont pas fourni ce checkpoint. Il n'existe donc aucun candidat à inventorier en taille/date/hash et aucun fichier n'a été copié.

**LOCAL_MODEL_C_COPY = NOT_FOUND**  
**DOWNLOAD_REQUIRED = YES**

Aucun téléchargement n'a été lancé, conformément à la consigne de ne pas télécharger sans confirmation explicite. Aucun adapter ou code métier n'a été modifié. Aucun strict load, chargement, smoke test ou inférence MODEL_C n'a été effectué. Le registre par défaut continue d'utiliser `BuildingModelAdapter`; `SpaceNet2DeepLabAdapter` reste expérimental et non enregistré comme production. MODEL_A a été recontrôlé après la restauration précédente : taille 97 919 546 et SHA-256 attendu toujours identiques. GEE n'a pas été touché.

ÉTAPE 13A.3 — MODEL_C RESTORATION

LOCAL MODEL_C COPY FOUND :
NO

SOURCE PATH :
NOT FOUND — aucune copie locale dans les dossiers/archives explorés

DESTINATION PATH :
backend/data/models/building/experimental/spacenet2-deeplab/best_deeplab.pth (absent)

MODEL_C SIZE :
N/A — fichier absent

EXPECTED SIZE :
168357171

MODEL_C SHA256 :
N/A — fichier absent

EXPECTED SHA256 :
170C49E1F42737F5A4B3922B9FC58B25B6BA0A7DD7BF00B9186A92CCB84DC555

MODEL_C FILE :
MISSING

MODEL_C STATUS :
EXPERIMENTAL ONLY

MODEL_A :
UNCHANGED — 97919546 bytes; SHA256 6CD2467E063696E9D41D409BDA7751A9CCDB057D5ADBA251AB5A765D8D415987

PRODUCTION MODEL :
MODEL_A

BUSINESS LOGIC MODIFIED :
NO

GEE :
AUTH_REQUIRED / UNCHANGED

READY_TO_RESUME_13B_2_8 :
NO

NEXT STEP :
DOWNLOAD MODEL_C (après confirmation explicite)
