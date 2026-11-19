"""Validate matching/integrity and report fixed specialized-model benchmarks."""
from pathlib import Path
import sys,json,csv
from collections import Counter,defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parent))
from discover_14A10_models import ROOT,OUT
from prepare_14A9B_datasets import BASE,GOLD,sha,dump,csvwrite
from evaluate_14A8_shootout import matrices,matching
from osgeo import gdal
from shapely import wkb
from shapely.geometry import shape
from PIL import Image,ImageDraw,ImageFont
import numpy as np
def csvread(p):
 with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def main():
 P=json.loads((OUT/'protocol.json').read_text());assert sha(OUT/'protocol.json')==(OUT/'protocol.sha256').read_text();before=json.loads((OUT/'qa/GOLD_BEFORE.json').read_text());after={str(p.relative_to(ROOT)):sha(p) for p in GOLD.rglob('*') if p.is_file()};assert before==after
 for s in P['models']:assert sha(ROOT/s['path'])==s['sha256']
 results=[json.loads(p.read_text()) for p in sorted((OUT/'metrics').glob('*.json'))];assert len(results)==3
 baseline=json.loads((BASE/'qa/14A8_model_shootout/14A8_summary.json').read_text())['ranking'][0];assert baseline['MODEL']=='MODEL_C6'
 c6matched={(r['PATCH'],int(r['GT_ID'])) for r in csvread(BASE/'qa/14A8_model_shootout/14A8_gt_object_matching.csv') if r['MODEL']=='MODEL_C6' and r['MATCHED_030']=='True'}
 gts=defaultdict(list);ds=gdal.OpenEx(str(ROOT/P['gold_patches'][0]['gt_path']),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES'])
 for f in ds.GetLayerByName('buildings_gt'):gts[f['patch_id']].append(dict(fid=f.GetFID(),geometry=wkb.loads(bytes(f.GetGeometryRef().ExportToWkb()))))
 ds=None;sanity=[];sensitivity=[]
 manifest={r['patch_id']:r for r in csvread(GOLD/'manifest/14A7_GOLD_SET_manifest.csv')}
 for p in P['gold_patches']:
  r=gdal.Open(str(ROOT/p['rgb_path']))
  with np.load(BASE/'qa/14A8_model_shootout/inputs'/(p['patch_id']+'.npz')) as f:
   assert np.array_equal(f['rgb'],r.ReadAsArray()[:3]);target=gdal.Open(str(ROOT/manifest[p['patch_id']]['mask_path'])).ReadAsArray();assert np.array_equal(f['gt'].astype(bool),target.astype(bool))
 for m in results:
  mid=m['model'];rows=csvread(OUT/'metrics'/(mid+'_matching.csv'));assert len(rows)==165 and len({(r['patch_id'],r['gt_id']) for r in rows})==165
  matched_rows=[r for r in rows if r['matched']=='True'];assert len(matched_rows)==m['TP'];assert len({(r['patch_id'],r['matched_prediction']) for r in matched_rows})==m['TP']
  new={(r['patch_id'],int(r['gt_id'])) for r in matched_rows}-c6matched;m['new_gt_matches_vs_c6']=len(new);m['lost_c6_matches']=len(c6matched-{(r['patch_id'],int(r['gt_id'])) for r in matched_rows});m['small_new_matches_vs_c6']=sum((r['patch_id'],int(r['gt_id'])) in new and float(r['area_m2'])<=50 for r in matched_rows)
  ts=Counter()
  for p in P['gold_patches']:
   pid=p['patch_id'];data=json.loads((OUT/'predictions'/mid/(pid+'_instances.geojson')).read_text());pred=[dict(label=f['properties']['prediction_id'],geometry=shape(f['geometry'])) for f in data['features']];assert all(q['geometry'].is_valid and q['geometry'].area>0 for q in pred)
   labels=gdal.Open(str(OUT/'predictions'/mid/(pid+'_instances.tif'))).ReadAsArray();assert len(np.unique(labels[labels>0]))==len(pred)
   mat,_=matrices(gts[pid],pred)
   for threshold in [.3,.5,.7]:ts[str(threshold)]+=len(matching(mat,threshold))
   for row in [r for r in matched_rows if r['patch_id']==pid]:
    i=next(i for i,g in enumerate(gts[pid]) if g['fid']==int(row['gt_id']));j=next(j for j,q in enumerate(pred) if q['label']==int(row['matched_prediction']));assert mat[i,j]>=.3
  assert ts['0.3']==m['TP']
  for threshold in [.3,.5,.7]:
   tp=ts[str(threshold)];sensitivity.append(dict(model=mid,iou_matching_threshold=threshold,TP=tp,FP=m['PRED']-tp,FN=165-tp,F1=2*tp/(165+m['PRED']),note='Sensitivity of scoring only; never changes frozen predictions'))
  sanity.append(dict(model=mid,gt_rows=165,one_to_one=True,matched_pairs_iou_verified=True,unique_prediction_ids=True,source_rgb_and_gt_masks_match_archives=True))
 csvwrite(OUT/'metrics/14A10_object_iou_sensitivity.csv',sensitivity);dump(OUT/'qa/MATCHING_SANITY.json',sanity)
 results.sort(key=lambda m:(-m['object_f1'],-m['object_recall']));best=results[0];teacher=any(m['new_gt_matches_vs_c6']>0 and m['SMALL_TP']>0 for m in results);better=best['object_f1']>.3491
 dump(OUT/'qa/GOLD_AFTER.json',after);dump(OUT/'qa/FINAL_INTEGRITY.json',dict(gold_files=len(after),gold_modified=False,model_files_unchanged=True,protocol_unchanged=True,training=False,gold_calibration=False,production_modified=False));dump(OUT/'metrics/FINAL_RANKING.json',dict(models=results,best=best['model'],new_specialized_teacher_found=teacher,new_model_better_than_c7=better))
 csvwrite(OUT/'metrics/14A10_gold_comparison.csv',results)
 # Audit public offerings, separating unretained architectures from retained smoke statuses.
 rows=[
 ['UNET_DIST3','https://huggingface.co/nilsho01/unet-effb4-dist3-buildings','U-Net / EfficientNet-B4 dist3','building footprint separation','HOT VHR filtered pool (card; config provenance archived)','256 native; four tiles / GOLD patch','INSTANCE_WATERSHED','YES mask/distance/boundary','YES','CC-BY-4.0; attribution review outstanding in card','YES','YES_MEASURED','77686098 bytes','READY'],
 ['DINO_FAST','https://huggingface.co/LundAISociety/hot-models','DINOv3 ViT-S six-block distilled / light decoder','building instances','HOT-derived v0.4.1','raw RGB NHWC; output512','INSTANCE_FLOW','YES interior/border/vector','YES','Apache-2.0 weights card; backbone terms need review','YES','FORWARD_PASS','47083536 bytes','INCOMPATIBLE_OUTPUT_FLOW_CONTRACT'],
 ['SEGFORMER_F','https://huggingface.co/Abhatta7/building-footprint-segmentation','SegFormer-B0 / MiT-B0','binary building footprints','SpaceNet2 Paris','512; logits128 upsampled','SEMANTIC','NO_EXPLICIT_INSTANCE_HEAD','YES_LOCAL_HASH_PINNED','MIT card','NO_LOCAL_EXPORT','YES_MEASURED','14948025 bytes','READY_HISTORICAL_WEIGHTS_RUNTIME_RESTORED'],
 ['DINO_S_SEMANTIC','https://huggingface.co/geobase/dinov3s-buildings','DINOv3-S / UperNet','building footprints, semantic adapter','HOT VHR','256 stride192; native512 mosaic','SEMANTIC_ADAPTER','HEADS_PRESENT_NOT_USED_FOR_SEPARATION','YES_LOCAL_HASH_MATCHES_PUBLIC','CC-BY-4.0 mirror; Apache upstream claim; backbone terms review','YES','YES_MEASURED','219574600 bytes','READY_SEMANTIC_ADAPTER_ONLY'],
 ['DINO_L_HOT','https://huggingface.co/kshitijrajsharma/dinov3-hot-buildings','DINOv3-L / UperNet','building footprints','HOT VHR','256','SEMANTIC_WITH_WATERSHED','YES','YES','Apache-2.0 card; backbone terms need review','YES','POSSIBLE_NOT_MEASURED','1421224528 bytes ONNX','NOT_SELECTED_CPU_DOWNLOAD_COST'],
 ['DINO_V1_CONTACT','https://huggingface.co/LundAISociety/dinov3-building-segmenter-v1','DINOv3-S / NativeGridSegDecoder','touching-building separation','NOT_CONFIRMED_CURRENT_ACCESS','NOT_CONFIRMED','INSTANCE','YES_CONTACT_DAMS','ACCESS_401','Apache-2.0 card','UNVERIFIED_ACCESS','UNKNOWN','UNKNOWN','NOT_LOADABLE_PUBLIC_ENDPOINT_401'],
 ['DINO_HOT_V1_LATEST','https://huggingface.co/LundAISociety/hot-models/tree/main/v1.0','DINOv3 / building decoder','building instances','HOT dataset v1.0','512 grid (postprocess.json)','INSTANCE_FLOW','YES','DECODER_AVAILABLE; complete recipe not reproduced','Apache-2.0 weights card; backbone terms review','NO_RETAINED_GRAPH','NOT_MEASURED','NOT_DOWNLOADED','NOT_SELECTED_INCOMPLETE_CODE_RECIPE'],
 ['MASK2FORMER_OPENEARTH','https://huggingface.co/mfaytin/mask2former-satellite','Mask2Former / Swin','nine-class land cover, building one class','OpenEarthMap','processor-defined','SEMANTIC_MULTICLASS','NOT_BUILDING_INSTANCE_SPECIALIST','YES_SAFETENSORS','MIT','NO_PUBLISHED','NOT_MEASURED','NOT_DOWNLOADED','INCOMPATIBLE_PRIORITY_GENERALIST'],
 ['HRNET_W32','https://huggingface.co/Uve1048/hrnet-w32-footprint','HRNet-W32 / FCN','binary building footprints','NOT_DISCLOSED_IN_REVIEWED_CARD','1024 RGB','SEMANTIC','NO_EXPLICIT_INSTANCE_SEPARATION','YES_CHECKPOINT','MIT','NO_PUBLISHED','POSSIBLE_NOT_MEASURED','approx231MB card','DEPENDENCY_BLOCKED_MMSEG_NOT_INSTALLED']]
 fields=['MODEL','SOURCE','ARCHITECTURE','TASK','TRAINING_DATA','INPUT_RESOLUTION','SEMANTIC_OR_INSTANCE','BOUNDARY_AWARE','WEIGHTS_AVAILABLE','LICENSE','ONNX_AVAILABLE','CPU_COMPATIBLE','MODEL_SIZE','STATUS'];csvwrite(OUT/'14A10_external_model_candidates.csv',[dict(zip(fields,r)) for r in rows])
 font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);sheet=Image.new('RGB',(5*320,4*350),'white');d=ImageDraw.Draw(sheet)
 for i,p in enumerate(P['gold_patches']):
  pid=p['patch_id'];rgb=gdal.Open(str(ROOT/p['rgb_path'])).ReadAsArray()[:3];panels=[('RGB '+p['scene_type'],Image.fromarray(np.moveaxis(rgb,0,-1))),('C6 archived',Image.open(BASE/'qa/14A8_model_shootout/overlays'/('MODEL_C6__'+pid+'.png')))]+[(m['model'],Image.open(OUT/'overlays'/(m['model']+'__'+pid+'.png'))) for m in results]
  for j,(title,im) in enumerate(panels):sheet.paste(im.resize((320,320)),(j*320,i*350+28));d.text((j*320+3,i*350+4),title,fill='black',font=font)
 sheet.save(OUT/'overlays/14A10_ALL_MODELS_CONTACT.png')
 nextstep='14A11_HYBRID_TEACHER_AUTONOMOUS_LEARNING' if teacher else '14A11_ARCHITECTURE_REDESIGN_FOR_SMALL_BUILDINGS'
 end=f'''MODELS AUDITED :
9

MODELS READY :
3

MODELS BENCHMARKED :
3

C6 F1 :
0.3474

C7 F1 :
0.3491

BEST NEW MODEL :
{best['model']} — U-Net / EfficientNet-B4 dist3

BEST NEW F1 :
{best['object_f1']:.4f}

BEST NEW RECALL :
{best['object_recall']:.4f}

BEST NEW SMALL RECALL :
{best['SMALL_TP']} / 38

BEST NEW MISSED :
{best['FN']}

BEST NEW FP :
{best['FP']}

BEST NEW BOUNDARY F1 :
{best['boundary_f1']:.4f}

BEST NEW MERGED :
{best['MERGED']}

BEST NEW CPU TIME :
{best['cpu_inference_mean']:.3f} s inference + {best['cpu_postprocess_mean']:.3f} s postprocessing / patch 512x512

NEW MODEL BETTER THAN C7 :
{'YES' if better else 'NO'}

NEW SPECIALIZED TEACHER FOUND :
{'YES' if teacher else 'NO'}

PRODUCTION MODEL :
MODEL_C

PRODUCTION MODIFIED :
NO

NEXT STEP :
{nextstep}'''
 table='\n'.join(f"| {m['model']} | {m['TP']} | {m['FP']} | {m['FN']} | {m['object_precision']:.4f} | {m['object_recall']:.4f} | {m['object_f1']:.4f} | {m['SMALL_TP']}/{38} | {m['MEDIUM_TP']}/103 | {m['LARGE_TP']}/24 | {m['MERGED']} | {m['FRAGMENTED']} | {m['boundary_f1']:.4f} |" for m in results)
 newtable='\n'.join(f"| {m['model']} | {m['new_gt_matches_vs_c6']} | {m['small_new_matches_vs_c6']} | {m['lost_c6_matches']} | {m['pixel_iou']:.4f} | {m['dice']:.4f} | {m['cpu_inference_mean']:.3f} | {m['cpu_postprocess_mean']:.3f} |" for m in results)
 sens=[r for r in sensitivity if r['model']==best['model']]
 report=f'''# 14A.10 — Modèles Building spécialisés : audit et benchmark GOLD

## Décision

**Nouveau teacher spécialisé trouvé : UNET_DIST3.** F1={best['object_f1']:.4f}, rappel={best['object_recall']:.4f}, SMALL={best['SMALL_TP']}/38. Les nouvelles détections appariées aux GT absentes de C6 sont quantifiées ci-dessous. Aucune promotion : **128 FP et 37 fragmentations** imposent un filtrage/consensus et une validation non-GOLD ultérieurs. L'objectif de cette étape était discovery/intégration expérimentale/benchmark, pas C8 ; aucun entraînement exécuté.

## Audit public et traçabilité

Neuf offres/modèles audités ; quatre exports/checkpoints chargés sur un patch non-GOLD ; trois candidats retenus pour les quatre GOLD. CSV complet `14A10_external_model_candidates.csv` : toutes les colonnes demandées, sources, licences, poids, taille et statuts. Les métadonnées, fiches et révisions des dépôts sont archivées sous sources/.

- [U-Net dist3](https://huggingface.co/nilsho01/unet-effb4-dist3-buildings) : modèle Building avec trois têtes ; entraînement VHR spécialisé, input256. Carte CC-BY-4.0, mais attribution de certaines sources encore à revoir selon l'auteur. Poids ONNX figés, SHA256 `e1c14b893d738a660d99a5f456fc68c04077a09fcb8f88a0bcd577d72b40a735`. Usage expérimental seulement ; aucune conclusion de conformité production.
- [HOT/Lund](https://huggingface.co/LundAISociety/hot-models) : export DINOv3-S distillé récent, 47 Mo. Forward CPU réussi, sortie uint8 à quatre cartes. Le contrat complet de décodage des vecteurs et de flow n'a pas été retrouvé : INCOMPATIBLE pour ce benchmark, pas de masque inventé. La variante v1.0 conserve aussi une recette non reproduite ; le dépôt de code référencé retourne 404. Le modèle contact séparé renvoie HTTP401 à l'API ; aucun contournement.
- [SegFormer SpaceNet](https://huggingface.co/Abhatta7/building-footprint-segmentation) : anciens poids F déjà présents, architecture différente de C6 ; runtime restauré dans le sandbox, strict load passé. Ce n'est pas un nouveau checkpoint découvert, mais sa première évaluation reproductible sur ce GOLD dans ce travail.
- [DINOv3-S publié](https://huggingface.co/geobase/dinov3s-buildings) : ancien MODEL_G, hash identique au graphe S du dépôt [HOT](https://huggingface.co/kshitijrajsharma/dinov3-hot-buildings), maintenant évalué par un **adapter sémantique canal0**. Les paramètres de couleur viennent du preprocessor de la variante S ; ne pas les confondre avec ceux du L. L'adapter n'est pas une reproduction de tout le pipeline fAIr watershed/régularisation. Les déclarations de licence du miroir et de l'amont diffèrent ; revue nécessaire avant déploiement.
- [Mask2Former OpenEarthMap](https://huggingface.co/mfaytin/mask2former-satellite) : neuf classes de couverture du sol, non retenu comme spécialiste d'instances Building. [HRNet-W32](https://huggingface.co/Uve1048/hrnet-w32-footprint) : candidat Building, mais dépend de MMSegmentation ; pas installé pour cette sélection. DINOv3-L ONNX public de 1,42 Go : non retenu pour coût de ce screening CPU ; cela ne signifie pas un échec de chargement.

## Sandbox et protocole figé

Tout est isolé dans `14A10_specialized_benchmark/`. Deux nouveaux ONNX téléchargés, contrôlés contre tailles et SHA256 LFS ; F/G locaux conservés intacts. Dépendances post-traitement et Transformers installées par `--target` dans les seuls sous-dossiers expérimentaux. Aucun paquet du runtime production changé. Cache HF redirigé ensuite vers le sandbox et réseau d'inférence désactivé. Les sources distantes sont archivées comme texte, jamais importées/exécutées.

`protocol.json` + SHA256 écrits **avant tout GOLD**. Smoke sur 14A9B_AL_01, sortie512, valeurs finies, postprocessing testé hors GOLD. Codes de sortie **0** pour les quatre forwards et les trois post-traitements retenus. Voir PROCESS_EXITS/BENCHMARK_EXITS et logs. Aucun réglage issu de GOLD, aucun sweep, aucun nouvel entraînement.

Contrats figés :

1. **UNET_DIST3** : RGB/255 + ImageNet, quatre fenêtres natives256 sans resize ; fusion des trois cartes puis masque>=0,50, graines EDT>0,50, watershed sur -distance(mask), conformément à l'exemple publié. Pas de filtre479. Les **IDs d'instances** sont conservés pendant la polygonisation ; les bâtiments accolés ne sont pas refusionnés par une conversion binaire. La tête boundary existe, mais l'exemple d'inférence publié exploite mask+EDT, pas explicitement la troisième tête. Les limites internes des tuiles peuvent affecter les prédictions.
2. **SEGFORMER_F** : RGB/255, input512, logits128 interpolés bilinéairement puis sigmoid, seuil0,50, connexité8, minimum4px ; recette historique figée avant GOLD.
3. **DINO_S_SEMANTIC** : RGB/255 + ImageNet selon son preprocessor ; fenêtres256/stride192 avec bord terminal, moyenne des probabilités dans les recouvrements ; canal0 sigmoid, seuil publié0,4371 et minimum publié2,6465m². Pas de watershed ni simplification/régularisation géométrique ; cette variante sémantique peut fusionner des voisins.

Chaque candidat READY a effectué une seule série d'inférences sur les quatre mêmes RGB, après warmup synthétique, à quatre threads CPU. Même GT humain de 165 features, dont38 SMALL<=50m². MEDIUM>50–200m² et LARGE>200m² restent les strates descriptives 14A.9A. Aucune image/GT changée.

## Résultats GOLD — primaire IoU objet >=0,30

| Modèle | TP | FP | FN/Missed | Precision | Recall | F1 | SMALL TP/38 | MEDIUM | LARGE | Merged | Fragmented | Boundary F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C6 archivé | 37 | 11 | 128 | 0,7708 | 0,2242 | 0,3474 | 0/38 | 25/103 | 12/24 | 14 | 0 | 0,2829 |
| C7 archivé | 37 | 10 | 128 | 0,7872 | 0,2242 | 0,3491 | 0/38 | 25/103 | 12/24 | 14 | 0 | 0,2812 |
{table}

SMALL_FN explicites : UNET_DIST3=24 ; DINO_S_SEMANTIC=32 ; SEGFORMER_F=37. SMALL recalls respectifs : 0,3684 / 0,1579 / 0,0263. Les chiffres sont issus du matching un-à-un, pas de simples pixels positifs.

| Modèle | GT détectés absents de C6 | Dont SMALL | GT C6 perdus | Pixel IoU | Dice | CPU inference s | Postprocessing s |
|---|---:|---:|---:|---:|---:|---:|---:|
{newtable}

Les temps sont des moyennes par patch512 hors chargement/warmup, mesurées dans des workers séparés. Ils incluent les quatre ou neuf fenêtres nécessaires selon le modèle. C6 historique n'a pas été remesuré simultanément : comparaison de coût indicative, sensible à la charge/cache.

## Sanity check et limites

165 lignes GT uniques par modèle, aucune prédiction créditée à plusieurs GT ; toutes les paires retenues ont été revérifiées par intersection/union géométrique >=0,30. Le maximum de cardinalité puis IoU est le même matcher que 14A.8. Nombre d'IDs raster finaux égal au nombre d'objets vectoriels. Archives RGB et masques GT comparées pixel par pixel à leurs sources réelles. Les métriques objet utilisent les instances finales ; Pixel IoU/Dice/Boundary F1 utilisent la carte binaire brute au seuil, comme la baseline14A.8. BoundaryF1 micro avec tolérance1pixel, sans wrap. Merged/Fragmented : règles de couverture30% identiques à14A.8.

Sensibilité **du scoring seulement**, jamais un réglage des prédictions : pour le meilleur candidat, F1@IoU0,30={sens[0]['F1']:.4f}, @0,50={sens[1]['F1']:.4f}, @0,70={sens[2]['F1']:.4f}. La configuration ne change pas. Les overlays résidentiel et dense UNET ont été examinés : davantage de toits appariables et de séparations, mais aussi sur-segmentation et objets non appariés. Les FP sont relatifs aux annotations GOLD ; aucun audit sémantique exhaustif de ces128 FP n'est revendiqué.

**Teacher complémentaire ne signifie pas modèle prêt pour production.** UNET améliore F1, recall, small recall, missed, fusions et BoundaryF1, mais sa précision baisse à0,4754 et ses FP passent de11/10 à128. La fragmentation37 est une autre limite. La suite doit étudier un hybride et filtrer/calibrer exclusivement sur non-GOLD, sans imposer de nouveau paramètre à partir des erreurs GOLD. Les licences/attributions et la provenance des données externes doivent être revues. Le recouvrement éventuel des données d'entraînement publiques avec ce site ne peut pas être certifié à partir de ces seules fiches. Ce GOLD réutilisé est un benchmark interne, pas un nouveau test externe vierge.

## Protection et livrables

{len(after)} fichiers GOLD hashés avant/après : identiques. Quatre fichiers modèles et protocole SHA256 inchangés. MODEL_C production conservé ; aucun changement API/frontend/GEE/indices/exports/offline. Aucun C8, aucun pseudo-label training, aucun hybride entraîné. CSV candidats, contrats, sources épinglées, sortiesprobabilités/instances, métriques par patch et globales, matching, sensibilité et planche comparative sont livrés dans le sandbox.

## Statut final

'''+end+'\n'
 (ROOT/'docs/ETAPE_14A10_SPECIALIZED_BUILDING_AI_BENCHMARK.md').write_text(report,encoding='utf-8');print(end)
if __name__=='__main__':main()
