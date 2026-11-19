# ÉTAPE 13K.1C — Assisted Review Pilot Validation

## Résultat

Le pilote est **préparé mais non validé**. Les trois patches ont été choisis à partir de `metadata/review_priority.csv` et leurs fichiers de revue ont été lus et analysés. Aucune correction géométrique ni validation humaine n'a été réalisée. Le lancement de QGIS a été interrompu par la touche Échap physique; conformément à l'arrêt de l'outil d'interface, aucune autre action QGIS n'a été tentée.

| Rôle du patch | Patch | Préannotations | État actuel |
|---|---|---:|---|
| Dense | `GT_2024_residential_02` | 36 | `NOT_REVIEWED` / `NOT_ANNOTATED` |
| Moyen | `GT_2024_dense_02` | 15 | `NOT_REVIEWED` / `NOT_ANNOTATED` |
| Difficile / sans candidat | `GT_2024_difficult_01` | 0 | `NOT_REVIEWED` / `NOT_ANNOTATED` |

Les trois fichiers GeoJSON de revue sont présents et syntaxiquement lisibles. Leurs métadonnées indiquent `NOT_REVIEWED`; aucune propriété de bâtiment n'indique `REVIEWED` ou `VALIDATED`. Le total des propositions initiales sur les trois patches est de **51**.

Le rapport de validation existant du dataset indique 16 patches `NOT_ANNOTATED`, zéro `VALIDATED`, zéro masque et aucune erreur de validation antérieure. Aucun masque n'existe pour les trois patches du pilote. Par conséquent, dimensions/valeurs binaires des masques et alignement raster-vecteur du résultat final restent **non testés**. Aucun overlay QA final ne peut être produit avant la validation des annotations.

Les métriques de suppressions de faux positifs, corrections, bâtiments ajoutés et nombre final ne sont pas mesurées: elles nécessitent l'examen visuel et l'édition par un annotateur. Le journal `metadata/review_time_log.csv` est encore vide pour les durées et l'identité du réviseur; aucun temps ni gain de vitesse n'est estimé.

## Contrôles de sécurité du workflow

- Les propositions restent dans `review/` et ne sont pas promues dans `annotations/`.
- Le script `scripts/promote_validated_model_c_reviews.py` exige un état de revue explicitement validé, un réviseur et un état de revue sur chaque feature avant promotion.
- `scripts/building_annotation_workflow.py` ne crée le masque que pour un patch explicitement `VALIDATED`; il vérifie la taille, le CRS, la transformée raster et les valeurs binaires.
- Aucun statut, masque, GeoJSON d'annotation vérité terrain ou proposition du modèle n'a été modifié pour simuler une revue humaine.

## Rapport final

PATCHES REVIEWED :
0 / 3 (QGIS non ouvert jusqu'à la revue; les 3 patches sont sélectionnés)

PATCHES VALIDATED :
0 / 3

TOTAL PREANNOTATIONS :
51 (36 + 15 + 0)

DELETED FALSE POSITIVES :
NOT MEASURED

CORRECTED POLYGONS :
NOT MEASURED

ADDED MISSED BUILDINGS :
NOT MEASURED

FINAL BUILDINGS :
NOT MEASURED

MASKS GENERATED :
0 / 3

MASK ALIGNMENT :
NOT RUN (aucun masque validé)

AVERAGE REVIEW TIME :
NOT MEASURED

ESTIMATED SPEEDUP VS MANUAL FROM SCRATCH :
NOT_MEASURED

WORKFLOW USABLE :
NO (pilote humain de bout en bout non validé)

READY_TO_REVIEW_ALL_16_PATCHES :
NO

NEXT STEP :
FIX WORKFLOW (reprendre la revue QGIS du pilote de 3 patches, puis générer et contrôler les masques)
