"""Download pinned public ONNX candidates and documentation; never execute remote code."""
from pathlib import Path
import sys,json,urllib.request,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
from discover_14A10_models import ROOT,OUT,fetch
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def get(repo,filename,weights=False):
 folder=OUT/'sources'/repo.replace('/','__');meta=json.loads((folder/'metadata.json').read_text());rev=meta['sha'];f=next(x for x in meta['siblings'] if x['rfilename']==filename);target=folder/filename;target.parent.mkdir(parents=True,exist_ok=True)
 expected=f.get('lfs',{}).get('sha256');size=f.get('size')
 if target.exists() and (not expected or sha(target)==expected):return
 url='https://huggingface.co/'+repo+'/resolve/'+rev+'/'+filename
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'GeoRaster-research-audit/14A10'}),timeout=120) as src,target.with_suffix(target.suffix+'.part').open('wb') as dst:
  while True:
   b=src.read(1<<20)
   if not b:break
   dst.write(b)
 temp=target.with_suffix(target.suffix+'.part');assert not size or temp.stat().st_size==size;assert not expected or sha(temp)==expected;temp.replace(target);print('DOWNLOADED',filename,target.stat().st_size,sha(target),flush=True)
def main():
 if '--contracts' in sys.argv:
  get('LundAISociety/hot-models','v0.4.1-vit320-lite/postprocess.json')
  tree=json.loads((OUT/'sources/hotosm__fAIr-models_tree.json').read_text());rev=tree['sha']
  for name in ['models/dinov3s_buildings/pipeline.py','models/dinov3s_buildings/README.md']:
   data=fetch('https://raw.githubusercontent.com/hotosm/fAIr-models/'+rev+'/'+name);target=OUT/'sources'/('fair_'+Path(name).name);target.write_bytes(data);print('SOURCE_SAVED',name)
  return
 for filename in ['v0.4.1-fast-distilled/config.json','v0.4.1-fast-distilled/model.json','v0.4.1-fast-distilled/run.json','v0.4.1-fast-distilled/onnx/model_fp32.onnx','v1.0/config.json','v1.0/model.json','v1.0/postprocess.json','unet/model.json']:
  get('LundAISociety/hot-models',filename)
 for filename in ['config.json','best_threshold.json','model.onnx']:get('nilsho01/unet-effb4-dist3-buildings',filename)
 for filename in ['config.json','preprocessor_config.json']:get('geobase/dinov3s-buildings',filename)
 # Source discovery only: this code is archived as text and is not imported/executed.
 for repo in ['LundAISociety/dataset-hot','hotosm/fAIr-models']:
  try:
   data=json.loads(fetch('https://api.github.com/repos/'+repo+'/git/trees/main?recursive=1'));p=OUT/'sources'/(repo.replace('/','__')+'_tree.json');p.write_text(json.dumps(data,indent=2));print('GITHUB_TREE',repo,[x['path'] for x in data.get('tree',[]) if any(s in x['path'].lower() for s in ['postprocess','watershed','onnx','predict']) and x['path'].endswith(('.py','.ts'))][:45])
  except Exception as e:print('SOURCE_UNAVAILABLE',repo,str(e))
if __name__=='__main__':main()
