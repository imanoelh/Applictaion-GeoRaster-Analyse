"""Write inspected FP labels and diagnostic report; never modify source artifacts."""
from pathlib import Path
import sys,json,csv
sys.path.insert(0,str(Path(__file__).resolve().parent))
from diagnose_14A9A_small_buildings import ROOT,BASE,BENCH,OUT,readcsv,writecsv,dump,sha,FONT
from gold_set_14A7_guard import assert_non_gold_development_records
from osgeo import gdal
from PIL import Image,ImageDraw
import numpy as np

def main():
    summary=json.loads((OUT/'14A9A_summary.json').read_text())
    small=readcsv(OUT/'14A9A_small_buildings.csv')
    fp=[r for r in readcsv(BENCH/'14A8_false_positive_analysis.csv') if r['MODEL']=='MODEL_C6']
    # All eleven RGB/GT/prediction crops inspected in 14A9A_FP_ALL_11.png.
    notes={
      'FP14':'Roof-edge/partial roof footprint; shape discrepancy with neighbouring GT.',
      'FP15':'Grey/light roof partially covered; object IoU insufficient.',
      'FP16':'Roof-edge fragment next to road; context checked on full 14A8 overlay.',
      'FP103':'Several adjacent roofs connected into a single prediction.',
      'FP104':'Partial bright roof at patch edge; insufficient footprint agreement.',
      'FP105':'Reddish roof-like object without corresponding matched locked GT; semantics uncertain.',
      'FP106':'Several adjacent bright roofs connected into a single prediction.',
      'FP107':'Dark elongated roof-like surface; uncertain material, not classified as shadow solely from brightness.',
      'FP257':'Bright square roof-like object without matched locked GT.',
      'FP258':'Fragment on bright/grey roof-like surface without matched locked GT.',
      'FP259':'Road surface and painted crosswalk clearly visible.'}
    assert {r['REVIEW_ID'] for r in fp}==set(notes)
    rows=[dict(review_id=r['REVIEW_ID'],patch_id=r['PATCH'],prediction_id=r['PRED_ID'],area_m2=r['AREA_M2'],best_gt_iou=r['BEST_GT_IOU'],
         category='ROAD' if r['REVIEW_ID']=='FP259' else 'ROOF_LIKE_SURFACE',visual_review='YES',reviewer='ASSISTANT_VISUAL_RGB_REVIEW_NOT_HUMAN_GT',
         note=notes[r['REVIEW_ID']],image=r['REVIEW_ID']+'.png') for r in fp]
    writecsv(OUT/'14A9A_fp_categories.csv',rows)
    protocol=json.loads((BENCH/'14A8_frozen_protocol.json').read_text())
    alignment=[]
    for p in protocol['patches']:
        source=gdal.Open(str(ROOT/p['rgb_path']))
        for suffix in ['probability','threshold','components','final']:
            d=gdal.Open(str(OUT/(p['patch_id']+'_'+suffix+'.tif')))
            assert (d.RasterXSize,d.RasterYSize)==(512,512)
            assert d.GetProjection()==source.GetProjection() and d.GetGeoTransform()==source.GetGeoTransform()
            a=d.ReadAsArray()
            assert np.isfinite(a).all()
            if suffix=='probability':assert a.min()>=0 and a.max()<=1
            if suffix in ('threshold','final'):assert set(np.unique(a))<={0,1}
            alignment.append(dict(patch_id=p['patch_id'],state=suffix,alignment='EXACT_NATIVE_GRID',passed=True))
    dump(OUT/'14A9A_alignment_QA.json',alignment)
    # Select existing TRAIN images for future error-focused re-review only.
    # These are not new independent data, and no new C6 preannotations are run here.
    wanted=['14A2_2024_02','14A2_2024_06','14A2_2024_10','14A2_2024_13','14A2_2025_02']
    manifest=json.loads((BASE/'14A2_expansion/manifests/dataset_manifest.json').read_text())
    records=[];images=[]
    for pid in wanted:
        m=next(x for x in manifest['patches'] if x['patch_id']==pid);assert m['split'].lower()=='train'
        rgb=BASE/'14A2_expansion/train/rgb'/(pid+'.tif');r=gdal.Open(str(rgb));assert r
        a=np.moveaxis(r.ReadAsArray()[:3],0,-1)
        record=dict(patch_id=pid,split='TRAIN_EXISTING_REVIEW_ONLY',rgb_path=str(rgb.relative_to(ROOT)),rgb_sha256=sha(rgb),bounds_32637=m['bounds'],scene_type=m['scene_type'],
          target_context='SMALL;LOW_CONTRAST;DENSE;SHADOW;ADJACENT - confirm human selection before correction',
          role='EXISTING_TRAIN_ERROR_REVIEW_NOT_NOVEL_EXPANSION',preannotation='C6_FUTURE_STEP_NOT_RUN',training_allowed_now=False)
        records.append(record);images.append(Image.fromarray(a))
    assert_non_gold_development_records(records)
    dump(OUT/'14A9A_non_gold_review_shortlist.json',dict(records=records,gold_guard='PASS',new_independent_data=False,
         warning='Existing train imagery, not new expansion. Do not reassign to DEV/VAL. Fresh spatially disjoint NON-GOLD DEV imagery must be selected separately before calibration. Existing AI_ASSISTED_POOL is VALIDATION_LOCKED_FOR_C3_C6 and remains excluded from TRAIN.',
         next_actions=['Confirm small-building target contexts visually; preserve existing validated GT.',
                       'In a separately authorized step create C6 preannotations in copies; human corrects FN/FP/merges/boundaries only.',
                       'Select fresh spatially disjoint NON-GOLD DEV patches for calibration; freeze split before any sweep.',
                       'Train only after human validation and leakage checks; freeze all parameters on DEV before next GOLD evaluation.']))
    sheet=Image.new('RGB',(512*len(images),540),'white');d=ImageDraw.Draw(sheet)
    for i,(record,im) in enumerate(zip(records,images)):
        sheet.paste(im,(i*512,28));d.text((i*512+4,4),record['patch_id']+' TRAIN review only',fill='black',font=FONT)
    sheet.save(OUT/'14A9A_NON_GOLD_REVIEW_SHORTLIST.png')
    integrity=json.loads((OUT/'14A9A_integrity.json').read_text())
    assert all(sha(ROOT/p)==h for p,h in integrity['sha256_before_after'].items())
    summary.update(fp_categories={'ROOF_LIKE_SURFACE':10,'ROAD':1,'BARE_SOIL':0,'SHADOW':0,'INDUSTRIAL':0,'OTHER':0},
      decision='CASE_C_MIXED_LIMITATION',dominant='MIXED',primary_bottleneck='BEFORE_THRESHOLD_MODEL_RESPONSE',
      next_step='ACTIVE_LEARNING_PLUS_NON_GOLD_CALIBRATION',gold_used_for_calibration=False,source_files_changed=0,training=False,
      production='MODEL_C_UNCHANGED',visual_review_small=38,visual_review_fp=11,
      true_model_failures_caveat='20 no-enrichment proxy cases, not causal proof; 29/38 have no operational-threshold response. Relative enrichment in nine subthreshold cases is extremely weak, never evidence that lowering threshold would work.')
    dump(OUT/'14A9A_summary.json',summary)
    end='''GOLD SMALL BUILDINGS :
38

C6 SMALL DETECTED FINAL :
0 / 38

MODEL SIGNAL PRESENT :
17 / 38 (enrichissement relatif ; 9 / 38 franchissent 0,30)

SURVIVE THRESHOLD 0.30 :
9 / 38

REMOVED BY 479 PX :
3 / 38

MERGED :
5 / 38

MATCHING FAILURES :
1 / 38

TRUE MODEL FAILURES :
20 / 38 (proxy sans enrichissement local ; causalite non demontree)

DOMINANT FAILURE CAUSE :
MIXED

GOLD USED FOR CALIBRATION :
NO

PRODUCTION MODEL :
MODEL_C

PRODUCTION MODIFIED :
NO

NEXT STEP :
ACTIVE_LEARNING_PLUS_NON_GOLD_CALIBRATION'''
    report='''# 14A.9A — Diagnostic des petits bâtiments C6

## Conclusion

**CASE_C_MIXED_LIMITATION**. La réponse avant seuillage constitue le principal goulot : **29/38** petits bâtiments ne contiennent aucun pixel à 0,30. Le filtre historique supprime toute la couverture de **3/38**, dont **2** étaient réellement appariables avant filtrage. Les fusions expliquent **5** autres échecs ; le dernier objet conserve une prédiction mais manque l'IoU requis. Le filtre seul ne peut donc pas expliquer les 38 échecs. Aucun changement de paramètre n'est proposé sur le GOLD.

## Artefacts et protocole immuables

Lecture des probabilités C6 archivées dans `qa/14A8_model_shootout/models/MODEL_C6/`, sans nouvelle inférence. Checkpoint `backend/data/models/model_c6_experimental/best_model_c6.pth`, SHA256 `7690722427f1c9e78eb8afa5877bbdb96544e9b2594e93adfa4084b5f2ab1f84`.

Les quatre RGB, les 165 features du GT FIXED et les masques verrouillés sont ceux de 14A.8. SMALL reste **surface GT <=50 m²**, définition antérieure aux annotations GOLD. Prétraitement historique RGB min-max global par patch, aucune interpolation ; sigmoid, seuil **>=0,30**, connexité **4**, composantes **>=479 pixels**, aucune morphologie. Les masques reconstitués sont identiques pixel par pixel aux sorties 14A.8. Les 16 états diagnostiques GeoTIFF conservent exactement dimensions 512×512, CRS natif et transform des RGB. Les RGB/masques GOLD sont en EPSG:4326 ; seuls les vecteurs GT/mesures de surfaces et IoU sont en EPSG:32637. Pas de changement de CRS des sources.

**274 fichiers** existants contrôlés par SHA256 avant/après : aucun changement (GOLD, sorties complètes 14A.8, modèles référencés, manifestes). Aucun entraînement, benchmark multi-modèle, téléchargement ou changement de production.

## Définition du signal et limites causales

Il n'existait pas de seuil historique définissant un « signal significatif » sous 0,30. Pour éviter d'en calibrer un sur le GOLD, le diagnostic enregistre les probabilités exactes et un **proxy descriptif d'enrichissement spatial** : moyenne ET p90 dans le GT supérieurs aux valeurs correspondantes dans un anneau de 3 pixels, excluant tous les GT. Cette règle a été écrite avant le calcul. Ce n'est ni un test de significativité, ni une probabilité calibrée, ni un nouveau seuil de détection.

**17/38** présentent cet enrichissement relatif. Il ne faut pas les interpréter comme 17 détections latentes : les **9 cas B** ont un maximum compris entre **0,00000164 et 0,02110**, donc une réponse absolument très faible malgré le contraste relatif. Les **20 cas A** ne présentent même pas cet enrichissement et restent sous 0,30. « TRUE MODEL FAILURES » désigne uniquement ce proxy A ; une causalité interne au réseau n'est pas démontrée. Le constat robuste indépendant du proxy reste **29/38 sans aucun pixel >=0,30**. Un des neuf objets avec pixels au seuil n'a pas d'enrichissement relatif (contexte voisin plus fort) ; les deux compteurs ne sont donc pas emboîtés.

## Attribution exclusive des 38 échecs

Ordre : sans pixel au seuil -> A/B selon enrichissement ; toute couverture supprimée -> C ; couverture finale avec fusion selon la règle figée -> D ; couverture restante sans appariement -> E ; sinon F.

| Stade | Nombre | Observation |
|---|---:|---|
| A MODEL_SIGNAL_ABSENT | 20 | Aucun enrichissement local et aucun pixel au seuil |
| B BELOW_THRESHOLD | 9 | Enrichissement relatif mais très faible en valeur absolue |
| C REMOVED_BY_MIN_COMPONENT | 3 | Toute la couverture brute supprimée par 479 px |
| D MERGED_WITH_NEIGHBOR | 5 | Composante finale couvrant >=30 % de chacun d'au moins deux GT |
| E MATCHING_FAILURE | 1 | Couverture finale, IoU insuffisante, aucun bug démontré |
| F OTHER | 0 | — |

**9/38** ont une couverture binaire brute ; **6/38** gardent des pixels au final ; **0/38** sont appariés. Aucun des 38 n'a même une IoU finale >=0,30 : la contrainte un-à-un ne leur retire donc aucune paire admissible. Le matcher reste celui de 14A.8 : maximum de paires admissibles, puis maximum d'IoU ; aucun comptage multiple d'une prédiction.

### Effet exact des 479 pixels

| Patch / GT ID stable 14A.8 | Taille composante | Meilleure IoU brute | Apparié avant filtre |
|---|---:|---:|---|
| RESIDENTIAL_02 / 4 | 223 px | 0,6760 | Oui |
| DENSE_04 / 64 | 434 px | 0,7483 | Oui |
| DENSE_04 / 102 | 76 px | 0,1815 | Non |

**REMOVED_BY_479PX = 3/38**, mais seulement **2/38 détections objet admissibles** perdues spécifiquement au filtrage. Le troisième masque était déjà insuffisant avant filtre. Ce calcul utilise exclusivement l'état intermédiaire historique ; il ne constitue pas un essai de nouvelle configuration.

Les cinq fusions concernent GT IDs **6, 49, 50, 110, 128**. Le cas E est **GT46**, IoU **0,293** : désaccord d'emprise, pas preuve d'une erreur de matching. Aucun abaissement du seuil d'IoU n'a été testé.

## Comparaison par taille

MEDIUM (50–200 m²) et LARGE (>200 m²) sont des strates descriptives nouvelles, annoncées avant le calcul, sans prétendre qu'elles existaient dans 14A.8. Elles ne modifient pas SMALL ni le protocole de scoring.

| Taille | GT | Détectés finaux | Recall | Pixel au seuil | Toute couverture supprimée | Couverture finale |
|---|---:|---:|---:|---:|---:|---:|
| SMALL <=50 m² | 38 | 0 | 0 % | 9 | 3 | 6 |
| MEDIUM >50–200 m² | 103 | 25 | 24,27 % | 68 | 13 | 55 |
| LARGE >200 m² | 24 | 12 | 50,00 % | 15 | 0 | 15 |

Il existe un gradient de taille, mais pas une limitation exclusivement SMALL : 13 bâtiments moyens perdent aussi toute leur couverture et les 23 GT du patch INDUSTRIAL restent non détectés. **17/38 SMALL sont dans ce patch INDUSTRIAL** : taille et domaine de scène sont confondus sur ce petit échantillon. Aucun mécanisme causal propre à la taille ne peut être isolé ici.

## Faux positifs

Les **11/11 FP C6** ont été examinés visuellement par l'assistant sur RGB + contours GT/prédiction + probabilité : **10 ROOF_LIKE_SURFACE**, **1 ROAD (FP259, passage piéton)** ; BARE_SOIL/SHADOW/INDUSTRIAL/OTHER =0. Les catégories sont des observations visuelles, pas des labels humains validés. FP103/106 montrent des toits fusionnés ; plusieurs autres sont des fragments ou désaccords d'emprise. Certains toits apparents sans GT apparié restent sémantiquement incertains : un FP objet n'est pas nécessairement du sol mal classé. Les CSV conservent les observations par ID. La correction future doit traiter les fusions, contours et routes autant que les omissions.

## Préparation de la suite, sans l'exécuter

Décision : **ACTIVE_LEARNING_PLUS_NON_GOLD_CALIBRATION**. Priorité aux petits toits, faibles contrastes, densité, ombres et bâtiments adjacents ; conserver aussi de vrais négatifs routiers.

`14A9A_non_gold_review_shortlist.json` sélectionne cinq images **déjà TRAIN** pour revue ciblée : 14A2_2024_02, 14A2_2024_06, 14A2_2024_10, 14A2_2024_13, 14A2_2025_02. Le garde anti-GOLD a vérifié IDs, hashes et emprises. Ce sont des supports de correction de TRAIN existant, **pas une expansion indépendante**, et ils ne doivent pas devenir DEV/VAL. Les contextes visés restent à confirmer par le réviseur humain. Aucune préannotation nouvelle n'a été lancée ; à l'étape suivante, générer C6 dans des copies et corriger uniquement FN, FP, fusions et frontières, sans écraser les anciens GT.

Le pool assisté 14A.7 existant reste `VALIDATION_LOCKED_FOR_C3_C6` : il n'est pas réaffecté au TRAIN. Pour calibrer, sélectionner d'autres images **DEV non-GOLD**, spatialement disjointes du TRAIN/VAL/TEST protégé ; figer leurs affectations avant tout essai. Figer ensuite paramètres sur DEV avant une future évaluation GOLD. Ni nouvelles valeurs de seuil/aire/morphologie, ni sweep, ni gain attendu ne sont déduits de cette étape.

## Livrables et contrôles exécutés

Dans `qa/14A9A_small_building_diagnostic/` : quatre CSV demandés, table complète des 165 objets, règles, synthèse et preuve SHA256 ; 16 GeoTIFF d'états ; quatre planches de pipeline ; 38 fiches de petits bâtiments regroupées en sept planches inspectées ; 11 fiches FP et leur planche inspectée ; shortlist non-GOLD et RGB de revue. Les `building_id` originaux et `gt_id` stables permettent de retrouver chaque feature. Le masque individuel utilise les centres de pixels, exactement comme 14A.8 ; aucun resampling.

Exécution Python QGIS 3.40.14 terminée sans erreur. Contrôles : 165 objets, 38 SMALL, somme des six stades=38, appariements finaux identiques à 14A.8, masques historiques identiques, grille exacte et valeurs finies/binaires selon l'état, onze FP couverts, sources protégées inchangées. Le lancement initial avec `-P` a révélé uniquement un import local absent ; chemin du dossier scripts explicité avant l'exécution complète. Aucun test général backend/frontend nécessaire pour ces sorties diagnostiques isolées.

## Statut final

'''+end+'\n'
    (ROOT/'docs/ETAPE_14A9A_SMALL_BUILDING_FAILURE_DIAGNOSTIC.md').write_text(report,encoding='utf-8')
    print(end)
if __name__=='__main__':main()
