"""Report a completed single cycle and verify protected artifacts."""
from pathlib import Path
import sys,json,csv
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A9_auto import ROOT,BASE,AL,DEV,GOLD,OUT,sha,dump,csvwrite
from evaluate_14A9_auto import P,filtered
from evaluate_14A8_shootout import objects,draw_geom
from osgeo import gdal
from shapely import wkb
from pyproj import Transformer
from PIL import Image,ImageDraw,ImageFont
import numpy as np

def main():
 result=json.loads((OUT/'gold_evaluation/FINAL_RESULT.json').read_text());freeze=json.loads((OUT/'calibration/FROZEN_CANDIDATE.json').read_text());cons=json.loads((OUT/'qa/CONSENSUS_SUMMARY.json').read_text());history=json.loads((OUT/'models/training_history.json').read_text());runtime=json.loads((OUT/'qa/TEACHER_RUNTIME.json').read_text());m=result['metrics'];c=cons['counts']
 before=json.loads((OUT/'qa/GOLD_BEFORE.json').read_text());after={str(p.relative_to(ROOT)):sha(p) for p in GOLD.rglob('*') if p.is_file()};assert before==after
 expected=json.loads((AL/'qa/GOLD_HASHES_AFTER.json').read_text());assert all(after.get(p)==h for p,h in expected.items())
 for s in P['teachers']:assert sha(ROOT/s['path'])==s['sha256']
 for r in P['records']:assert sha(ROOT/r['rgb_path'])==r['rgb_sha256']
 assert sha(OUT/'calibration/FROZEN_CANDIDATE.json')==(OUT/'calibration/FROZEN_CANDIDATE.sha256').read_text();assert sha(ROOT/freeze['checkpoint'])==freeze['checkpoint_sha256']
 dump(OUT/'qa/GOLD_AFTER.json',after);dump(OUT/'qa/FINAL_INTEGRITY.json',dict(gold_modified=False,gold_files=len(after),teacher_weights_unchanged=True,rgb_unchanged=True,freeze_unchanged=True,production_modified=False,cycles=1))
 old=BASE/'qa/14A8_model_shootout';oldsummary=json.loads((old/'14A8_summary.json').read_text());baseline=next(r for r in oldsummary['ranking'] if r['MODEL']=='MODEL_C6');records=json.loads((old/'14A8_frozen_protocol.json').read_text())['patches']
 audit=list(csv.DictReader((old/'14A8_model_availability.csv').open(encoding='utf-8-sig')))
 for a in audit:
  a['CYCLE_ROLE']='ACTIVE_TEACHER' if a['MODEL'] in ['MODEL_C','MODEL_C3','MODEL_C6','MODEL_D'] else 'DERIVED_NOT_INDEPENDENT_VOTE' if a['MODEL']=='MODEL_E' else 'CORRELATED_WEAKER_HISTORICAL_NOT_SELECTED' if a['MODEL'] in ['MODEL_C2','MODEL_C4','MODEL_C5'] else 'HISTORICAL_RUNTIME_OR_SEMANTICS_EXCLUSION'
 csvwrite(OUT/'qa/LOCAL_MODEL_AUDIT.csv',audit)
 compare=[dict(model='MODEL_C6_CACHED_14A8',object_f1=baseline['OBJECT_F1'],recall=baseline['OBJECT_RECALL'],FP=baseline['FP'],FN=baseline['FN'],small_recall=baseline['SMALL_RECALL'],raw_boundary_f1=baseline['BOUNDARY_F1'],raw_pixel_iou=baseline['PIXEL_IOU'],cpu_mean_seconds=baseline['CPU_INFERENCE_MEAN']),dict(model='MODEL_C7_AUTO',object_f1=m['object_f1'],recall=m['object_recall'],FP=m['FP'],FN=m['FN'],small_recall=m['small_recall'],raw_boundary_f1=m['raw_boundary_f1'],raw_pixel_iou=m['raw_pixel_iou'],cpu_mean_seconds=m['cpu_mean_seconds'])];csvwrite(OUT/'gold_evaluation/C6_VS_C7.csv',compare)
 font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);sheet=Image.new('RGB',(3*512,4*545),'white');gt={r['patch_id']:[] for r in records};ds=gdal.OpenEx(str(ROOT/records[0]['gt_path']),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES'])
 for f in ds.GetLayerByName('buildings_gt'):gt[f['patch_id']].append(wkb.loads(bytes(f.GetGeometryRef().ExportToWkb())))
 ds=None
 for i,r in enumerate(records):
  pid=r['patch_id'];rgbds=gdal.Open(str(ROOT/r['rgb_path']));rgb=np.moveaxis(rgbds.ReadAsArray()[:3],0,-1);tx=Transformer.from_crs('EPSG:32637',rgbds.GetProjection(),always_xy=True);inv=gdal.InvGeoTransform(rgbds.GetGeoTransform())
  with np.load(OUT/'gold_evaluation'/(pid+'.npz')) as f:prob=f['probability']
  _,pred,_=objects(filtered(prob,freeze),ROOT/r['rgb_path'],dict(connectivity=4,min_component_pixels=freeze['min_component']));im=Image.fromarray(rgb);d=ImageDraw.Draw(im)
  for g in gt[pid]:draw_geom(d,g,tx,inv,'lime',1)
  for q in pred:draw_geom(d,q['geometry'],tx,inv,'magenta',1)
  im.save(OUT/'gold_evaluation'/(pid+'_C7_overlay.png'))
  for j,(title,panel) in enumerate([('RGB '+r['scene_type'],Image.fromarray(rgb)),('C6 cached / GT green',Image.open(old/'overlays'/('MODEL_C6__'+pid+'.png'))),('C7 frozen / GT green',im)]):
   sheet.paste(panel,(j*512,i*545+30));ImageDraw.Draw(sheet).text((j*512+3,i*545+4),title,fill='black',font=font)
 sheet.save(OUT/'gold_evaluation/C6_C7_FINAL_CONTACT.png')
 accepted=result['decision']=='CANDIDATE_ACCEPTED_FOR_STAGING';nextstep='STAGING_NEW_CANDIDATE' if accepted else 'AUTONOMOUS_DATA_EXPANSION'
 end=f'''GOLD MANUAL REANNOTATION REQUIRED :
NO

TRAIN MANUAL ANNOTATION REQUIRED :
NO

AUTOMATIC TEACHERS :
MODEL_C, MODEL_C3, MODEL_C6, MODEL_D (+ D horizontal-flip consistency)

AUTO TRAIN OBJECTS :
{c.get('auto_train_objects',0)}

AUTO DEV OBJECTS :
{c.get('auto_dev_objects',0)}

SMALL BUILDING PSEUDO-LABELS :
{c.get('small',0)} (TRAIN + DEV)

HARD NEGATIVES :
{cons['hard_negative_patches']} patches TRAIN de contexte route/sol nu, consensus-background uniquement

NEW MODEL :
MODEL_C7_AUTO (epoch {freeze['epoch']})

DEV OBJECT F1 :
{freeze['dev_metric']['object_f1']:.4f} (pseudo-labels, pas GT humaine)

GOLD OBJECT F1 :
{m['object_f1']:.4f}

GOLD OBJECT RECALL :
{m['object_recall']:.4f}

GOLD SMALL RECALL :
{m['small_recall']:.4f} ({m['SMALL_TP']} / {m['SMALL_GT']})

GOLD FP :
{m['FP']}

GOLD MISSED :
{m['FN']}

BASELINE C6 F1 :
0.3474

BASELINE C6 RECALL :
0.2242

AUTOMATIC PIPELINE :
PASS

CANDIDATE BETTER THAN C6 :
{'YES' if accepted else 'NO'}

PRODUCTION MODEL :
MODEL_C

PRODUCTION MODIFIED :
NO

NEXT STEP :
{nextstep}'''
 gate_table='\n'.join('| '+k+' | '+('PASS' if v else 'FAIL')+' |' for k,v in result['gates'].items())
 report=f'''# 14A.9-AUTO — Cycle autonome expérimental unique

## Décision

**{result['decision']}**. Le pipeline a exécuté un seul cycle complet. PASS signifie exécution et traçabilité, pas qualité suffisante pour production. MODEL_C reste production ; aucun registry, backend ou frontend modifié.

Sur ce cycle, le gain de F1 provient d'un seul FP en moins (10 contre 11), sans aucun TP supplémentaire : 37 TP, 128 FN, 0/38 SMALL comme C6. Il ne répond donc pas à l'objectif de récupération des petits bâtiments. Sur DEV pseudo, le meilleur F1 passe de 0,1928 pour C6 à 0,2012 pour le repli C7 choisi, mais les petits objets appariés passent de 3/90 à 2/90 ; les contraintes DEV ne sont pas satisfaites. Les 72 micro-fragments et les propositions souvent partielles montrent une limite des pseudo-labels de ce cycle. Leur responsabilité causale exacte n'est pas isolée par une ablation : ne pas attribuer cet échec à un unique paramètre ni annoncer qu'un entraînement plus long suffirait. La prochaine génération devra améliorer les données non-GOLD et la qualité des pseudo-objets ; aucune nouvelle génération n'est lancée ici.

## Protocole et données

`protocol.json` et son SHA256 ont été écrits avant les prédictions et l'entraînement. Quatorze RGB nouveaux de 14A.9B sont réutilisés automatiquement avec leur affectation fixe : 10 TRAIN, 4 DEV, emprises séparées de plus de 20 m entre elles et des crops historiques protégés. Aucun GT prétendument humain de 14A.9C n'est utilisé. Pas de réaffectation des anciens TRAIN/VAL/TEST ; overlap TRAIN/DEV/GOLD=0. Le même parent Maxar reste partagé : validation spatiale interne, pas validation d'acquisition externe.

La sélection de ce cycle est bornée au pool éligible de 14 fenêtres déjà préparées ; ce n'est pas une exploration exhaustive des 208 fenêtres de screening. Les indicateurs de désaccord, proximité du seuil et petites composantes sont archivés par les cartes de consensus/mining. Le lanceur `scripts/run_14A9_auto_cycle.py` enchaîne les étapes sans intervention, refuse les redémarrages silencieux d'un entraînement partiel et une seconde tentative GOLD. Le premier lanceur PowerShell a été refusé par la politique locale ; aucun changement de politique système n'a été effectué. Aucun cycle suivant n'est lancé. Les générations futures doivent utiliser un nouvel espace d'artefacts/protocole et de nouvelles données non-GOLD ; pas de boucle ouverte.

## Audit des teachers

C, C3, C6 et D ont réellement chargé et prédit les 14 RGB. C/C3/D utilisent ONNX CPU ; C6 PyTorch CPU ; 4 threads. E est dérivé de C+D, donc pas de vote indépendant. C2/C4/C5 sont reproductibles historiquement mais non sélectionnés comme votes supplémentaires d'une famille corrélée, plus faible lors du benchmark existant. F/F2 : transformers indisponible dans le runtime stable ; A/H : SMP absent ; G : sémantique des canaux non résolue. Aucun téléchargement ou installation. L'audit local des 13 modèles et les contrats réutilisés sont conservés dans qa/.

Les trois DeepLab sont **corrélés** : 3 votes ne sont pas trois preuves indépendantes. Le soutien de D est obligatoire pour le tier A. Un fort consensus n'est pas une preuve de vérité, en particulier lorsque tous les teachers manquent le même petit toit.

## Pseudo-labels et petits objets

Tier A : au moins 3 votes, D>=0,50, moyenne>=0,60, différence D/flip<=0,15. Tier B : D>=0,95 et D-flip>=0,90 hors A. Tier C : incertain, poids nul. Tier D : tous les teachers et D-flip<=0,05, proxy background. Poids A=1, B=0,35, C=0, D=0,5. Aucun filtre 479 px pour créer les positifs pseudo : composantes à partir de 1 pixel, géométrie valide et aire tracée.

**{c.get('auto_train_objects',0)} objets TRAIN**, **{c.get('auto_dev_objects',0)} objets DEV**, **{c.get('small',0)} petites propositions <=50 m²** au total. Les vecteurs GeoJSON conservent source, modèle, votes, confiance, accord de frontière, aire, tier, méthode et usage TRAIN. Masques et poids sont enregistrés séparément ; ce ne sont pas des GT humaines. Le mining conserve aussi les réponses C6 0,10–0,30 et les composantes pré-filtre <479 comme candidats incertains, sans les injecter automatiquement comme positifs.

La QA technique des 404 objets confirme géométries valides, OOB=0 sur la grille pixel native, doublons=0, masques binaires et grilles identiques aux RGB. **72 objets font moins de 4 pixels** : certaines petites propositions sont des fragments, pas des bâtiments complets. L'inspection des overlays AL04/AL09/DEV11 l'illustre. Il ne faut pas annoncer 303 petits bâtiments réels récupérés. Les 82 823 pixels A et 109 065 pixels B donnent environ 68 % de poids positif au tier A après pondération ; les 760 192 pixels incertains sont ignorés. Ces contrôles ne prouvent pas la justesse sémantique des pseudo-labels.

Les négatifs sont des **proxies de consensus-background** : aucun algorithme de segmentation sémantique routes/sol/ombres n'a été inventé. Deux contextes TRAIN route/sol nu sont inclus ; leur faible réponse multi-teacher apporte des pixels négatifs pondérés. Les désaccords roof-like restent ignorés, jamais déclarés vrais négatifs sur cette seule base. Des bâtiments manqués par tous les modèles peuvent malgré tout contaminer le background : limite importante du pseudo-supervisé.

## Apprentissage réel et sélection DEV

Trois epochs CPU réellement effectuées depuis le checkpoint C6 intact. Seuls classifier et backbone.layer4 entraînables, BatchNorm en mode évaluation ; taille native 512, batch1, AdamW lr1e-5, BCE+Dice pondérées. Flips, rotations90 et luminosité0,9–1,1 ; pas de resize. Cohérence par flip du teacher D avant pondération, pas de promesse de consistency loss étudiant non implémentée. Trois checkpoints distincts et leurs prédictions DEV sont conservés.

Calibration **DEV uniquement** : 3 epochs × seuils [0,20;0,30;0,50] × min_component [4;64;128;479] × morphologie [NONE;OPEN3] = **72 configurations**. Object matching un-à-un maximal à IoU>=0,30. Objectif Object F1 avec rappel small amélioré d'au moins une détection DEV, FP<=max(1,5×baseline,baseline+3), Boundary F1 final>=95% baseline. Si aucune configuration admissible, le meilleur F1 est quand même figé pour documenter le cycle, mais le gate DEV reste FAILED et interdit le staging.

Sélection : epoch **{freeze['epoch']}**, seuil **{freeze['threshold']}**, minimum **{freeze['min_component']} px**, morphologie **{freeze['morphology']}**, contraintes DEV **{freeze['dev_constraints_satisfied']}**. F1 DEV **{freeze['dev_metric']['object_f1']:.4f}**. **Le DEV est pseudo-labellisé : ce score mesure l'accord avec l'ensemble, pas une précision humaine et pas une preuve de généralisation.** Le biais du teacher et l'initialisation C6 imposent cette réserve.

Checkpoint, prétraitement et postprocessing sont figés dans `FROZEN_CANDIDATE.json` avec SHA256 **avant** de lire les prédictions GOLD du candidat. Une seule inférence par patch GOLD, sans TTA, avec un warmup synthétique exclu du temps. Aucun retuning après GOLD.

## GOLD final humain — comparaison stricte

| Mesure | C6 historique | C7 AUTO figé |
|---|---:|---:|
| Object F1 | {baseline['OBJECT_F1']:.4f} | {m['object_f1']:.4f} |
| Object Precision | {baseline['OBJECT_PRECISION']:.4f} | {m['object_precision']:.4f} |
| Object Recall | {baseline['OBJECT_RECALL']:.4f} | {m['object_recall']:.4f} |
| TP / FP / FN | {baseline['TP']} / {baseline['FP']} / {baseline['FN']} | {m['TP']} / {m['FP']} / {m['FN']} |
| Small recall | 0/38 | {m['SMALL_TP']}/{m['SMALL_GT']} |
| Medium recall >50–200 m² | — | {m['MEDIUM_TP']}/{m['MEDIUM_GT']} |
| Large recall >200 m² | — | {m['LARGE_TP']}/{m['LARGE_GT']} |
| Boundary F1 raw, micro | {baseline['BOUNDARY_F1']:.4f} | {m['raw_boundary_f1']:.4f} |
| Pixel IoU raw | {baseline['PIXEL_IOU']:.4f} | {m['raw_pixel_iou']:.4f} |
| Dice raw | {baseline['DICE']:.4f} | {m['raw_dice']:.4f} |
| Merged / Fragmented | {baseline['MERGED']} / {baseline['FRAGMENTED']} | {m['MERGED']} / {m['FRAGMENTED']} |
| CPU inference moyenne s/tile | {baseline['CPU_INFERENCE_MEAN']:.3f} | {m['cpu_mean_seconds']:.3f} |

Les objets utilisent le masque final après morphologie/filtre, comme 14A.8. Pour comparaison historique, Pixel/Boundary raw utilisent le masque au seuil avant filtre ; C7 fournit aussi les métriques finales séparées (IoU={m['pixel_iou']:.4f}, Dice={m['dice']:.4f}, Boundary macro={m['final_boundary_f1']:.4f}). Le temps C6 est archivé, pas une remesure simultanée ; charge CPU/cache peuvent varier. Aucune conclusion de vitesse fine sur cette seule comparaison.

## Gates préenregistrés

F1 et recall strictement supérieurs à C6 ; FN<128 ; small recall>=0,10 (au moins 4/38) ; FP<=17 ; Boundary raw>=95% de 0,282915 ; CPU<=12,192 s/tile ; contraintes DEV satisfaites.

| Gate | Résultat |
|---|---|
{gate_table}

La décision est mécanique : tous les gates doivent passer. Aucun assouplissement après consultation du GOLD. Un échec ne déclenche ni nouvel entraînement ni nouvelle grille sur le GOLD. Le GOLD a déjà servi à plusieurs étapes historiques : référence interne fixe, pas nouveau test externe vierge.

## Intégrité et sorties

{len(after)} fichiers GOLD SHA256 avant/après identiques. Les quatre poids teachers, les 14 RGB et le fichier freeze sont inchangés. Toutes les sorties sont dans `14A9_auto_pipeline/` ; aucun modèle expérimental précédent écrasé. Les poids C7 restent dans models/ et ne sont enregistrés dans aucun registry production. Les planches finales montrent RGB, C6 archivé et C7 figé avec les mêmes GT, sans sélection d'exemples pour ajuster les paramètres.

## Statut final

'''+end+'\n'
 (ROOT/'docs/ETAPE_14A9_AUTO_AUTONOMOUS_BUILDING_PIPELINE.md').write_text(report,encoding='utf-8');print(end)
if __name__=='__main__':main()
