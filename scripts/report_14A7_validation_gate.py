"""Complete 14A.7 evidence outputs when the independent-GT gate fails."""
from __future__ import annotations
import csv
import hashlib
import json
import sqlite3
from pathlib import Path
import numpy as np
import rasterio

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision'
OUT=BASE/'qa/14A7_extended_validation'

def dump(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')

def csv_out(name,rows,fields):
    with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    audit=list(csv.DictReader((OUT/'14A7_data_leakage_audit.csv').open(encoding='utf-8-sig')))
    summary=json.loads((OUT/'14A7_inventory_summary.json').read_text())
    inventory=json.loads((OUT/'14A7_source_inventory.json').read_text())
    if any(r['ELIGIBLE_14A7']=='YES' for r in audit):
        raise RuntimeError('Eligible GT exists: do not issue an insufficiency report without reassessment.')
    status='NOT_RUN_VALIDATION_DATASET_INSUFFICIENT'
    # Check image-content aliases separately from filenames and geographic metadata.
    image_checks=[]
    for row in audit:
        p=ROOT/row['RGB']
        with rasterio.open(p) as ds:
            x=ds.read((1,2,3))
            image_checks.append(dict(patch_id=row['PATCH'],path=row['RGB'],shape=list(x.shape),pixel_sha256=hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest(),
                file_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    grouped={}
    for row in image_checks:grouped.setdefault(row['pixel_sha256'],[]).append(row['patch_id'])
    dump('14A7_rgb_identity_audit.json',dict(images=image_checks,duplicate_pixel_groups=[v for v in grouped.values() if len(v)>1]))
    # Compare actual TIFF metadata against the old catalog; never silently trust the catalog.
    rasters={r['path']:r for r in inventory['rasters'] if r.get('status')=='READABLE'}
    catalog=json.loads((ROOT/'test-data/building-ground-truth/patch_catalog.json').read_text())
    catalog_rows=[]
    for year in catalog['dates'].values():
        for row in year['patches']:
            path=row['patch_raster'].replace('\\','/')
            actual=rasters[path]['bounds'];b=row['bounds'];declared=[b['left'],b['bottom'],b['right'],b['top']]
            catalog_rows.append(dict(patch_id=row['patch_id'],path=path,declared_bounds=json.dumps(declared),actual_bounds=json.dumps(actual),
                                     bounds_match=all(abs(a-b)<1e-6 for a,b in zip(actual,declared))))
    csv_out('14A7_catalog_consistency.csv',catalog_rows,list(catalog_rows[0]))
    # Diagnose the corrected GPKG header without rewriting any blob or geometry.
    fixed=BASE/'annotations/14A5B_new_patch_expansion_gt_FIXED.gpkg'
    headers=[]
    if Path(str(fixed)+'-wal').exists() and Path(str(fixed)+'-wal').stat().st_size:
        raise RuntimeError('Nonempty WAL: no immutable inspection allowed')
    with sqlite3.connect(fixed.as_uri()+'?mode=ro&immutable=1',uri=True) as conn:
        for table,col in conn.execute('SELECT table_name,column_name FROM gpkg_geometry_columns'):
            blob=conn.execute('SELECT "'+col+'" FROM "'+table+'" LIMIT 1').fetchone()[0]
            headers.append(dict(layer=table,flags=blob[3],envelope_indicator=(blob[3]>>1)&7,declared_wkb_offset=8,
                actual_envelope_bytes_before_wkb=32,actual_wkb_offset=40))
    dump('14A7_fixed_gt_container_diagnostic.json',dict(path=str(fixed.relative_to(ROOT)),unreadable_features=sum(len(v.get('errors',[])) for v in inventory['geopackage_layers'] if '14A5B_new_patch' in v['path']),
          cause='Header flags declare no envelope, but XY envelope occupies 32 bytes before WKB. Standard WKB reader starts at byte 8 instead of 40.',layers=headers,modified=False))
    # Identify existing RGBs needing genuinely manual GT. No dataset/split is changed.
    proposed_ids=['14A2_2024_03','14A2_2024_07','14A2_2025_03','14A2_2025_07',
                  '13R_industrial_005_06656_03072','13R_industrial_011_08192_06656',
                  '13R_industrial_017_05120_08192','13R_industrial_023_01024_01536']
    proposed=[]
    for pid in proposed_ids:
        row=next(r for r in audit if r['PATCH']==pid)
        if row['SPLIT'].lower()!='val':
            raise RuntimeError('Proposal must already belong to VAL, never TRAIN: '+pid)
        if row['SPATIAL_OVERLAPS']!='{}' or row['HISTORICAL_REGION_OVERLAPS']!='{}':
            raise RuntimeError('Proposed annotation source conflicts with train/history: '+pid)
        proposed.append(dict(patch_id=pid,rgb=row['RGB'],existing_split=row['SPLIT'],scene_type=row['SCENE_TYPE'],
            human_gt_action='ANNOTATE_FROM_RGB_AND_VALIDATE_ALL_BUILDINGS',existing_labels='PSEUDO_LABELS_NOT_GT' if pid.startswith('13R_') else 'NO_APPROVED_MANUAL_GT',
            actual_scene_difficulty='REQUIRES_HUMAN_RGB_REVIEW',future_policy='RESERVE_FOR_C3_C6_EVALUATION_ONLY; DO_NOT_MOVE_EXISTING_SPLITS',
            bounds_32637=row['BOUNDS'],spatial_conflict_with_known_train=False,spatial_conflict_with_14A6C=False))
    csv_out('14A7_additional_gt_required.csv',proposed,list(proposed[0]))
    # Empty metrics are deliberate: no excluded RGB is silently evaluated.
    fields=['patch_id','model','evaluation_status','GT_BUILDINGS','TP','FP','FN','Object_Precision','Object_Recall','Object_F1','Pixel_IoU','Dice','Pixel_Precision','Pixel_Recall','Boundary_F1_1px','CPU_inference_seconds','total_patch_seconds','exclusion_reason']
    rows=[dict(patch_id=r['PATCH'],model=model,evaluation_status=status,exclusion_reason=r['REASON']) for r in audit for model in ('MODEL_C3','MODEL_C6')]
    csv_out('14A7_patch_metrics.csv',rows,fields)
    csv_out('14A7_false_positive_analysis.csv',[dict(model='MODEL_C6',fp_type=t,count=None,status=status) for t in ['road','bare_soil','shadow','vegetation','roof_like_surface','industrial_structure','unknown']],['model','fp_type','count','status'])
    csv_out('14A7_missed_buildings_analysis.csv',[dict(model=m,fn_type=t,count=None,status=status) for m in ('MODEL_C3','MODEL_C6') for t in ['small','low_contrast','shadow','dense_cluster','edge_of_patch','complex_roof','other']],['model','fn_type','count','status'])
    metrics={k:None for k in ['object_precision','object_recall','object_f1','TP','FP','missed','pixel_iou','dice','pixel_precision','pixel_recall','boundary_f1_1px','mean_boundary_distance','cpu_inference_seconds_mean','total_patch_seconds_mean']}
    global_data=dict(stage='14A.7',decision='VALIDATION_DATASET_INSUFFICIENT',validation_patches_executed=0,independent_patches_with_approved_gt=0,
        candidate_patches_audited=len(audit),train_leakage_executed=0,checkpoints=summary['checkpoints'],inference_executed=False,training_executed=False,
        pipeline=dict(threshold=0.30,minimum_component_area_px=479,morphology='NONE',connectivity=4,normalization='per_raster_RGB_minmax',activation='sigmoid',input_size=[512,512],
                      object_matcher='full_pairwise_IoU_Hungarian_max_sum_then_threshold_one_to_one',object_iou_threshold=0.30,
                      source='scripts/benchmark_14A6B_c3_vs_c6.py as used by 14A.6C',executed=False,retuned=False),
        MODEL_C3=dict(status=status,**metrics),MODEL_C6=dict(status=status,**metrics),generalization_gain='NOT_EVALUATED',production_model='MODEL_C',promotion=False,
        historical_14A6C_reference_only=dict(MODEL_C3=dict(object_recall=0.2128,object_f1=0.2817,FP=14,missed=37),MODEL_C6=dict(object_recall=0.4468,object_f1=0.4773,FP=20,missed=26,pixel_iou=0.3602,boundary_f1_1px=0.3819),rerun=False),
        next_step='PREPARE_ADDITIONAL_VALIDATION_GT',additional_manual_gt_patches=proposed_ids)
    dump('14A7_global_metrics.json',global_data)
    dump('14A7_overlays_manifest.json',dict(status=status,overlays_created=0,reason='No independent validated GT; instruction 15 STOP applies before inference. Historical AI outputs are not relabeled as new validation.'))
    seed=['14A2_2025_13','14A2_2024_13','14A2_2024_15','14A2_2025_14','14A2_2024_12']
    dump('14A7_training_lineage.json',dict(MODEL_C2=dict(source='MODEL_C',patches=seed,evidence='scripts/run_14A3_model_c2_finetuning.py'),
         MODEL_C3=dict(source='MODEL_C',train_patches=seed,calibration_patches=seed,evidence=['scripts/run_14A3B_model_c3_highres_revision.py','scripts/run_14A3C_model_c3_calibration.py']),
         MODEL_C4=dict(source='MODEL_C3',dataset='14A2_expansion/crops_14A3D/crop_manifest.json',evidence='scripts/train_model_c4_experimental.py'),
         MODEL_C5=dict(source='MODEL_C3',positive_crops_manifest='14A2_expansion/crops_14A3D/crop_manifest.json',negative_manifest='14A2_expansion/balanced_dataset_14A3E/hard_negative_manifest.json',internal_val_patch='14A2_2024_12',evidence='scripts/train_model_c5_balanced.py'),
         MODEL_C6=dict(source='MODEL_C3 best_model_c3_WEIGHTED_BCE_DICE.pth',inherited_train_patches=seed,direct_train_patches=['14A2_2024_06','14A2_2024_10','14A2_2025_02','14A2_2025_06'],
             source_script='scripts/train_model_c6_14A6.py',untrained_fifth_patch='14A2_2025_10',fifth_patch_independent=False,reason='Same geographic footprint as 14A2_2024_10',
             actual_internal_validation_executed=False,actual_training_epochs=2,actual_training_tiles=16,
             enriched_manifest_consumed=False,early_stopping_implemented=False,checkpoint_is_last_epoch_not_validation_selected=True)))
    c3=summary['checkpoints']['MODEL_C3'];c6=summary['checkpoints']['MODEL_C6']
    proposed_table='\n'.join(f"| `{p['patch_id']}` | {p['existing_split']} | {p['scene_type']} | GT humaine complète à créer |" for p in proposed)
    report=f'''# ÉTAPE 14A.7 — Extended internal validation MODEL_C3 vs MODEL_C6

Date : 9 novembre 2026. **Décision : VALIDATION_DATASET_INSUFFICIENT.** Le contrôle préalable des données échoue : aucun patch audité ne réunit GT humaine complète approuvée, indépendance du TRAIN direct/hérité et nouveauté vis-à-vis de 14A.6C. La règle STOP de la section 15 s'applique. Aucune inférence, aucun entraînement, aucune promotion n'a été lancé.

## Inventaire exécuté

Les trois racines demandées ont été lues : `backend/data/fine_tuning/buildings/`, `test-data/`, `backend/data/ground_truth/`. Inventaire : **{summary['files']} fichiers utiles**, **792 rasters TIFF lisibles / 792**, **110 enregistrements de couches/conteneurs GeoPackage**, **428 GeoJSON**, **74 patches candidats**. Les copies de diagnostics et prédictions ne sont pas de nouvelles GT.

`14A7_file_inventory.csv` donne les chemins et rôles. `14A7_source_inventory.json` donne CRS, dimensions, bandes, transforms, bounds, couches, comptes de features, erreurs et statuts. `14A7_spatial_sources.json` conserve les coordonnées natives et leur conversion en UTM 37N pour comparer les emprises dans un CRS commun. Le PROJ fourni avec Rasterio est utilisé dans le seul processus d'audit, pour éviter le `proj.db` PostGIS système incompatible ; aucune configuration système n'a été changée.

| Groupe | Données réelles | Décision d'éligibilité |
|---|---|---|
| Seed 14A.2B, 5 patches | GT manuelle approuvée, 100 features dans la référence | TRAIN/calibration C3, donc aussi exposition héritée par C6 : exclus |
| Nouveaux 14A5B | 5 patches, 85 annotations source | 4 patches effectivement entraînés par C6 ; le 5e recouvre un patch entraîné : exclus |
| Targeted 14A.3E/3E2 | Annotations de crops et hard negatives ; couverture complète non établie | Déjà utilisées dans le développement ; jamais traiter leurs zones non annotées comme fond certain |
| 13M, résidentiel/difficile | 4 patches humains, versions réparées approximatives | Recouvrent les emprises Seed C3, exposition héritée par C6 : exclus |
| 13M, industriel | 2 images, 1 feature par image, un seul site sur deux dates | Originaux NOT_REVIEWED et hors bounds ; version réparée explicitement approximative, pas de GT haute précision approuvée |
| 13R | 36 patches initiaux ; manifeste QA utilisable de 34 entrées | Labels `MODEL_C_PSEUDO_LABEL_REVIEWED`, pas GT humaine indépendante |
| VAL 14A2 | 4 RGB 512×512, deux sites sur deux années | Aucune GT humaine approuvée disponible |
| 14A_001 / 14A_003 | Référence historique 47 bâtiments | Contrôles 14A.6C uniquement ; exclus de la validation principale |
| Catalogue test-data | Templates GeoJSON d'annotation vides | Pas de GT ; plusieurs métadonnées du catalogue divergent des TIFF réels |
| Zones maxar_2025 | RGB et fichiers d'annotation vides | Pas de GT supplémentaire ; zones 1/3 = contrôle historique, zone 2 recouvre le TRAIN hérité |

## Provenance effective de C6 et fuite spatiale

Le script réel utilise `PATCHES[:-1]` : `14A2_2024_06`, `14A2_2024_10`, `14A2_2025_02`, `14A2_2025_06`, soit 16 crops 256×256. `14A2_2025_10` n'a pas été entraîné directement, mais son emprise est identique à celle de `14A2_2024_10` : il ne constitue pas une validation géographique indépendante.

C6 hérite aussi des cinq patches Seed utilisés par C3. Les `GT_2024/2025_residential_02` recouvrent à 100 % les emprises `14A2_2024/2025_13`. Les `GT_2024/2025_difficult_02` recouvrent deux emprises Seed/Targeted à 50 % chacune. Changer la date ou le nom ne supprime pas cette exposition.

Autre limite constatée dans le code C6 : le manifeste enrichi n'est pas consommé ; aucune validation interne, sélection de meilleur checkpoint ou early stopping n'est exécutée. `best_model_c6.pth` contient le dernier epoch, et l'attribut `best_epoch=2` ne prouve pas une sélection sur validation. Le présent audit corrige cette interprétation du rapport précédent sans modifier le checkpoint.

## Qualité des conteneurs et correspondance des sources

Le GeoPackage `14A5B_new_patch_expansion_gt_FIXED.gpkg` contient 85 features étiquetées VALIDATED mais son en-tête binaire est incohérent : flag 1 / enveloppe déclarée absente, alors que 32 octets d'enveloppe XY précèdent le WKB. Le lecteur conforme démarre au byte 8, au lieu du byte 40 réel ; **85/85 blobs échouent**. L'annonce antérieure d'un GeoPackage validé était donc trop large. Ce défaut est documenté dans `14A7_fixed_gt_container_diagnostic.json`, sans réparation ni changement de géométrie. Les masques déjà produits ne constituent pas de nouvelles annotations indépendantes.

Dans le catalogue `test-data/building-ground-truth`, **{sum(not x['bounds_match'] for x in catalog_rows)}/16 emprises déclarées divergent des TIFF réels**. Les emprises TIFF et les hashes de contenu sont consignés séparément ; aucune réparation ou substitution silencieuse n'a été appliquée.

## Pipeline et checkpoints figés

- C3 : `{c3['path']}` ; {c3['size']} bytes ; SHA256 `{c3['sha256']}`.
- C6 : `{c6['path']}` ; {c6['size']} bytes ; SHA256 `{c6['sha256']}`.
- Pipeline de référence 14A.6C : RGB natif 512×512, min-max RGB par image, sigmoid, threshold 0.30, composantes 4-connexes, aire minimale objet 479 px, aucune morphologie, matrice IoU complète, Hungarian maximum-somme puis filtrage IoU >= 0.30.
- Le code historique calcule les métriques pixel sur le masque seuillé avant filtrage des composantes, et les métriques objet sur les composantes filtrées. Cette distinction est enregistrée ; aucun paramètre n'a été ajusté.

## Contrôle historique : références conservées, aucun nouveau run

| Référence 14A.6C uniquement | C3 | C6 |
|---|---:|---:|
| Object Recall | 0.2128 | 0.4468 |
| Object F1 | 0.2817 | 0.4773 |
| FP | 14 | 20 |
| Missed | 37 | 26 |

Ces valeurs proviennent des rapports précédents ; elles ne sont pas présentées comme une nouvelle mesure indépendante ou une reproduction exécutée pendant 14A.7. Le gain de généralisation est **non évalué**, pas rejeté. Aucun classement FP/FN visuel n'est inventé en l'absence d'inférence admissible.

## Patches existants nécessitant une annotation manuelle

Voici les huit RGB proposés, tous déjà dans un split VAL, sans GT fabriquée, sans déplacement de split et sans création de dataset. Ils ne recouvrent ni le TRAIN connu ni les deux emprises historiques après mise dans un CRS commun. Aucun fichier de split TRAIN n'est proposé. Les catégories fines (petits bâtiments, ombres, toits adjacents) doivent être confirmées lors de la revue RGB humaine. Les annotations futures doivent être réservées à l'évaluation C3/C6.

| Patch | Split existant | Scène déclarée | Travail nécessaire |
|---|---|---|---|
{proposed_table}

Les variantes 2025 des deux VAL 14A2 couvrent les mêmes sites : les huit RGB représentent six emprises distinctes, avec deux réplications temporelles. Toutes les scènes sont déclarées industrielles. Ce plan exploite les VAL existants mais ne suffit pas encore à démontrer la généralisation résidentielle/dense : il faudra préparer des RGB VAL résidentiels/denses réellement nouveaux, hors TRAIN et hors emprises historiques, puis les annoter. Aucun identifiant de nouveau patch n'est inventé dans cette étape. Les deux `GT_2024/2025_industrial_02` peuvent être revus pour une évaluation complémentaire après approbation humaine, mais leur unique bâtiment et site ne suffisent pas à eux seuls. `13R_industrial_008_03584_04096` est exclu des propositions : il recouvre une zone historique et une petite partie du TRAIN après reprojection.

## Livrables et décision

Les cinq sorties minimales demandées sont créées. Les métriques non exécutées sont vides/null avec statut `{status}`, jamais zéro simulé. Les overlays RGB/GT/C3/C6 ne sont pas produits : le gate STOP interdit de lancer les prédictions sur des données inadmissibles ; `14A7_overlays_manifest.json` documente cette limite. Le plan d'annotation est dans `14A7_additional_gt_required.csv`. Aucune conclusion CONFIRMED/REJECTED n'est possible sans les annotations indépendantes ; le statut d'insuffisance prévu en section 15 prévaut.

VALIDATION PATCHES :
0 executed (74 candidats audités ; 2 contrôles historiques conservés)

INDEPENDENT PATCHES :
0 avec GT humaine complète approuvée

TRAIN LEAKAGE :
0 (aucun patch exécuté)

C3 CHECKPOINT :
{c3['path']}

C6 CHECKPOINT :
{c6['path']}

C3 OBJECT PRECISION :
NOT_RUN

C3 OBJECT RECALL :
NOT_RUN

C3 OBJECT F1 :
NOT_RUN

C3 FP :
NOT_RUN

C3 MISSED :
NOT_RUN

C3 PIXEL IOU :
NOT_RUN

C3 BOUNDARY F1 :
NOT_RUN

C3 CPU TIME :
NOT_RUN

C6 OBJECT PRECISION :
NOT_RUN

C6 OBJECT RECALL :
NOT_RUN

C6 OBJECT F1 :
NOT_RUN

C6 FP :
NOT_RUN

C6 MISSED :
NOT_RUN

C6 PIXEL IOU :
NOT_RUN

C6 BOUNDARY F1 :
NOT_RUN

C6 CPU TIME :
NOT_RUN

GENERALIZATION GAIN :
NOT_EVALUATED — VALIDATION_DATASET_INSUFFICIENT

FINAL DECISION :
VALIDATION_DATASET_INSUFFICIENT

PRODUCTION MODEL :
MODEL_C

NEXT STEP :
PREPARE_ADDITIONAL_VALIDATION_GT
'''
    (ROOT/'docs/ETAPE_14A7_EXTENDED_INTERNAL_VALIDATION_MODEL_C6.md').write_text(report,encoding='utf-8')
    print(json.dumps(dict(decision=global_data['decision'],additional_manual_gt_patches=proposed_ids,catalog_bound_mismatches=sum(not r['bounds_match'] for r in catalog_rows),checkpoint_hashes=summary['checkpoints']),indent=2))

if __name__=='__main__':main()
