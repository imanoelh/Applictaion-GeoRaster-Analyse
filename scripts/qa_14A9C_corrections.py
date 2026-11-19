"""Read-only QA of persisted human review; no inference, training or calibration."""
from pathlib import Path
import sys,json,csv,sqlite3,hashlib,zipfile,xml.etree.ElementTree as ET
from collections import Counter,defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_14A9B_datasets import ROOT,BASE,AL,DEV,GOLD,dump,sha,csvwrite
from osgeo import gdal
from shapely import wkb
from shapely.validation import explain_validity
from shapely.ops import transform as geom_transform,unary_union
from shapely.geometry import Polygon,box
from pyproj import Transformer,CRS
import numpy as np

OUT=BASE/'qa/14A9C_correction_qa'
def snapshot(path,name):
 target=OUT/(name+'.gpkg')
 if target.exists():
  evidence=json.loads((OUT/'14A9C_SOURCE_INTEGRITY.json').read_text())['source_hashes_before']
  assert evidence.get(str(path.relative_to(ROOT)))==sha(path),'Source changed: retain old snapshot; audit a fresh run separately'
  for suffix in ['-wal']:
   side=Path(str(path)+suffix)
   if side.exists():assert evidence.get(str(side.relative_to(ROOT)))==sha(side)
  return target
 src=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);dst=sqlite3.connect(target)
 assert src.execute('pragma integrity_check').fetchone()[0]=='ok'
 src.backup(dst);dst.close();src.close()
 return target
