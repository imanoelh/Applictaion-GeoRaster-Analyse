"""Finalize the single experimental hybrid cycle with immutable-source checks."""
from pathlib import Path
import sys,json,csv
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A11_hybrid import ROOT,BASE,OUT,sha,dump,csvwrite
from prepare_14A9B_datasets import GOLD
from PIL import Image,ImageDraw,ImageFont
import numpy as np

def reconcile_dev_loss():
 # Preserve the raw diagnostic if an already-running worker used uint8 unary
 # negation. Recompute from saved probabilities, never rerun training or GOLD.
 path=OUT/'models/training_history.json';history=json.loads(path.read_text());p=json.loads((OUT/'protocol.json').read_text());records=[r for r in p['records'] if r['split']=='DEV_CALIBRATION'];best=float('inf');stale=0;repaired=False
 for ck in history:
  losses=[]
  for r in records:
   pid=r['patch_id']
   with np.load(OUT/'dev'/(f"epoch{ck['epoch']}__"+pid+'.npz')) as f:q=np.clip(f['probability'],1e-6,1-1e-6)
   with np.load(OUT/'dev'/(pid+'.npz')) as f:y=f['mask'].astype('float32');w=f['weight']
   losses.append(float(((-y*np.log(q)-(1-y)*np.log(1-q))*w).sum()/max(1,w.sum())))
  value=float(np.mean(losses));assert np.isfinite(value) and value>=0
  if abs(value-ck['dev_weighted_bce'])>1e-5:
   ck['runtime_dev_weighted_bce_invalid_uint8']=ck['dev_weighted_bce'];ck['dev_weighted_bce']=value;repaired=True
  stale=0 if value<best-1e-6 else stale+1;best=min(best,value);ck['stale_epochs']=stale
 if repaired:
  assert len(history)==p['training']['epochs']==3
  dump(path,history)
 dump(OUT/'qa/DEV_LOSS_AUDIT.json',dict(verified=True,uint8_diagnostic_corrected=repaired or any('runtime_dev_weighted_bce_invalid_uint8' in ck for ck in history),epochs=len(history),training_schedule_affected=False,reason='patience2 cannot terminate before third epoch; maximum3; final checkpoint uses DEV object F1',training_repeated=False))
 print('DEV_LOSS_AUDIT',history,flush=True)

