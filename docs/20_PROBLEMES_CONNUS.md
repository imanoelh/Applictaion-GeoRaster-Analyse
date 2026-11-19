# Problèmes connus et améliorations recommandées

## Anomalies techniques confirmées

| Sujet | Constat | Impact | Recommandation |
| --- | --- | --- | --- |
| Résolution | `resolution` est stockée, mais le calcul utilise 10 m S2 / 30 m Landsat | attente UI trompeuse | appliquer/valider l’échelle ou renommer le réglage |
| GeoTIFF | NoData, dtype, compression, bandes et tags non spécifiés | interopérabilité non contractuelle | définir un profil d’export et le tester avec GDAL |
| Fichier `.tif` local | contient l’URL GEE, pas le raster | confusion lors de l’inspection disque | utiliser `.url`/métadonnée ou télécharger réellement |
| CRS KSA/GEE | export demandé KSA, requête GEE en UTM WGS84 | métadonnée différente du souhait national | documenter et éventuellement reprojeter après téléchargement |
| EPSG:9333 | accepté pour analyse/export métrique | risque d’unités en degrés | limiter ou forcer un UTM effectif |
| 3D | option affichée sans moteur | promesse fonctionnelle ambiguë | afficher « expérimental/configuration seulement » |
| Authentification | absente ; header admin par défaut | accès non protégé | ajouter identité, rôles et secrets |
| Clé API settings | persistée mais inutilisée | faux sentiment de sécurité | brancher ou retirer |
| Catalogue | `/catalog` est statique, `/map` a le catalogue GEE | expérience incohérente | unifier les sources |
| Capteurs | Dynamic World/WorldCover sélectionnables mais incompatibles avec les analyses | erreurs/UX | filtrer selon l’analyse |
| Jobs | catalogue en mémoire | perte au redémarrage/multi-worker | queue persistante |
| Runs | calcul synchrone et statut directement succeeded | pas de vraie progression serveur | job de calcul asynchrone |
| Monolithes | fichiers backend/frontend très volumineux | maintenance/risque de régression | découpage progressif |
| Fallback visuel | faux raster en bandes si pas de tuile | peut être pris pour résultat | étiqueter explicitement mock |
| URL GEE | temporaires | History/export peuvent expirer | régénération systématique/stockage |
| FastAPI | `on_event` déprécié | dette de mise à niveau | utiliser lifespan |
| Dépendance certifi | import optionnel non déclaré | comportement TLS variable | déclarer ou supprimer |
| Bundle | chunks > 500 kB | chargement initial | code splitting |
| MAPTILER_KEY | avertissement externe, variable inutilisée | bruit/config écrasée | supprimer de l’environnement ou config externe |
| i18n source | plusieurs chaînes arabes apparaissent mojibake dans les sorties console | risque d’encodage/outillage | imposer UTF‑8 et ajouter contrôle |
| Suppression | détruit fichiers d’export liés | action irréversible | confirmation forte et journal d’audit |

## Limites scientifiques

- seuils fixes non calibrés par biome/saison ;
- NDWI et NDBI sensibles aux surfaces mixtes ;
- classification supervisée peut basculer sur WorldCover sans échantillons utilisateur suffisants ;
- KMeans produit des groupes à interpréter ;
- OSI‑SAR détecte des suspects seulement ;
- Change Detection confond potentiellement saisonnalité et changement réel.

## Éléments non vérifiables ici

- projet/compte GEE et quotas ;
- calculs en ligne ;
- conformité des exports téléchargés ;
- performance sur grandes AOI ;
- rendu réel des services de fonds ;
- pertinence métier des classes et seuils.

## Dette documentaire

Les anciens guides contiennent des chemins absolus, comptes personnels, commits datés, routes absentes, résultats de tests périmés et architectures cibles. Ils sont inventoriés dans [CARTOGRAPHIE_DOCUMENTATION_EXISTANTE.md](CARTOGRAPHIE_DOCUMENTATION_EXISTANTE.md).