def features(path,table):
 ds=gdal.OpenEx(str(path),gdal.OF_VECTOR,open_options=['IMMUTABLE=YES']);assert ds
 layer=ds.GetLayerByName(table);assert layer,table
 out=[]
 for f in layer:
  geom=f.GetGeometryRef()
  out.append(dict(fid=f.GetFID(),attrs={d.GetName():f.GetField(d.GetName()) for d in layer.schema},geometry=wkb.loads(bytes(geom.ExportToWkb())) if geom else None))
 crs=layer.GetSpatialRef().ExportToWkt();ds=None
 return out,crs
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 records=json.loads((AL/'manifests/14A9B_selected_patches.json').read_text())
 gold_before={str(p.relative_to(ROOT)):sha(p) for p in GOLD.rglob('*') if p.is_file()}
 dump(OUT/'GOLD_HASHES_BEFORE.json',gold_before)
 patches=[];feature_rows=[];events=[];errors=[];sources_before={};group_stats={};project_sources=[]
 for directory,filename in [(AL,'14A9B_ACTIVE_LEARNING_CORRECTION.qgz'),(DEV,'14A9B_DEV_CALIBRATION_CORRECTION.qgz')]:
  path=directory/'qgis'/filename
  with zipfile.ZipFile(path) as z:
   tree=ET.fromstring(z.read(next(n for n in z.namelist() if n.endswith('.qgs'))))
   for layer in tree.findall('./projectlayers/maplayer'):
    project_sources.append(dict(project=str(path.relative_to(ROOT)),name=layer.findtext('layername'),datasource=layer.findtext('datasource')))
 dump(OUT/'14A9C_PROJECT_DATASOURCES.json',project_sources)
 for name,directory,split,ai_dir,gt_dir in [('TRAIN',AL,'ACTIVE_LEARNING_TRAIN','train_candidates','corrected_gt'),('DEV',DEV,'DEV_CALIBRATION','qa','gt')]:
  manual=directory/gt_dir/'MANUAL_CORRECTED_GT.gpkg';ai=directory/ai_dir/'AI_PREANNOTATION_C6.gpkg'
  for p in [manual,ai]:
   for q in [p,Path(str(p)+'-wal')]:
    if q.exists():sources_before[str(q.relative_to(ROOT))]=sha(q)
  snap=snapshot(manual,name+'_CORRECTED_SNAPSHOT');ref=snapshot(ai,name+'_AI_REFERENCE_SNAPSHOT')
  totals=Counter();size=Counter();actions=Counter();small_added=0;small_missed=0;small_merged=0
  for r in [r for r in records if r['split']==split]:
   pid=r['patch_id'];fs,crs=features(snap,pid);original,_=features(ref,pid);assert CRS.from_wkt(crs).equals(CRS.from_epsg(32637))
   rgbpath=ROOT/r['rgb_path'];assert sha(rgbpath)==r['rgb_sha256'];ds=gdal.Open(str(rgbpath));assert ds and (ds.RasterXSize,ds.RasterYSize)==(512,512)
   tr=ds.GetGeoTransform();proj=ds.GetProjection();to_utm=Transformer.from_crs(proj,'EPSG:32637',always_xy=True)
   to_native=Transformer.from_crs('EPSG:32637',proj,always_xy=True);inv=gdal.InvGeoTransform(tr)
   def pixel_coords(x,y,z=None):
    x,y=to_native.transform(x,y);x=np.asarray(x);y=np.asarray(y)
    return inv[0]+inv[1]*x+inv[2]*y,inv[3]+inv[4]*x+inv[5]*y
   row=Counter();row['features']=len(fs);geoms=[];seen={};ids=set();human=0;unchanged=0
   old_by_pid={str(f['attrs'].get('proposal_id')):f for f in original}
   old_by_bid={str(f['attrs'].get('building_id')):f for f in original}
   current_parents=defaultdict(list);event_rows=[]
   for f in fs:
    a=f['attrs'];g=f['geometry'];problems=[];reason=explain_validity(g) if g is not None else 'NULL';bid=a.get('building_id')
    if g is None:row['null']+=1;problems.append('NULL')
    else:
     if g.is_empty:row['empty']+=1;problems.append('EMPTY')
     if not g.is_valid:row['invalid']+=1;problems.append('INVALID:'+reason)
     if 'intersection' in reason.lower():row['self_intersections']+=1
     if g.area<=0:row['zero_area']+=1;problems.append('ZERO_AREA')
     if g.geom_type not in ['Polygon','MultiPolygon']:row['wrong_geometry_type']+=1;problems.append('NON_POLYGON')
     if not g.is_empty:
      key=g.normalize().wkb
      if key in seen:row['duplicates']+=1;problems.append('EXACT_DUPLICATE_OF_FID_'+str(seen[key]))
      seen[key]=f['fid']
      # Test in the native pixel grid. A four-corner UTM chord is not the
      # exact boundary of a geographic raster and falsely flags edge objects.
      gp=geom_transform(pixel_coords,g)
      if not box(0,0,512,512).buffer(1e-6).covers(gp):row['oob']+=1;problems.append('OUT_OF_RGB_BOUNDS')
      if g.is_valid and g.area>0:geoms.append(g)
    if a.get('patch_id')!=pid:row['wrong_patch']+=1;problems.append('WRONG_PATCH_ID')
    if not bid or str(bid) in ids:row['building_id_error']+=1;problems.append('MISSING_OR_DUPLICATE_BUILDING_ID')
    ids.add(str(bid))
    source=str(a.get('source') or '').upper();review=str(a.get('review_status') or '').upper();annotation=str(a.get('annotation_status') or '').upper()
    # Human-reviewed original proposals may retain their AI provenance, but review must be explicit.
    human_ok=review in ['REVIEWED','VALIDATED','HUMAN_VALIDATED'] and annotation in ['VALIDATED','HUMAN_VALIDATED']
    if not human_ok:row['human_status_not_validated']+=1;problems.append('HUMAN_VALIDATION_STATUS_MISSING')
    else:human+=1
    if not source:row['source_missing']+=1;problems.append('SOURCE_MISSING')
    if not a.get('review_status'):row['review_status_missing']+=1
    old=old_by_pid.get(str(a.get('proposal_id'))) or old_by_bid.get(str(bid))
    if old is not None:
     parent=str(old['attrs']['proposal_id']);current_parents[parent].append(f)
     equal=g is not None and old['geometry'] is not None and g.equals(old['geometry'])
     unchanged+=int(equal);action=('KEPT_CORRECT' if human_ok else 'UNCHANGED_UNREVIEWED') if equal else 'EDITED_BOUNDARY'
     if a.get('correction_action')=='SPLIT':action='SPLIT_MERGED'
    else:parent='';action='ADDED_FN'
    area=g.area if g is not None else 0;cls='SMALL' if 0<area<=50 else 'MEDIUM' if 50<area<=200 else 'LARGE' if area>200 else 'UNDEFINED';size[cls]+=1
    small_added+=int(action=='ADDED_FN' and cls=='SMALL')
    # Missed = no matched provenance, not proof that C6 had zero pixel signal.
    small_missed+=int(action=='ADDED_FN' and cls=='SMALL')
    small_merged+=int(cls=='SMALL' and (a.get('correction_action')=='SPLIT' or a.get('error_category')=='MERGED'))
    feature_rows.append(dict(dataset=name,patch_id=pid,fid=f['fid'],building_id=bid,area_m2=area,size_class=cls,source=a.get('source'),review_status=a.get('review_status'),annotation_status=a.get('annotation_status'),error_category=a.get('error_category'),correction_action=a.get('correction_action'),human_validated=human_ok,geometry_reason=reason,errors=';'.join(problems)))
    event_rows.append(dict(dataset=name,patch_id=pid,building_id=bid,proposal_id=parent,classification=action,human_confirmed=human_ok,error_category=a.get('error_category'),basis='PERSISTED_GEOMETRY_AND_PROVENANCE_COMPARISON_NOT_SEMANTIC_PROOF'))
    for error in problems:errors.append(dict(dataset=name,patch_id=pid,building_id=bid,fid=f['fid'],error=error))
   # One parent split into several outputs is one corrected merge, not N separate merge events.
   split_parents={k for k,v in current_parents.items() if len(v)>1 or any(f['attrs'].get('correction_action')=='SPLIT' for f in v)}
   for e in event_rows:
    if e['proposal_id'] in split_parents:e['classification']='SPLIT_MERGED_CHILD'
   counts=Counter(e['classification'] for e in event_rows);counts['SPLIT_MERGED']=len(split_parents)
   for old in original:
    parent=str(old['attrs']['proposal_id'])
    if parent not in current_parents:
     counts['DELETED_FP']+=1;event_rows.append(dict(dataset=name,patch_id=pid,building_id=old['attrs'].get('building_id'),proposal_id=parent,classification='DELETED_FP',human_confirmed='PATCH_REVIEW_REQUIRED',error_category='UNCONFIRMED_DELETION',basis='PROPOSAL_REMOVED_NOT_AUTOMATIC_PROOF_OF_SEMANTIC_FP'))
   # Empty negatives need a persisted explicit human patch review; no invented validation.
   patch_human=bool(fs) and human==len(fs)
   critical=['null','empty','invalid','zero_area','duplicates','oob','wrong_patch','wrong_geometry_type','building_id_error','source_missing']
   geometry_pass=not any(row[k] for k in critical)
   validated=geometry_pass and patch_human
   maskpath='';alignment='NOT_GENERATED'
   if validated:
    from diagnose_14A9A_small_buildings import rasterize
    mask=rasterize(unary_union(geoms),Transformer.from_crs('EPSG:32637',proj,always_xy=True),tr,proj) if geoms else np.zeros((512,512),bool)
    folder=directory/('corrected_gt/masks_14A9C' if name=='TRAIN' else 'masks/14A9C');folder.mkdir(parents=True,exist_ok=True);path=folder/(pid+'_GT.tif')
    if path.exists():raise RuntimeError('Refuse replacing prior QA mask')
    d=gdal.GetDriverByName('GTiff').Create(str(path),512,512,1,gdal.GDT_Byte,options=['COMPRESS=DEFLATE']);d.SetGeoTransform(tr);d.SetProjection(proj);d.GetRasterBand(1).WriteArray(mask.astype('uint8'));d=None
    d=gdal.Open(str(path));assert d.GetGeoTransform()==tr and d.GetProjection()==proj and np.array_equal(d.ReadAsArray(),mask.astype('uint8'));alignment='PASS';maskpath=str(path.relative_to(ROOT))
   pr=dict(dataset=name,patch_id=pid,features=len(fs),initial_proposals=len(original),unchanged_proposal_geometry=unchanged,geometry_pass=geometry_pass,human_validated=patch_human,patch_validated=validated,mask_path=maskpath,alignment=alignment,**{k:row[k] for k in critical+['self_intersections','human_status_not_validated']})
   patches.append(pr);totals.update(row);actions.update(counts);events.extend(event_rows)
   print(name,pid,'FEATURES',len(fs),'UNCHANGED',unchanged,'INVALID',row['invalid'],'OOB',row['oob'],'HUMAN_VALIDATED',human,flush=True)
  group_stats[name]=dict(counters=dict(totals),sizes=dict(size),corrections=dict(actions),small_added=small_added,small_missed=small_missed,small_merged_corrected=small_merged)
 # Spatial checks use actual RGB footprints in the locked manifest, not merely IDs.
 train=[r for r in records if r['split']=='ACTIVE_LEARNING_TRAIN'];dev=[r for r in records if r['split']=='DEV_CALIBRATION'];goldlock=json.loads((GOLD/'manifest/GOLD_SET_LOCK.json').read_text())['patches']
 overlap_td=sum(box(*a['bounds_32637']).intersection(box(*b['bounds_32637'])).area>0 for a in train for b in dev)
 overlap_gold=sum(box(*a['bounds_32637']).intersection(box(*b['bounds_32637'])).area>0 for a in records for b in goldlock)
 assert len({r['patch_id'] for r in records})==14 and not ({r['rgb_sha256'] for r in train}&{r['rgb_sha256'] for r in dev})
 assert not overlap_td and not overlap_gold
 changed=[p for p,h in sources_before.items() if not (ROOT/p).exists() or sha(ROOT/p)!=h]
 gold_after={str(p.relative_to(ROOT)):sha(p) for p in GOLD.rglob('*') if p.is_file()};gold_changed=gold_before!=gold_after
 dump(OUT/'GOLD_HASHES_AFTER.json',gold_after);dump(OUT/'14A9C_SOURCE_INTEGRITY.json',dict(source_hashes_before=sources_before,changed=changed,gold_modified=gold_changed,gold_files_checked=len(gold_before)))
 assert not changed and not gold_changed,'Source changed during QA; do not authorize readiness'
 csvwrite(OUT/'14A9C_patch_QA.csv',patches)
 if feature_rows:csvwrite(OUT/'14A9C_feature_QA.csv',feature_rows)
 if errors:csvwrite(OUT/'14A9C_errors.csv',errors)
 if events:csvwrite(OUT/'14A9C_correction_events.csv',events)
 for name,directory in [('TRAIN',AL),('DEV',DEV)]:
  summary=[]
  for p in [p for p in patches if p['dataset']==name]:
   ev=[e for e in events if e['patch_id']==p['patch_id']];c=Counter(e['classification'] for e in ev)
   summary.append(dict(patch_id=p['patch_id'],KEPT_CORRECT=c['KEPT_CORRECT'],DELETED_FP=c['DELETED_FP'],ADDED_FN=c['ADDED_FN'],EDITED_BOUNDARY=c['EDITED_BOUNDARY'],SPLIT_MERGED=group_stats[name]['corrections'].get('SPLIT_MERGED',0) if len([x for x in patches if x['dataset']==name])==1 else len({e['proposal_id'] for e in ev if e['classification']=='SPLIT_MERGED_CHILD'}),OTHER=c['OTHER']+c['UNCHANGED_UNREVIEWED'],UNCHANGED_UNREVIEWED=c['UNCHANGED_UNREVIEWED'],human_validated=p['human_validated'],note='Unchanged unreviewed proposals are OTHER, never confirmed human KEEP; removed does not prove semantic FP.'))
  csvwrite(directory/'manifests'/('14A9C_train_correction_summary.csv' if name=='TRAIN' else '14A9C_dev_correction_summary.csv'),summary)
 ready_train=all(p['patch_validated'] for p in patches if p['dataset']=='TRAIN');ready_dev=all(p['patch_validated'] for p in patches if p['dataset']=='DEV')
 result=dict(datasets=group_stats,patches=patches,train_dev_overlap=overlap_td,gold_overlap=overlap_gold,gold_modified=gold_changed,ready_for_training=ready_train,ready_for_calibration=ready_dev,training=False,calibration=False)
 dump(OUT/'14A9C_summary.json',result)
 lines=[]
 for name in ['TRAIN','DEV']:
  for p in [p for p in patches if p['dataset']==name]:lines.append(f"| {name} | {p['patch_id']} | {p['features']} | {p['unchanged_proposal_geometry']} | {p['invalid']} | {p['oob']} | {'YES' if p['human_validated'] else 'NO'} |")
 t=group_stats['TRAIN'];v=group_stats['DEV'];tc=t['counters'];vc=v['counters']
 tm=sum(p['alignment']=='PASS' for p in patches if p['dataset']=='TRAIN');dm=sum(p['alignment']=='PASS' for p in patches if p['dataset']=='DEV')
 final=f'''TRAIN PATCHES :
10

DEV PATCHES :
4

TRAIN GT FEATURES :
{tc['features']} (propositions IA persistées, non validées humainement)

DEV GT FEATURES :
{vc['features']} (propositions IA persistées, non validées humainement)

TRAIN INVALID :
{tc.get('invalid',0)}

DEV INVALID :
{vc.get('invalid',0)}

TRAIN OOB :
{tc.get('oob',0)}

DEV OOB :
{vc.get('oob',0)}

TRAIN MASKS READY :
{tm} / 10

DEV MASKS READY :
{dm} / 4

SMALL BUILDINGS TRAIN :
{t['sizes'].get('SMALL',0)}

SMALL BUILDINGS DEV :
{v['sizes'].get('SMALL',0)}

C6 FALSE POSITIVES CORRECTED :
{t['corrections'].get('DELETED_FP',0)+v['corrections'].get('DELETED_FP',0)}

C6 MISSED BUILDINGS ADDED :
{t['corrections'].get('ADDED_FN',0)+v['corrections'].get('ADDED_FN',0)}

C6 MERGED BUILDINGS SPLIT :
{t['corrections'].get('SPLIT_MERGED',0)+v['corrections'].get('SPLIT_MERGED',0)}

TRAIN / DEV OVERLAP :
{overlap_td}

GOLD OVERLAP :
{overlap_gold}

GOLD MODIFIED :
NO

READY_FOR_ACTIVE_LEARNING_TRAINING :
{'YES' if ready_train else 'NO'}

READY_FOR_DEV_CALIBRATION :
{'YES' if ready_dev else 'NO'}

NEXT STEP :
{'14A9D_DEV_POSTPROCESSING_CALIBRATION' if ready_dev and ready_train else 'FIX_CORRECTION_QA'}'''
 report='''# 14A.9C — QA des corrections assistées TRAIN / DEV

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
'''+ '\n'.join(lines)+f'''

Les deux patches négatifs TRAIN vides AL09/AL10 n'ont pas non plus d'attestation persistée de revue complète du patch. Une couche vide n'est pas automatiquement un négatif humain validé.

## Corrections et tailles

Les deux CSV demandés sont créés dans les dossiers `manifests/` TRAIN et DEV : `14A9C_train_correction_summary.csv` et `14A9C_dev_correction_summary.csv`. **KEPT_CORRECT confirmé=0**, DELETED_FP=0, ADDED_FN=0, EDITED_BOUNDARY=0, SPLIT_MERGED=0. Les propositions inchangées mais non revues sont explicitement `UNCHANGED_UNREVIEWED` et classées OTHER (124 TRAIN / 49 DEV), sans inventer une validation KEEP.

Tailles descriptives identiques à 14A.9A : SMALL <=50 m², MEDIUM >50–200 m², LARGE >200 m². Sur les propositions persistées : TRAIN **0 / 58 / 66**, DEV **0 / 22 / 27**. Il ne s'agit pas de statistiques d'une GT humaine validée. Petits bâtiments ajoutés manuellement=0, petits bâtiments ajoutés sans parent C6=0, petites sorties de fusion corrigées=0. Ces zéros ne mesurent pas les omissions réelles de C6 dans les images ; ils reflètent l'absence d'ajouts humains enregistrés.

## Masques et readiness

**Aucun nouveau masque GT humain généré** : 0/10 TRAIN, 0/4 DEV. Les masques IA existants ne sont pas recyclés sous un nom GT. Les géométries sont techniquement exploitables mais les préconditions humaines sont absentes. L'alignement de nouveaux masques humains reste NOT_GENERATED ; celui des masques de préannotation avait été contrôlé en 14A.9B et ne vaut pas validation des corrections.

## Protection des splits et du GOLD

TRAIN∩DEV=0 ; TRAIN∩GOLD=0 ; DEV∩GOLD=0, contrôlés sur les emprises métriques verrouillées et les IDs, avec contrôle des hashes RGB sélectionnés. Les quatre DEV restent réservés à calibration, jamais TRAIN. Les fichiers sources corrigés/références et leurs WAL éventuels sont inchangés pendant cette QA. **{len(gold_before)} fichiers GOLD** hashés avant/après : aucun changement. Aucun modèle, frontend, API ou registry modifié. Aucune inférence, aucun entraînement ni sweep de calibration.

## Action requise

1. Vérifier les sessions QGIS en cours sans fermer ni perdre les modifications non enregistrées.
2. Enregistrer les éditions des couches **MANUAL_CORRECTED_GT_PENDING**, et vérifier leur persistance dans les sources ci-dessus.
3. Renseigner les catégories de correction, les sources humaines et les statuts de revue ; attester explicitement les patches négatifs vides. Ne pas passer simplement toutes les copies IA à VALIDATED sans revue effective.
4. Refaire la QA sur la version humaine persistée ; générer les masques uniquement après succès, puis autoriser éventuellement 14A.9D.

Les snapshots et tableaux détaillés de cette QA sont conservés dans `qa/14A9C_correction_qa/`. Ils figent l'état observé ; une version source ultérieure devra être auditée dans une nouvelle exécution avec de nouveaux snapshots, sans écraser cette preuve.

## Statut final

'''+final+'\n'
 (ROOT/'docs/ETAPE_14A9C_AI_ASSISTED_CORRECTION_QA.md').write_text(report,encoding='utf-8')
 print(json.dumps(dict(datasets=group_stats,ready_for_training=ready_train,ready_for_calibration=ready_dev),indent=2))
if __name__=='__main__':main()