def main():
 P=json.loads((OUT/'protocol.json').read_text());freeze=json.loads((OUT/'calibration/FROZEN_CANDIDATE.json').read_text());result=json.loads((OUT/'gold_evaluation/FINAL_RESULT.json').read_text());m=result['metrics'];c=json.loads((OUT/'qa/HYBRID_SUMMARY.json').read_text())['counts'];qa=json.loads((OUT/'qa/PSEUDO_TECHNICAL_QA.json').read_text());finalcounts=qa['counts'];history=json.loads((OUT/'models/training_history.json').read_text())
 before=json.loads((OUT/'qa/GOLD_BEFORE.json').read_text());after={str(p.relative_to(ROOT)):sha(p) for p in GOLD.rglob('*') if p.is_file()};assert before==after
 expected=json.loads((BASE/'14A9B_active_learning/qa/GOLD_HASHES_AFTER.json').read_text());assert all(after.get(k)==v for k,v in expected.items());old=BASE/'qa/14A8_model_shootout';oldp=json.loads((old/'14A8_frozen_protocol.json').read_text())
 protected={path:h for s in oldp['models'] for path,h in zip(s['path'].split(';'),s['sha256'].split(';'),strict=True)};protected[P['dist3_path']]=P['dist3_sha256'];oldfreeze=json.loads((BASE/'14A9_auto_pipeline/calibration/FROZEN_CANDIDATE.json').read_text());protected[oldfreeze['checkpoint']]=oldfreeze['checkpoint_sha256']
 protected['backend/data/models/building/experimental/spacenet2-deeplab/best_deeplab.pth']='170c49e1f42737f5a4b3922b9fc58b25b6ba0a7dd7bf00b9186a92ccb84dc555'
 for path,h in protected.items():assert sha(ROOT/path)==h
 for r in P['records']:assert sha(ROOT/r['rgb_path'])==r['rgb_sha256']
 assert sha(OUT/'protocol.json')==(OUT/'protocol.sha256').read_text();assert sha(OUT/'calibration/FROZEN_CANDIDATE.json')==(OUT/'calibration/FROZEN_CANDIDATE.sha256').read_text();assert sha(ROOT/freeze['checkpoint'])==freeze['checkpoint_sha256']
 assert json.loads((OUT/'gold_evaluation/STARTED.json').read_text())['freeze_sha256']==sha(OUT/'calibration/FROZEN_CANDIDATE.json')
 dump(OUT/'qa/GOLD_AFTER.json',after);dump(OUT/'qa/FINAL_INTEGRITY.json',dict(gold_files=len(after),gold_modified=False,previous_model_files=len(protected),previous_models_unchanged=True,rgb_files_unchanged=True,protocol_and_freeze_unchanged=True,production_modified=False,cycles=1,gold_attempts=1))
 b=next(r for r in json.loads((old/'14A8_summary.json').read_text())['ranking'] if r['MODEL']=='MODEL_C6');c7=json.loads((BASE/'14A9_auto_pipeline/gold_evaluation/FINAL_RESULT.json').read_text())['metrics'];d=json.loads((BASE/'14A10_specialized_benchmark/metrics/UNET_DIST3.json').read_text())
 def row(name,x):return dict(MODEL=name,TP=x['TP'],FP=x['FP'],FN=x['FN'],PRECISION=x['object_precision'],RECALL=x['object_recall'],F1=x['object_f1'],SMALL_TP=x['SMALL_TP'],SMALL_RECALL=x['small_recall'],BOUNDARY_F1=x.get('raw_boundary_f1',x.get('boundary_f1')),MERGED=x['MERGED'],FRAGMENTED=x['FRAGMENTED'],CPU_TIME=x.get('cpu_mean_seconds',x.get('cpu_inference_mean')))
 rows=[dict(MODEL='MODEL_C6',TP=b['TP'],FP=b['FP'],FN=b['FN'],PRECISION=b['OBJECT_PRECISION'],RECALL=b['OBJECT_RECALL'],F1=b['OBJECT_F1'],SMALL_TP=b['SMALL_TP'],SMALL_RECALL=b['SMALL_RECALL'],BOUNDARY_F1=b['BOUNDARY_F1'],MERGED=b['MERGED'],FRAGMENTED=b['FRAGMENTED'],CPU_TIME=b['CPU_INFERENCE_MEAN']),row('MODEL_C7_AUTO',c7),row('UNET_DIST3',d),row('MODEL_C8_HYBRID',m)]
 csvwrite(OUT/'14A11_global_comparison.csv',rows)
 font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13);sheet=Image.new('RGB',(4*384,4*410),'white')
 for i,r in enumerate(P['records']):
  im=Image.open(OUT/'qa'/(r['patch_id']+'_HYBRID_OVERLAY.png'));sheet.paste(im.resize((384,384)),((i%4)*384,(i//4)*410+26));ImageDraw.Draw(sheet).text(((i%4)*384+3,(i//4)*410+3),r['patch_id']+' '+('TRAIN' if r['split']=='ACTIVE_LEARNING_TRAIN' else 'DEV'),fill='black',font=font)
 sheet.save(OUT/'qa/14A11_HYBRID_LABELS_CONTACT.png')
 yes=lambda v:'YES' if v else 'NO';staging=result['candidate_ready_for_staging'];nextstep='14A12_STAGING_AND_CPU_OPTIMIZATION' if staging else '14A12_HYBRID_TEACHER_REFINEMENT'
 end=f'''HYBRID TEACHER :
C6 + UNET_DIST3

PSEUDO LABELS TOTAL :
{finalcounts['objects']} (355 TRAIN + 149 DEV)

CONSENSUS :
{finalcounts.get('HIGH_CONFIDENCE_CONSENSUS',0)}

DIST3 ONLY ACCEPTED :
{finalcounts.get('HIGH_CONFIDENCE_DIST3_ONLY',0)}

C6 ONLY ACCEPTED :
{finalcounts.get('HIGH_CONFIDENCE_C6_ONLY',0)}

UNCERTAIN EXCLUDED :
{c['uncertain_excluded']} propositions enseignants

DIST3 FP REJECTED :
{c['dist3_candidates_rejected']} rejets automatiques, FP non confirmes humainement

SMALL BUILDING PSEUDO LABELS :
{c['train_small']+c['dev_small']} (101 TRAIN + 51 DEV)

FRAGMENTS MERGED :
{c.get('fragment_pairs_merged',0)}

NEW MODEL :
MODEL_C8_HYBRID

DEV F1 :
{freeze['dev_metric']['object_f1']:.4f} (accord pseudo-labels, pas GT humaine)

GOLD F1 :
{m['object_f1']:.4f}

GOLD RECALL :
{m['object_recall']:.4f}

GOLD SMALL RECALL :
{m['SMALL_TP']} / 38

GOLD FP :
{m['FP']}

GOLD MISSED :
{m['FN']}

GOLD BOUNDARY F1 :
{m['raw_boundary_f1']:.4f}

C6 F1 :
0.3474

UNET_DIST3 F1 :
0.5672

C8 BETTER THAN C6 :
{yes(m['object_f1']>b['OBJECT_F1'])}

C8 BETTER THAN UNET_DIST3 :
{yes(m['object_f1']>d['object_f1'])}

CANDIDATE READY FOR STAGING :
{yes(staging)}

PRODUCTION MODEL :
MODEL_C

PRODUCTION MODIFIED :
NO

NEXT STEP :
{nextstep}
'''
 base_dev=json.loads((OUT/'calibration/C6_DEV_PSEUDO_BASELINE.json').read_text());fp_dev_limit=max(1.5*base_dev['FP'],base_dev['FP']+5)
 table='| MODEL | TP | FP | FN | Precision | Recall | F1 | Small TP /38 | Boundary F1 | Merge | Fragment | CPU s/patch |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n'
 for r in rows:table+='| '+f"{r['MODEL']} | {r['TP']} | {r['FP']} | {r['FN']} | {r['PRECISION']:.4f} | {r['RECALL']:.4f} | {r['F1']:.4f} | {r['SMALL_TP']} | {r['BOUNDARY_F1']:.4f} | {r['MERGED']} | {r['FRAGMENTED']} | {r['CPU_TIME']:.3f}"+' |\n'
 report=f'''# ETAPE 14A.11 — Hybrid teacher autonomous learning

## Decision

Un seul cycle experimental termine. C8 {'satisfait' if staging else 'ne satisfait pas'} tous les criteres figes de staging. Aucun remplacement production. Etape suivante : `{nextstep}`.

## Donnees et separation

- 12 TRAIN, 4 DEV existants non-GOLD. Les 10 nouveaux patches 14A9B sont completes par 2 RGB industriels historiquement TRAIN (14A2_2024_11 et 14A2_2025_11), sans reutilisation de leurs anciens labels. Ce ne sont pas de nouvelles scenes independantes.
- Overlap spatial TRAIN/DEV/GOLD : 0 ; RGB dupliques : 0. Aucun label humain historique ni GOLD utilise en apprentissage/calibration. Hashes des {len(after)} fichiers GOLD identiques avant/apres et a la reference anterieure.
- TRAIN : 355 objets (101 petits <=50m2, 178 moyens >50–200m2, 76 grands >200m2). DEV : 149 (51/74/24). Ce sont des pseudo-labels, pas une nouvelle verite terrain.
- Tous les masques : grille native 512x512 du RGB, valeurs 0/1, meme CRS/transform/bounds, sans resampling. Les RGB de ce jeu utilisent leur CRS natif ; les GeoJSON et surfaces sont en EPSG:32637. QA 16/16 : validite, non-vide, surfaces, unicite, bounds testes en coordonnees pixel inversees (pas seulement bbox UTM).

## Contrat enseignants et hybride objet

C6 conserve son preprocessing RGB minmax global par patch, seuil0.30, composantes4, minimum479px. DIST3 ONNX CPU utilise RGB/255 puis ImageNet mean/std, quatre fenetres256 sans overlap par patch512, sigmoid des trois sorties mask/distance/boundary, watershed global des seeds distance>0.5 dans mask>=0.5. Une inference retournee par flip horizontal fournit une coherence d'augmentation.

Les labels d'instances DIST3 sont preserves. Consensus : IoU>=0.30 ou intersection/aireDIST3>=0.60. Choix de contour par proxy fixe boundary/compactness/confiance ; conservation des unites DIST3 face a un gros objet C6 fusionne. DIST3 seul : aire>=1m2, compactness>=0.08, aspect<=8, confiance/IoUflip (>=0.8/0.5 ou >=0.95/0.35), score de rejet<0.55. Pas de filtre479px sur ces objets. C6 seul : confiance>=0.85 et DIST3 moyen>=0.05 ; aucun n'a passe.

Regroupement conservateur : contact>=2px, faible frontiere interne, forte confiance, orientation compatible, meme composante C6, continuite de forme. {c.get('fragment_pairs_merged',0)} paires regroupees. Split conditionne a plusieurs cores C6 et une frontiere interne : {c.get('merged_objects_split',0)} cas declenches. Ces operations ne garantissent pas une correction semantique humaine.

Le score `DIST3_FP_REJECTION_SCORE` combine confiance, coherence flip, forme, fraction background C6, texture et contexte route/sol nu du patch. Distances aux routes, probabilites sol nu, classes parking/vegetation : NON DISPONIBLES. Les {c['dist3_candidates_rejected']} rejets ne sont donc pas des FP verifies. {c['uncertain_excluded']} propositions enseignants incertaines exclues (compteur de propositions pouvant se recouvrir, pas de batiments uniques). Les objets rejetes ne deviennent pas automatiquement du negatif ; seul le background concordant C6/DIST3/flip<0.05 est supervise.

254 consensus et253 DIST3 seuls ont ete appliques avant separation des contacts ; 3 consensus minuscules disparaissent lors des gaps, d'ou 251+253=504 objets finaux. Les gaps entre instances voisines sont supervises background (poids1), les contours externes ne sont pas erodes. Les pixels incertains ont poids0 : {finalcounts['ignored_pixels']}. Les gaps sont une hypothese de separation, pas une GT humaine.

## Entrainement et calibration

C8 initialise strictement C6, backbone+classifier entrainables, aux gele et statistiques BN gelees, AdamW (2e-5 backbone,1e-4 head,weight_decay1e-4), BCE+Dice ponderees, clipping1, batch1 natif512. Poids objets A1/B0.6/C0.75, facteur aire clip(200/px,0.25,4), negatives0.7. Ordre par contexte et exemples petits/moyens/grands reponderes ; pas de garantie d'equilibre semantique parfait sur ce petit jeu.

{len(history)} epochs, seed1411 ; flips/rotations90/luminosite0.9–1.1. Patience2, maximum3. Le controle `qa/DEV_LOSS_AUDIT.json` recalcule la BCE depuis les predictions sauvegardees en float : le diagnostic uint8 d'un worker deja lance est conserve dans l'historique, corrige avant selection ; aucun effet sur le nombre d'epochs (patience2 ne pouvait arreter avant la troisieme), aucun reentrainement. Selection finale exclusivement par metriques objet DEV.

Grille DEV : seuils0.20/0.30/0.50, minimum4/32/128/479, NONE/OPEN3 sur chaque checkpoint. Contraintes : petits TP>C6, FP<=max(1.5*FP_C6,FP_C6+5), BoundaryF1 final>=95% C6. Labels DEV hybrides correles aux enseignants : le score est un accord de pseudo-labels, pas une mesure independante de precision reelle.

Freeze : epoch{freeze['epoch']}, seuil{freeze['threshold']}, minimum{freeze['min_component']}, {freeze['morphology']}, connexite4. DEV F1={freeze['dev_metric']['object_f1']:.6f}, contraintes={'PASS' if freeze['dev_constraints_satisfied'] else 'FAIL'}. DEV C6 : F1={base_dev['object_f1']:.6f}, petitsTP={base_dev['SMALL_TP']}, FP={base_dev['FP']}. C8 : petitsTP={freeze['dev_metric']['SMALL_TP']}, FP={freeze['dev_metric']['FP']} (plafond={fp_dev_limit:g}), BoundaryF1 final={freeze['dev_metric']['final_boundary_f1']:.6f} (minimum={.95*base_dev['final_boundary_f1']:.6f}). Si aucune combinaison n'est admissible, meilleur F1 de repli fige et gate DEV refusee. SHA checkpoint `{freeze['checkpoint_sha256']}`. Freeze SHA `{sha(OUT/'calibration/FROZEN_CANDIDATE.json')}`.

## Evaluation finale GOLD

Un seul passage C8 apres freeze, quatre patches/165 GT, petits38. Pas de generation hybride sur GOLD et pas de reparametrage apres resultat. Matching IoU>=0.30, maximum cardinalite puis IoU, strictement un-a-un ; chaque GT apparait une fois dans le CSV de matching. Merge/fragmentation : memes seuils d'intersection descriptifs que14A8/14A10. Les comparaisons C6/C7/DIST3 viennent des resultats caches, aucune nouvelle inference baseline.

{table}

BoundaryF1 tableau : micro des comptes contours bruts a tolerance1px, conforme aux baselines ; objet : masque final apres postprocessing. Pixel brut C8 IoU={m['raw_pixel_iou']:.6f}, Dice={m['raw_dice']:.6f}. Medium recall={m['MEDIUM_TP']}/{m['MEDIUM_GT']}, large={m['LARGE_TP']}/{m['LARGE_GT']}. CPU : PyTorch4threads inference moyenne par512 apres warmup, hors chargement ; postprocessing={m['cpu_postprocessing_mean_seconds']:.3f}s. Comparaison des temps descriptive (engines/dates differents), pas un benchmark intercale.

Criteres minimum declares avant entrainement : F1>0.3491, recall>0.2242424, petitTP>=1, missed<128, FP<=64, BF1>=0.2687692, CPU<=12.1924s, contraintesDEV. Resultat : `{json.dumps(result['gates'],ensure_ascii=False)}`. Les objectifs ambitieux ne sont pas des resultats forces.

### Lecture du resultat

C8 progresse face a C6/C7 en F1, recall et petits TP, avec moins de FP que DIST3. Il ne recupere toutefois que {m['SMALL_TP']}/38 petits contre14/38 pour DIST3, et presente {m['MERGED']} objets fusionnes contre14 pour C6 et9 pour DIST3. L'etudiant semantique n'a pas conserve la separation des instances de l'enseignant. C'est un constat des sorties finales ; son origine precise (labels, loss, architecture ou duree d'apprentissage) n'a pas ete isolee causalement. Le gain de F1 ne suffit pas a valider le staging : les contraintes DEV restent refusees. Les mentions « BETTER THAN » du bloc final comparent le F1 objet, pas toutes les dimensions de qualite.

## Integrite, limites et artefacts

{len(protected)} fichiers de modeles historiques/enseignants compares a leurs SHA precedents ; tous identiques. Les RGB sources et protocoles/freeze sont intacts. Aucun fichier backend/app, frontend, registry ou production modifie par cette etape. Aucune promotion automatique ni export ONNX C8. Le teacher DIST3 a une licence CC-BY4 et une reserve d'attribution archivee en14A10 : revue necessaire avant toute diffusion/staging.

Ce resultat concerne quatre patches GOLD fixes : utilisation repetee de ce GOLD dans les experiences historiques, generalisation externe non demontree. Aucune annotation humaine nouvelle ne confirme les pseudo-labels ni les rejets. Cette limite demeure meme si les scores augmentent.

Artefacts sous `backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A11_hybrid_pipeline/` : `protocol.json`, `hybrid_teacher/` (objets, decisions, masques, actions), `small_candidates/`, `hard_negatives/`, `qa/` (QA, hashes, contact sheet), `models/` (C8 epochs + historique), `calibration/` (grille et freeze), `gold_evaluation/` (matching, metriques, overlays, contact sheet), `14A11_global_comparison.csv`.

## Statut final

{end}'''
 (ROOT/'docs/ETAPE_14A11_HYBRID_TEACHER_AUTONOMOUS_LEARNING.md').write_text(report,encoding='utf-8');(OUT/'FINAL_STATUS.txt').write_text(end,encoding='utf-8');print(end,flush=True)
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='devloss':reconcile_dev_loss()
 else:main()
