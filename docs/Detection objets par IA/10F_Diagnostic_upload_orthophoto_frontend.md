# Diagnostic de l’import frontend des orthophotos Maxar

Date : 14 octobre 2026

## Conclusion

Le message « The local GeoTIFF is invalid or unsupported » ne provenait pas du modèle, du tuilage ou de l’inférence. Le COG Maxar original 2025 est un produit multispectral valide, mais il n’est pas une entrée compatible avec le contrat actuel de `LocalRasterSource` : 8 bandes `uint16` et 1 323 007 113 octets. La limite d’upload est 536 870 912 octets et le profil local exige exactement 3 bandes RGB `uint8`.

Les dérivés RGB 2024 et 2025 (3 bandes `uint8`, `ColorInterp=red/green/blue`, EPSG:32637, 0,35 m/pixel) passent l’API exactement comme l’appelle le frontend, sans mapping explicite supplémentaire. La cause fonctionnelle est donc le choix du COG original (ou d’un autre fichier non conforme), aggravée par le frontend qui masquait le détail JSON renvoyé par le backend derrière un message générique.

## Reproduction

| Fichier | Résultat API `POST /api/ai/raster/local` | Cause |
|---|---|---|
| `25JUL28115945-S3DS-200009702745_01_P001_COG.tif` | Rejet attendu HTTP 422 | 8 bandes `uint16`, 1 323 007 113 octets, au-delà de 512 MiB |
| `maxar_2024_rgb_p2p98.tif` | HTTP 200 | 3 bandes RGB `uint8`, mapping déduit de ColorInterp |
| `maxar_2025_rgb_p2p98.tif` | HTTP 200 | 3 bandes RGB `uint8`, mapping déduit de ColorInterp |

L’interface ne permet pas d’inspecter après coup le chemin exact choisi dans le sélecteur Windows. Le fichier sélectionné lors de l’incident ne peut donc pas être prouvé depuis les logs navigateur. La reproduction est toutefois déterministe avec le COG original 2025 documenté ci-dessus ; le dérivé RGB 2025 réussit avec le même endpoint et le même `Content-Type: image/tiff`.

## Correction frontend

`uploadLocalBuildingRaster` décode désormais `detail.code` et `detail.message` des réponses JSON FastAPI. `buildingErrorMessage` transforme notamment le rejet de taille en indication explicite : limite 512 MiB et nécessité d’un dérivé RGB `uint8`, et transforme le rejet multispectral en indication « exactly 3 RGB uint8 bands ». Aucun composant du pipeline IA ni aucune limite backend n’a été modifié.

Après un rejet, aucun `raster_id` n’est créé et le bouton Run reste inactif. Après un upload RGB accepté, le `raster_id` est renvoyé et le bouton Run devient actif.

## Vérifications

- `LocalRasterSource` + `ImageValidator` : validés sur les deux dérivés RGB.
- Mapping automatique : `ColorInterp` donne `[1,2,3]`.
- Frontend tests : OK.
- Build client : SUCCESS.
- Build SSR : SUCCESS.
- Backend : `209 passed, 0 failed` (avec un répertoire temporaire local au projet ; un premier lancement hors de ce répertoire a rencontré une permission Windows sur `%TEMP%`).
- Aucun entraînement, fine-tuning, changement de modèle, changement de seuil ou modification des analyses historiques.

## Limites

Le COG Maxar original n’est pas importable directement par le contrat actuel. Il faut fournir un dérivé RGB `uint8` géoréférencé, ou définir ultérieurement un profil Maxar multispectral versionné avec conversion radiométrique et traitement par blocs. Le test de clics dans le navigateur n’a pas pu être certifié dans cette session ; les deux uploads ont été exercés par le même endpoint HTTP utilisé par le frontend.

IMPORT ORTHOPHOTO — STATUT :
PARTIELLEMENT VALIDÉE

ROOT CAUSE :
COG Maxar original sélectionné/non conforme au contrat local (8 bandes uint16 et taille supérieure à 512 MiB), détail d’erreur masqué par le frontend.

SELECTED FILE :
ORIGINAL MAXAR (reproduction déterministe ; chemin exact du fichier choisi dans le navigateur non observable)

BACKEND UPLOAD :
VALIDÉ

LOCALRASTERSOURCE :
VALIDÉ

2024 RGB P2P98 UPLOAD :
VALIDÉ

2025 RGB P2P98 UPLOAD :
VALIDÉ

FRONTEND UPLOAD :
VALIDÉ

RUN BUTTON AFTER UPLOAD :
ACTIF pour un dérivé RGB accepté / INACTIF après rejet de l’original

BACKEND REGRESSION :
AUCUNE

FRONTEND BUILD :
SUCCESS
