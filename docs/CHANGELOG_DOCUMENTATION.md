# Changelog de la documentation

## 2026-07-27 — Récupération conservatrice des toits clairs NDBI v14

- Ajout de GHSL 2018 comme troisième référence auxiliaire, uniquement pour NDBI Built-up Sentinel‑2.
- Seuil retenu après comparaison visuelle : au moins 50 m² bâtis par cellule de 100 m² ; le seuil 25 et la fermeture morphologique ont été rejetés.
- GHSL intervient en dernier et peut uniquement promouvoir « aucune évidence » vers « bâti détecté », jamais vers « haute confiance ».
- AOI réelle de 47 ha : 2,83 ha récupérés ; classe haute confiance inchangée à 15,57 ha.
- Seconde AOI de 79 ha : 71,6 % d’évidence bâtie, contre 95,4 % dans la version erronée antérieure à `v12`.
- Validation : 40 tests backend, calcul GEE forcé en 36,5 s, cache en 0,10 s, exports CSV/PNG/GeoTIFF réussis.

## 2026-07-27 — Correction NDBI Built-up v12

- WorldCover devient une preuve de confirmation et ne peut plus créer seul une classe bâtie.
- Deux tests anti-faux-positifs ajoutés ; 8 tests NDBI et 37 tests backend réussissent.
- Même AOI GEE validée : 95,4 % d’évidence Built-up avant correction, 60,3 % après correction.
- Performance mesurée : 44,7 s sans cache et 0,184 s avec cache.
- Le backend conserve NDBI Raw ; l’interface présente uniquement Built-up.

## 2026-07-27 — Consolidation finale

### Ajouté

- `DOCUMENTATION_VERSION_FINALE.md` ;
- index officiel `00_INDEX_DOCUMENTATION.md` ;
- 21 chapitres couvrant architecture, dépôt, installation, frontend, API, GEE, analyses, changement, projections, couches, 3D, exports, PDF, flux, erreurs, tests, déploiement, règles, problèmes et roadmap ;
- cartographie de 21 documents historiques ;
- liste des contradictions, anomalies et éléments non vérifiables.

### Vérifié

- 40 routes FastAPI ;
- 13 analyses UI ;
- cinq projections KSA UTM, deux références géographiques KSA et les CRS web/entrée ;
- collections GEE, masques, mosaïques, formules, seuils, palettes et classes ;
- trois sous-couches par Change Detection ;
- flux cache/History ;
- exports et rapports ;
- schéma SQLite et paramètres ;
- consommateurs frontend.

### Validation

- 37 tests backend réussis ;
- contrôle i18n réussi : 13 analyses, 130 termes ;
- build client/SSR réussi ;
- chemins, routes et liens documentaires contrôlés par script local.

### Non modifié

- logique métier ;
- formules/seuils/palettes ;
- routes/contrats ;
- projections ;
- exports/rapports ;
- dépendances et environnement.

### Documents historiques

Aucun document n’a été supprimé ou déplacé. Les recommandations d’archivage sont enregistrées dans `CARTOGRAPHIE_DOCUMENTATION_EXISTANTE.md`.
