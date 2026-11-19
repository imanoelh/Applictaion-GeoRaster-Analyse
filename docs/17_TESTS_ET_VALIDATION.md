# Tests et validation

## Suite présente

| Fichier | Couverture |
| --- | --- |
| `test_backend_flow.py` | settings/CRS, création, run mock, cache, JSON export, history, suppression |
| `test_gee_contract.py` | configs, seuils NDBI, capteurs, structures mock, palettes |
| `test_request_contracts.py` | contrat canonique/legacy et Change Detection |
| `test_map_pdf_adaptive_layout.py` | layout PDF et mosaïque de tuiles |
| `test_simulation_3d_crs.py` | isolement EPSG:9332 |
| `test_unsupervised_cluster_customization.py` | noms/couleurs, ordre, palette, CRS stats |
| `_option2_live_check.py` | script manuel NDBI lié à un ID local |
| `check-result-legend-i18n.mjs` | 13 analyses et traductions des légendes |

## Validation exécutée le 27 juillet 2026

### Backend

```powershell
C:\Users\Imane_C4E\anaconda3\python.exe -m pytest -q backend\tests
```

Résultat courant après correction NDBI `v14` : **40 passed** en 19,99 s.

Avertissements :

- `@app.on_event("startup")` déprécié ;
- même avertissement propagé par FastAPI.

La `.venv` racine et le Python système ne contenaient pas pytest ; l’environnement Anaconda l’a fourni. C’est une divergence par rapport aux anciens guides.

### Légendes

```powershell
npm.cmd --prefix frontend run test:legend-i18n
```

Résultat : **13 analyses, 130 termes anglais/arabe**, succès.

### Build

```powershell
npm.cmd --prefix frontend run build
```

Résultat : build client et SSR réussi avec Vite 7.3.3.

Avertissements :

- plusieurs chunks > 500 kB ;
- `MAPTILER_KEY` écrasée par la configuration de build externe ; variable absente du code du dépôt.

### Documentation

Contrôles statiques exécutés après consolidation :

- 26 fichiers Markdown officiels parcourus, aucun lien local cassé ;
- 40 décorateurs de routes FastAPI, tous présents dans `06_BACKEND_API.md` après normalisation des noms de paramètres ;
- 33 références de chemins analysées : 32 existent, `docs/archive/` est uniquement une destination future proposée ;
- `git diff --check` réussi, avec seulement les avertissements de conversion LF/CRLF propres au worktree Windows.

### Validation NDBI réelle

AOI de contrôle en Arabie saoudite, environ 79,5 ha :

- calcul GEE complet sans cache : 44,7 s ;
- restitution du même résultat depuis le cache : 0,184 s ;
- 174 images Sentinel‑2, couverture 100 % ;
- avant correction : 95,4 % de pixels avec évidence Built-up, surestimation causée par WorldCover ;
- après correction `v12` : 40,1 % sans évidence et 60,3 % avec évidence potentielle/détectée ;
- 8 tests NDBI ciblés réussis, dont deux garde-fous empêchant WorldCover de créer du bâti sur un sol nu.

Validation `v14` sur l’AOI de comparaison visuelle fournie, environ 47 ha :

- 174 images Sentinel‑2 et couverture GEE 100 % ;
- calcul forcé sans cache : 36,5 s ; restitution depuis le cache : 0,10 s ;
- avant GHSL : 20,72 ha sans évidence, 0,65 ha potentiel, 10,02 ha détecté, 15,57 ha haute confiance ;
- après GHSL seuil 50 : 17,89 ha sans évidence, 0,65 ha potentiel, 12,85 ha détecté, 15,57 ha haute confiance ;
- la récupération porte donc sur 2,83 ha et ne modifie pas la haute confiance ;
- le seuil 25 et la fermeture morphologique ont été rejetés visuellement car trop permissifs ;
- exports de la sous-couche `ndbi_built_detection` validés : CSV, PNG GEE et GeoTIFF GEE.

Contrôle de non-régression `v14` sur la seconde AOI saoudienne d’environ 79 ha :

- calcul forcé : 42,5 s, 174 images et couverture 100 % ;
- 28,8 % sans évidence et 71,6 % avec évidence potentielle/détectée ;
- le résultat reste nettement inférieur aux 95,4 % erronés de la version antérieure à `v12`.

## Ce que ces tests ne prouvent pas

- disponibilité GEE et validité des credentials ;
- calcul réel des 13 analyses ;
- exactitude scientifique ou comparaison terrain ;
- téléchargement et conformité binaire du GeoTIFF ;
- rendu visuel complet des PDF/PNG ;
- navigation e2e dans un navigateur ;
- sécurité, charge et concurrence ;
- services de fonds de carte tiers.

## Matrice minimale avant livraison

1. tests backend ;
2. test des légendes ;
3. build frontend ;
4. `git diff --check` ;
5. santé API et statut GEE ;
6. un run réel par famille de données ;
7. cache froid/chaud et History ;
8. régénération des tuiles ;
9. export CSV, GeoTIFF, PNG et PDF ;
10. contrôle QGIS/GDAL du GeoTIFF ;
11. interface anglais/arabe ;
12. CRS automatique, manuel et AOI multi-zone.

## Critères scientifiques

- vérifier formule et bandes ;
- comparer des périodes saisonnières cohérentes ;
- contrôler nuages et couverture ;
- vérifier les surfaces contre le raster ;
- documenter toute donnée auxiliaire ;
- faire valider les seuils par un expert métier.
