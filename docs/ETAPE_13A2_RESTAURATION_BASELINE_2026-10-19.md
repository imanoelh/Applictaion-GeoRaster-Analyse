# Étape 13A.2 — restauration de la baseline — 19 octobre 2026

## Résumé

Restauration conservative de l'environnement exécutable et des artefacts disponibles. Aucun adapter, fichier de logique métier, test, configuration GEE, index, export historique ni modèle MODEL_C n'a été modifié. Aucun téléchargement ni réauthentification n'a été effectué. La suite backend complète a été exécutée avec succès après avoir redirigé ses dossiers temporaires dans le workspace (le dossier temporaire par défaut Windows était inaccessible au sandbox).

## Environnements et versions

La copie `Georaster-03-10` existe; aucune copie/dossier `Georaster-18-10` n'a été trouvé à côté des versions GeoRaster locales. Le `backend/requirements.txt` de cette ancienne copie est identique à celui de `Georaster-19-10`. L'environnement virtuel Python déjà installé dans le backend 03-10 est réutilisé pour exécuter les sources actuelles. Il correspond aux versions fixes déclarées (torch/torchvision etc.) et aux plages NumPy/Rasterio/Shapely du manifeste. La tentative d'installation dans le nouvel environnement a été bloquée par l'accès réseau du poste. Les tests n'ont donc pas utilisé le Python global.

| Paquet/runtime | Version vérifiée |
|---|---:|
| Python | 3.12.10 |
| FastAPI | 0.115.6 |
| NumPy | 2.5.4 |
| Rasterio | 1.5.2 |
| GDAL (embarqué par Rasterio) | 3.12.2 |
| Affine | 3.0.1 |
| PyTorch | 2.8.0+cpu |
| Torchvision | 0.23.0+cpu |
| segmentation_models_pytorch | 0.5.0 |
| Shapely | 2.2.0 |
| earthengine-api | 1.7.47 |
| pytest | 7.4.0 |

Les `frontend/package-lock.json` des copies 03-10 et 19-10 ont le même SHA-256 (`404177A5FB7CC06E6346EDB72725121C4465BCC226BDB0BC9CAA14899F948B5B`). Le cache npm hors ligne ne contenait pas tous les paquets (`zod` manquant); les dépendances déjà installées dans 03-10 ont donc été réutilisées via une jonction `frontend/node_modules`. Les scripts actuels sont lancés depuis le frontend 19-10. Aucune mise à niveau ni modification du lockfile.

`backend/.venv` a été créé dans 19-10, mais l'installation de dépendances via pip a échoué car l'accès au registre est interdit. Les tests se sont exécutés depuis l'environnement virtuel complet de 03-10 ci-dessus. Le nouveau `.venv` n'est donc pas l'environnement ayant exécuté les tests.

## Checkpoints retrouvés

### MODEL_A

Trouvé dans `Georaster-03-10/backend/data/models/building/kastela-dof5/unet_best.pt`, taille **97 919 546 octets** et SHA-256 **6CD2467E063696E9D41D409BDA7751A9CCDB057D5ADBA251AB5A765D8D415987**. Le fichier validé a été copié à l'emplacement attendu de 19-10, puis son hash a été revérifié. Les tests réels MODEL_A du backend ont chargé le modèle en CPU et exécuté l'inférence sur une orthophoto synthétique locale de 700×640 (2 tuiles), avec le pipeline jusqu'aux résultats vectoriels/statistiques. Aucun autre modèle n'a remplacé MODEL_A.

### MODEL_C

`best_deeplab.pth` absent des arbres GeoRaster extraits disponibles, y compris les copies 03-10 et 19-10. Les archives ZIP GeoRaster consultables ne contiennent pas ce checkpoint; le listing local de l'archive Georaster-03-10.rar expose le checkpoint MODEL_A, pas MODEL_C. Aucune copie exacte/validable de MODEL_C n'a été trouvée. Aucun téléchargement. Taille/hash/structure restent non vérifiés; strict load et smoke test volontairement non lancés. L'adapter reste expérimental et n'est pas promu.

## Contrôles effectués

