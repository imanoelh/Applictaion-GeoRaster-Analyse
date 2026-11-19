# 14A.9C — QA des corrections assistées TRAIN / DEV

## Décision : FIX_CORRECTION_QA

Les fichiers réellement persistés ne contiennent **aucune correction par rapport aux références IA 14A.9B** : 124 géométries TRAIN et 49 DEV inchangées topologiquement, zéro ajout, suppression ou modification. Les 173 features conservent `source=MODEL_C6_PREANNOTATION`, `review_status=NOT_REVIEWED`, `annotation_status=NOT_VALIDATED`, `correction_action=PENDING`, `error_category=UNCLASSIFIED`, `is_ground_truth=0`. Elles ne peuvent pas être déclarées GT humaines.

La comparaison confirme une absence de correction **dans ces fichiers enregistrés**, pas l'absence de travail dans une session QGIS. Des éditions non enregistrées ou une autre copie restent possibles ; ne pas fermer QGIS ni écraser ces éventuelles éditions. Enregistrer les modifications des couches vertes dans leurs fichiers sources, puis reprendre la QA. En cas de travail dans un autre GeoPackage, identifier ce fichier avant tout remplacement.

## Sources contrôlées

- TRAIN : `14A9B_active_learning/corrected_gt/MANUAL_CORRECTED_GT.gpkg`, dix tables par patch.
- DEV : `14A9B_dev_set/gt/MANUAL_CORRECTED_GT.gpkg`, quatre tables par patch.
- Références immuables de comparaison : `14A9B_active_learning/train_candidates/AI_PREANNOTATION_C6.gpkg` et `14A9B_dev_set/qa/AI_PREANNOTATION_C6.gpkg`.

Les URI de couches des deux projets QGIS livrés ont été extraites dans `qa/14A9C_correction_qa/14A9C_PROJECT_DATASOURCES.json`. Elles pointent vers ces GeoPackages. Aucun GeoPackage alternatif de corrections 14A.9B plus récent n'a été trouvé dans les datasets Building inspectés. Les fichiers sources ont été lus en mode SQLite read-only et sauvegardés par `backup` dans quatre snapshots QA : les éventuels WAL sont ainsi pris en compte, contrairement à une simple copie du fichier principal. Aucun fichier original ni statut n'a été modifié.

## Géométrie et emprises

Les 173 features sont Polygon, EPSG:32637, valides, non nulles, non vides et de surface positive. TRAIN/DEV : invalid=0, self-intersections=0, null=0, empty=0, zero-area=0, duplicates=0, wrong patch=0, OOB=0. Les identifiants patch/building sont présents et uniques par patch ; source et statuts existent mais n'attestent pas une revue humaine.

Le contrôle OOB se fait **sur la grille native RGB**, après transformation inverse des vecteurs vers les coordonnées pixel, dans [0,512]×[0,512], avec une tolérance numérique de 0,000001 pixel. Un premier contrôle utilisant seulement quatre coins transformés en UTM produisait de faux débordements sur les bords : les limites d'un raster géographique ne sont pas exactement les cordes entre ces quatre points UTM. Ce contrôle QA a été corrigé, sans toucher aux géométries. Les RGB restent natifs EPSG:4326 ; les vecteurs sont en EPSG:32637.

| Jeu | Patch | Features persistées | Géométries IA inchangées | Invalid | OOB | Validation humaine |
|---|---|---:|---:|---:|---:|---|
| TRAIN | 14A9B_AL_01_R00256_C02304 | 7 | 7 | 0 | 0 | NO |
| TRAIN | 14A9B_AL_02_R00512_C07680 | 20 | 20 | 0 | 0 | NO |
| TRAIN | 14A9B_AL_03_R04352_C03328 | 19 | 19 | 0 | 0 | NO |
| TRAIN | 14A9B_AL_04_R07936_C07936 | 15 | 15 | 0 | 0 | NO |
| TRAIN | 14A9B_AL_05_R03840_C02048 | 30 | 30 | 0 | 0 | NO |
| TRAIN | 14A9B_AL_06_R06400_C05376 | 16 | 16 | 0 | 0 | NO |
| TRAIN | 14A9B_AL_07_R05120_C09472 | 3 | 3 | 0 | 0 | NO |
| TRAIN | 14A9B_AL_08_R07424_C03584 | 14 | 14 | 0 | 0 | NO |
| TRAIN | 14A9B_AL_09_R01280_C04864 | 0 | 0 | 0 | 0 | NO |
| TRAIN | 14A9B_AL_10_R01792_C08960 | 0 | 0 | 0 | 0 | NO |
| DEV | 14A9B_DEV_11_R00256_C05888 | 22 | 22 | 0 | 0 | NO |
| DEV | 14A9B_DEV_12_R03840_C06400 | 4 | 4 | 0 | 0 | NO |
| DEV | 14A9B_DEV_13_R05888_C02816 | 9 | 9 | 0 | 0 | NO |
| DEV | 14A9B_DEV_14_R08448_C08960 | 14 | 14 | 0 | 0 | NO |

