"""Final data/integrity QA and review instructions. No calibration/training."""
from pathlib import Path
import sys,json,sqlite3
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A9B_datasets import ROOT,BASE,AL,DEV,GOLD,dump,sha,csvwrite
from diagnose_14A9A_small_buildings import rasterize
from osgeo import gdal
from shapely import wkb
from shapely.ops import unary_union
from shapely.geometry import box
from pyproj import Transformer
import numpy as np

def main():
 records=json.loads((AL/'manifests/14A9B_selected_patches.json').read_text());inv=json.loads((AL/'qa/14A9B_all_rgb_inventory.json').read_text())
 gold=json.loads((AL/'qa/GOLD_HASHES_BEFORE.json').read_text());assert all(sha(ROOT/p)==h for p,h in gold.items())
 assert all(sha(ROOT/r['rgb_path'])==r['sha256'] for r in inv if r.get('readable'))
 assert sha(ROOT/records[0]['source'])==records[0]['source_sha256']
 proto=json.loads((BASE/'qa/14A8_model_shootout/14A8_frozen_protocol.json').read_text())
 for s in proto['models']:
  if s['model'] in ['MODEL_C','MODEL_C6']:assert sha(ROOT/s['path'])==s['sha256']
 checks=[];totals={}
 for directory,split,aimember,manmember in [(AL,'ACTIVE_LEARNING_TRAIN','train_candidates','corrected_gt'),(DEV,'DEV_CALIBRATION','qa','gt')]:
  ai=directory/aimember/'AI_PREANNOTATION_C6.gpkg';manual=directory/manmember/'MANUAL_CORRECTED_GT.gpkg'
  for p in [ai,manual]:
   con=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);assert con.execute('pragma integrity_check').fetchone()[0]=='ok';con.close()
  total=0
  for r in [r for r in records if r['split']==split]:
   rgb=gdal.Open(str(ROOT/r['rgb_path']));tx=Transformer.from_crs('EPSG:32637',rgb.GetProjection(),always_xy=True);geoms=[];serialized=[]
   ds=gdal.OpenEx(str(manual),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES']);l=ds.GetLayerByName(r['patch_id']);assert l.GetSpatialRef().GetAuthorityCode(None)=='32637'
   for f in l:
    geom=wkb.loads(bytes(f.GetGeometryRef().ExportToWkb()));assert geom.is_valid and not geom.is_empty and geom.area>0 and box(*r['bounds_32637']).buffer(1e-6).covers(geom)
    assert all(f.GetField(k) is not None for k in ['patch_id','building_id','proposal_id','source','label_source','error_category','correction_action','annotation_status','review_status','is_ground_truth','annotator'])
    assert f['is_ground_truth']==0 and f['review_status']=='NOT_REVIEWED';geoms.append(geom);serialized.append(geom.wkb)
   ds=None;assert len(set(serialized))==len(serialized);total+=len(geoms)
   mask=rasterize(unary_union(geoms),tx,rgb.GetGeoTransform(),rgb.GetProjection()) if geoms else np.zeros((512,512),bool)
   mpath=directory/('train_candidates/AI_PREANNOTATION_C6' if directory==AL else 'qa/AI_PREANNOTATION_C6')/(r['patch_id']+'_AI_mask.tif');m=gdal.Open(str(mpath));assert np.array_equal(mask,m.ReadAsArray().astype(bool))
   assert rgb.GetProjection()==m.GetProjection() and rgb.GetGeoTransform()==m.GetGeoTransform()
   checks.append(dict(patch_id=r['patch_id'],proposals=len(geoms),valid_geometry=True,out_of_bounds=0,duplicates=0,vector_mask_round_trip='EXACT',human_gt='NOT_VALIDATED',rgb_sha256=sha(ROOT/r['rgb_path'])))
  totals[split]=total
 dump(AL/'qa/14A9B_FINAL_QA.json',dict(checks=checks,proposals=totals,gold_files_checked=len(gold),gold_modified=False,original_rgb_checked=len(inv),original_rgb_modified=False,source_orthophoto_modified=False,models_c_c6_unchanged=True,training=False,calibration=False,train_dev_overlap=0,gold_overlap=0,human_gt_validation='PENDING'))
 dump(AL/'qa/GOLD_HASHES_AFTER.json',{p:sha(ROOT/p) for p in gold})
 # Freeze the actual RGB split and model/protocol before human correction.
 dump(AL/'manifests/14A9B_review_protocol.json',dict(model='MODEL_C6',weights_sha256=next(s['sha256'] for s in proto['models'] if s['model']=='MODEL_C6'),preprocessing='RGB_GLOBAL_PATCH_MINMAX',threshold=.30,min_component_pixels=479,connectivity=4,morphology='NONE',calibration_run=False,training_run=False,training_allowed=False,calibration_allowed=False,
  train=[r['patch_id'] for r in records if r['split']=='ACTIVE_LEARNING_TRAIN'],dev=[r['patch_id'] for r in records if r['split']=='DEV_CALIBRATION'],human_validation_required=True,
  stop_conditions=['All proposals must be reviewed including image regions with no prediction.','Reject or correct major FN/FP/merges/boundaries.','Human-corrected vectors require geometry/bounds/duplicate QA and aligned binary GT masks.','Only then validate labels; DEV may calibrate but may never join TRAIN.']))
 instructions='''# Revue humaine 14A.9B

Ouvrir le .qgz du dossier qgis. Les groupes/bookmarks correspondent aux patches. Seul le premier groupe est visible au démarrage.

La couche verte MANUAL_CORRECTED_GT_PENDING est une **copie des prédictions**, pas encore de la vérité terrain. La référence violette AI_PREANNOTATION_C6_NOT_GT est figée et masquée au démarrage ; l'activer pour comparer. Modifier uniquement la couche verte.

- KEEP : conserver les contours corrects et renseigner correction_action=KEEP.
- DELETE : supprimer les faux positifs dans la copie verte, jamais dans la référence IA.
- EDIT / SPLIT : corriger les limites ou scinder les bâtiments fusionnés.
- ADD : ajouter les bâtiments manqués, en particulier les petits toits et zones sans prédiction.
- Renseigner error_category selon le cas : FN_SMALL, FN_SHADOW, FN_LOW_CONTRAST, MERGED, BOUNDARY_BAD, FP_ROAD, FP_BARE_SOIL, FP_OTHER. Pour KEEP sans erreur, conserver UNCLASSIFIED. Renseigner annotator.
- Après contrôle de toute l'image : review_status=REVIEWED et annotation_status=ANNOTATED. Conserver is_ground_truth=0 jusqu'à la QA finale. Enregistrer les modifications des couches dans le GeoPackage.

Les nouveaux objets reçoivent un UUID et les attributs de patch. Adapter error_category, dont la valeur initiale est FN_SMALL, à l'erreur réellement observée. Conserver proposal_id pour EDIT/SPLIT ; les nouveaux FN sans parent restent identifiables par building_id. Les nouvelles features sont HUMAN_CORRECTED_PENDING_QA ; les propositions copiées restent MODEL_C6_PREDICTION_NOT_GT jusqu'à la QA finale.

Le manifeste d'erreurs initial n'annonce aucune correction humaine. Après revue, sa mise à jour doit comparer les proposal_id de la référence figée et de la copie : identifier les suppressions, nouveaux objets, éditions et scissions, puis reprendre les catégories humaines. Ne pas inventer de catégorie pour un objet supprimé sans information : la faire confirmer. Les lignes NO_FINAL_C6_PROPOSAL sont des tâches de revue de patch, pas des faux négatifs confirmés.

Les deux patches centrés sur route/sol nu n'ont aucune proposition finale C6 : vérifier visuellement l'absence de bâtiments, puis déclarer explicitement le négatif humain si approprié. Les autres patches comportent des omissions ; la revue doit aussi parcourir les régions sans contour. Il n'est pas nécessaire de redessiner les contours déjà corrects, mais tous les bâtiments manqués doivent être ajoutés.

Aucun masque GT humain final n'est livré à ce stade. Après QA humaine, générer les masques 512×512 {0,1} sur la grille native RGB, sans resampling, puis seulement autoriser TRAIN ou calibration selon le split verrouillé.
'''
 (AL/'MANUAL_REVIEW.md').write_text(instructions,encoding='utf-8');(DEV/'MANUAL_REVIEW.md').write_text(instructions+'\nDEV : calibration uniquement après QA ; ne jamais déplacer ces patches vers TRAIN.\n',encoding='utf-8')
 (DEV/'masks/README.md').write_text('Aucun masque Ground Truth humain valide pour le moment. Les masques IA se trouvent dans qa/AI_PREANNOTATION_C6 et ne doivent pas être traités comme GT.\n',encoding='utf-8')
 desktop_path=AL/'qa/QGIS_DESKTOP_QA.json';desktop=json.loads(desktop_path.read_text()) if desktop_path.exists() else {'status':'NOT_EXECUTED_OR_NOT_COMPLETED'}
 desktop_summary=desktop.get('status',{'train':desktop.get('train',{}).get('open_reopen_editing','PENDING'),'dev':desktop.get('dev',{}).get('open_reopen_editing','PENDING')})
 eligible=sum(r.get('historical_train_status')=='TRAIN' and not r.get('duplicate_of') for r in inv)
 duplicate=sum(bool(r.get('duplicate_of')) for r in inv)
 report=f'''# 14A.9B — Active Learning ciblé et DEV non-GOLD

## Livraison

Deux jeux **distincts**, sans entraînement ni calibration : **10 patches ACTIVE_LEARNING_TRAIN**, **4 patches DEV_CALIBRATION**. Les 14 RGB sont des fenêtres nouvelles 512×512 de l'orthophoto locale, copiées sans resampling et sans modifier la source. Aucun ancien TRAIN/VAL/TEST n'a changé d'affectation.

Projets directement ouvrables :

- `14A9B_active_learning/qgis/14A9B_ACTIVE_LEARNING_CORRECTION.qgz` : 30 couches (10 RGB, 10 références IA, 10 copies éditables), 10 bookmarks.
- `14A9B_dev_set/qgis/14A9B_DEV_CALIBRATION_CORRECTION.qgz` : 12 couches, 4 bookmarks.

Références IA violettes en lecture seule ; copies éditables vertes préremplies. Une seule paire de travail visible au départ. Les couches s'appellent explicitement NOT_GT / GT_PENDING. **Aucune GT humaine n'est déjà validée**. Le DEV n'est donc **pas prêt à calibrer**.

## Inventaire et séparation

163 petits RGB GeoTIFF (3 bandes minimum, jusqu'à 1024 pixels) inventoriés récursivement dans les jeux Building et test-data : tous lisibles ; {duplicate} doublons stricts de pixels identifiés, non sélectionnés comme nouvelles données. {eligible} sources TRAIN non dupliquées sont seulement admissibles à une re-revue historique. Les sources à statut ambigu, GOLD, VAL et TEST restent exclues. Les PNG de visualisation, masques mono-bande, probabilités et grandes orthophotos parentes ne sont pas assimilés à des patches RGB d'annotation. L'inventaire historique complet et ses emprises sont conservés dans qa/.

208 fenêtres nouvelles éligibles spatialement examinées sur cinq planches RGB ; elles constituent des **candidats**, pas 208 nouveaux fichiers matérialisés ni 208 fenêtres mutuellement disjointes. Quatre sont réservées au DEV, donc 204 restent potentiellement TRAIN avant toute sélection additionnelle. Le CSV demandé comprend les 163 sources historiques et ces 208 fenêtres, avec origine, statut, exclusion, contexte et sélection. Les contextes non examinés restent UNREVIEWED.

Les 14 fenêtres retenues sont toutes distantes de **plus de 20 m** entre elles et des emprises historiques protégées, incluant les 4 GOLD, le pool 14A.7 réservé à validation et les références déclarées de tests anciens. Empreintes de pixels uniques, différentes des anciens RGB. Garde GOLD vérifié sur ID, hash et emprise. **TRAIN/DEV overlap=0 ; GOLD overlap=0**. La même acquisition Maxar parente reste partagée : développement interne spatialement séparé, aucune prétention d'indépendance entre acquisitions.

## Répartition exclusive du batch TRAIN

| Groupe principal de revue | Nombre | Patches AL |
|---|---:|---|
| Petits bâtiments / diversité de toits | 4 | 01,02,03,04 |
| Dense / adjacent | 2 | 05,06 |
| Ombres / faible contraste | 2 | 07,08 |
| Contexte FP route / sol nu | 2 | 09,10 |

Les catégories décrivent la priorité visuelle du patch, pas une GT de taille ou de matériau. La présence et la surface exactes des petits bâtiments seront confirmées par l'humain ; plusieurs contextes se recoupent. Les 4 DEV couvrent dense, résidentiel, ombres et scènes mixtes séparément.

## C6 utilisé exclusivement pour proposer

Même checkpoint SHA256 `7690722427f1c9e78eb8afa5877bbdb96544e9b2594e93adfa4084b5f2ab1f84`, strict load réussi, CPU PyTorch, RGB min-max global, sigmoid, seuil historique **0,30**, connexité **4**, filtre historique **479 pixels**, aucune morphologie. **Aucun sweep**. Le protocole et le split sont enregistrés avant correction humaine.

**124 propositions TRAIN**, **49 propositions DEV**, soit **173** au total, toutes étiquetées MODEL_C6_PREDICTION_NOT_GT, NOT_REVIEWED, NOT_VALIDATED et is_ground_truth=0. Les copies vertes reprennent ces géométries ; elles ne deviennent pas humaines par simple copie.

La table `14A9B_C6_priority_indicators.csv` décrit composantes brutes/petites, fraction proche de 0,30 et couverture. La bande descriptive [0,25;0,35] ne change aucun masque et ne sélectionne aucun nouveau seuil. Par exemple AL04 comporte 25 petites composantes sur 40 ; AL05 montre 41 composantes brutes et des toits voisins fusionnés dans les overlays. Les planches finales ont été inspectées. Les deux scènes route/sol nu n'ont aucune composante finale : **contextes négatifs à examiner**, pas un nombre de FP humains confirmé. Le manifeste d'erreurs reste PENDING_HUMAN_REVIEW : aucun FN/FP corrigé fictif.

## Revue à réaliser

KEEP, DELETE, EDIT, SPLIT, ADD dans la copie verte. Utiliser les huit catégories demandées pour les erreurs et renseigner annotator. Voir `MANUAL_REVIEW.md` dans chaque dataset. Les UUID, proposal_id, correction_action et statuts permettent le rapprochement avec la référence figée ; les suppressions devront être reprises dans le manifeste d'erreurs lors de la QA post-correction. Aucun script utilisateur ou console Python requis pour ouvrir les projets et modifier les couches.

Les propositions réduisent le dessin initial, mais **les zones sans prédiction doivent aussi être revues**. Ajouter les bâtiments manqués. Ne pas utiliser les copies comme labels finaux avant cette revue, notamment sur petits objets. Les masques présents sont des masques **IA** rangés sous AI_PREANNOTATION_C6 ; le dossier DEV/masks ne contient volontairement aucun faux masque GT humain. Les masques humains binaires seront produits après correction et validation.

## Contrôles réellement exécutés

- 14 RGB strictement identiques aux fenêtres parentes ; dimensions/grilles natives conservées. Projet/vectoriels EPSG:32637, RGB natifs EPSG:4326 affichés par transformation QGIS ; aucune reprojection des RGB.
- 173 propositions valides, non vides, surfaces positives ; hors bounds=0, doublons de géométries par patch=0, attributs complets avec statuts explicites.
- Ré-rastérisation des vecteurs de travail sur chaque grille RGB : **égalité pixel par pixel** avec les masques IA correspondants ; dimensions, CRS et transform identiques.
- SQLite integrity_check=ok sur les quatre GeoPackages. Édition et persistance d'une feature test validées **dans une copie temporaire seulement**.
- Les deux projets s'ouvrent et se rouvrent via PyQGIS 3.40.14 ; 30/12 couches valides et 10/4 bookmarks. Le constructeur a émis des avertissements SQLite lors du nettoyage de connexions ; les contrôles indépendants des quatre fichiers ont ensuite confirmé intégrité et lecture complètes. Ne pas attribuer ces avertissements à une corruption sans preuve.
- Contrôle Desktop dédié : `{json.dumps(desktop_summary)}`. Résultats détaillés dans `qa/QGIS_DESKTOP_QA.json` lorsqu'exécutés complètement. Un simple lancement sans résultat n'est pas un PASS.
- **78 fichiers GOLD** comparés par SHA256 avant/après : aucun changement. 163 RGB historiques inchangés, orthophoto parente et poids C/C6 inchangés. Production backend/frontend non modifiée. Aucun modèle promu, aucune calibration, aucun entraînement.

## Décision

**Prêt pour correction humaine assistée. Pas prêt pour calibration DEV.** Après correction : QA géométrique et sémantique, finalisation des sources/statuts humains, masques alignés, registre des erreurs et vérification de fuite. Ensuite seulement autoriser une étape de calibration sur DEV ; figer les paramètres avant tout retour sur GOLD. Les 4 DEV ne rejoindront jamais le futur TRAIN.

ACTIVE LEARNING CANDIDATES :
208 fenêtres nouvelles examinées (204 hors réserve DEV) ; 163 RGB historiques audités séparément

ACTIVE LEARNING SELECTED :
10

SMALL BUILDING PATCHES :
4 (contexte attendu, à confirmer humainement)

DENSE / ADJACENT PATCHES :
2

SHADOW / LOW CONTRAST PATCHES :
2

FP-FOCUSED PATCHES :
2

DEV PATCHES :
4

TRAIN / DEV OVERLAP :
0

GOLD OVERLAP :
0

GOLD MODIFIED :
NO

AI PREANNOTATION USED :
YES

FULL MANUAL ANNOTATION REQUIRED :
NO

READY_FOR_AI_ASSISTED_CORRECTION :
YES

READY_FOR_DEV_CALIBRATION :
NO

NEXT STEP :
AI_ASSISTED_CORRECTION_14A9B
'''
 (ROOT/'docs/ETAPE_14A9B_ACTIVE_LEARNING_AND_DEVSET_PREPARATION.md').write_text(report,encoding='utf-8')
 print(json.dumps(dict(proposals=totals,gold_unchanged=len(gold),historical_rgb_unchanged=len(inv),ready_for_correction=True,ready_for_calibration=False)))
if __name__=='__main__':main()