- Imports réussis : FastAPI, NumPy, Rasterio/GDAL, Affine, PyTorch CPU, Torchvision, SMP, Shapely, `ee` et principaux modules AI Building.
- GEE : `earthengine-api` importable, variables de projet/compte présentes dans l'environnement, mais contrôle `gee_status` indique **auth-required**. Credentials non modifiés; aucune authentification interactive lancée.
- Backend : `216 passed, 0 failed` (suite complète actuelle). Un premier passage a rencontré des erreurs d'accès au temp Windows; la relance avec `--basetemp` sous `backend/.pytest-runtime` a réussi.
- Frontend : tests complets réussis — contrôle bilingue, AOI GeoJSON/KML/KMZ/Shapefile, AI Building.
- Client build : réussi avec Vite 7.3.3.
- Le même `npm run build` a aussi compilé avec succès l'environnement SSR et émis `dist/server`. Aucun script autonome `build:ssr` n'est défini.
- Small raster avec MODEL_A : validé dans les tests d'intégration réels (700×640, 2 tuiles).
- Large raster : les tests memmap/disk-backed, seuillage par fenêtres et fusion équivalente mémoire/disque passent dans la suite; ils utilisent des prédictions de test déterministes, pas MODEL_A sur un raster géant. Baseline large end-to-end avec MODEL_A non lancée.
- Statistics : tests exacts total/moyenne/médiane/min/max, aires et résultats réels du pipeline passent.
- Preview orthophoto : smoke HTTP direct réussi, réponse 200 `image/png` avec signature PNG.
- GeoJSON, CSV, métadonnées JSON et ZIP : tests de service/API réussis.
- Affine : dans le code applicatif contrôlé, polygonisation utilise `inverse_transform * (x, y)` et aucune occurrence `Affine @ (x, y)` incompatible trouvée. Avec Affine 3.0.1, l'opérateur `*` émet un avertissement de dépréciation, mais les tests passent. Le changement vers `@` n'a pas été effectué.

## Limites et reprise

L'exécution GEE distante n'est pas disponible tant que le compte n'est pas authentifié; cette mission interdit de réauthentifier automatiquement. Le test grand raster avec le modèle de production complet n'a pas été lancé. MODEL_C est absent : l'étape 13B.2.8 ne peut pas être validée. Aucun fine-tuning ni Building Change Detection n'a été lancé/développé.

ÉTAPE 13A.2 — NEW WORKSPACE RESTORATION

PYTHON ENVIRONMENT :
VALIDATED — environnement virtuel isolé réutilisé depuis Georaster-03-10; pip réseau bloqué pour backend/.venv local

PYTHON VERSION :
3.12.10

TORCH :
2.8.0+cpu

TORCHVISION :
0.23.0+cpu

RASTERIO :
1.5.2 (GDAL 3.12.2)

AFFINE :
3.0.1

EARTHENGINE_API :
1.7.47

GEE ENVIRONMENT :
AUTH_REQUIRED

MODEL_A :
AVAILABLE

MODEL_A SIZE :
97919546 bytes

MODEL_A SHA256 :
6CD2467E063696E9D41D409BDA7751A9CCDB057D5ADBA251AB5A765D8D415987

MODEL_A SMOKE TEST :
VALIDATED

MODEL_C :
MISSING

MODEL_C SIZE :
N/A

MODEL_C SHA256 :
N/A

MODEL_C CHECKPOINT STRUCTURE :
NOT RUN

MODEL_C STATUS :
EXPERIMENTAL ONLY

BACKEND TESTS :
216 PASSED / 0 FAILED

FRONTEND DEPENDENCIES :
RESTORED — reused from matching lockfile in Georaster-03-10

FRONTEND TESTS :
SUCCESS

CLIENT BUILD :
SUCCESS

SSR BUILD :
SUCCESS — emitted by combined Vite build; no standalone build:ssr script

SMALL RASTER BASELINE :
VALIDATED

LARGE RASTER BASELINE :
NOT RUN — MODEL_A end-to-end; memmap/fusion tests passed with deterministic predictions

STATISTICS :
VALIDATED

ORTHOPHOTO PREVIEW :
VALIDATED

EXPORTS :
VALIDATED

PRODUCTION MODEL :
MODEL_A

BUSINESS LOGIC MODIFIED :
NO

READY_TO_RESUME_13B_2_8 :
NO

NEXT STEP :
FIX BASELINE FIRST