Les deux patches négatifs TRAIN vides AL09/AL10 n'ont pas non plus d'attestation persistée de revue complète du patch. Une couche vide n'est pas automatiquement un négatif humain validé.

## Corrections et tailles

Les deux CSV demandés sont créés dans les dossiers `manifests/` TRAIN et DEV : `14A9C_train_correction_summary.csv` et `14A9C_dev_correction_summary.csv`. **KEPT_CORRECT confirmé=0**, DELETED_FP=0, ADDED_FN=0, EDITED_BOUNDARY=0, SPLIT_MERGED=0. Les propositions inchangées mais non revues sont explicitement `UNCHANGED_UNREVIEWED` et classées OTHER (124 TRAIN / 49 DEV), sans inventer une validation KEEP.

Tailles descriptives identiques à 14A.9A : SMALL <=50 m², MEDIUM >50–200 m², LARGE >200 m². Sur les propositions persistées : TRAIN **0 / 58 / 66**, DEV **0 / 22 / 27**. Il ne s'agit pas de statistiques d'une GT humaine validée. Petits bâtiments ajoutés manuellement=0, petits bâtiments ajoutés sans parent C6=0, petites sorties de fusion corrigées=0. Ces zéros ne mesurent pas les omissions réelles de C6 dans les images ; ils reflètent l'absence d'ajouts humains enregistrés.

## Masques et readiness

**Aucun nouveau masque GT humain généré** : 0/10 TRAIN, 0/4 DEV. Les masques IA existants ne sont pas recyclés sous un nom GT. Les géométries sont techniquement exploitables mais les préconditions humaines sont absentes. L'alignement de nouveaux masques humains reste NOT_GENERATED ; celui des masques de préannotation avait été contrôlé en 14A.9B et ne vaut pas validation des corrections.

## Protection des splits et du GOLD

TRAIN∩DEV=0 ; TRAIN∩GOLD=0 ; DEV∩GOLD=0, contrôlés sur les emprises métriques verrouillées et les IDs, avec contrôle des hashes RGB sélectionnés. Les quatre DEV restent réservés à calibration, jamais TRAIN. Les fichiers sources corrigés/références et leurs WAL éventuels sont inchangés pendant cette QA. **78 fichiers GOLD** hashés avant/après : aucun changement. Aucun modèle, frontend, API ou registry modifié. Aucune inférence, aucun entraînement ni sweep de calibration.

## Action requise

1. Vérifier les sessions QGIS en cours sans fermer ni perdre les modifications non enregistrées.
2. Enregistrer les éditions des couches **MANUAL_CORRECTED_GT_PENDING**, et vérifier leur persistance dans les sources ci-dessus.
3. Renseigner les catégories de correction, les sources humaines et les statuts de revue ; attester explicitement les patches négatifs vides. Ne pas passer simplement toutes les copies IA à VALIDATED sans revue effective.
4. Refaire la QA sur la version humaine persistée ; générer les masques uniquement après succès, puis autoriser éventuellement 14A.9D.

Les snapshots et tableaux détaillés de cette QA sont conservés dans `qa/14A9C_correction_qa/`. Ils figent l'état observé ; une version source ultérieure devra être auditée dans une nouvelle exécution avec de nouveaux snapshots, sans écraser cette preuve.

## Statut final

TRAIN PATCHES :
10

DEV PATCHES :
4

TRAIN GT FEATURES :
124 (propositions IA persistées, non validées humainement)

DEV GT FEATURES :
49 (propositions IA persistées, non validées humainement)

TRAIN INVALID :
0

DEV INVALID :
0

TRAIN OOB :
0

DEV OOB :
0

TRAIN MASKS READY :
0 / 10

DEV MASKS READY :
0 / 4

SMALL BUILDINGS TRAIN :
0

SMALL BUILDINGS DEV :
0

C6 FALSE POSITIVES CORRECTED :
0

C6 MISSED BUILDINGS ADDED :
0

C6 MERGED BUILDINGS SPLIT :
0

TRAIN / DEV OVERLAP :
0

GOLD OVERLAP :
0

GOLD MODIFIED :
NO

READY_FOR_ACTIVE_LEARNING_TRAINING :
NO

READY_FOR_DEV_CALIBRATION :
NO

NEXT STEP :
FIX_CORRECTION_QA
