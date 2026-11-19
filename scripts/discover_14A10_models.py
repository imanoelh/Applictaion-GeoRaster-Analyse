"""Fetch primary model cards/metadata only into the experimental sandbox."""
from pathlib import Path
import urllib.request,json,sys,hashlib
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A10_specialized_benchmark'
REPOS=['LundAISociety/dinov3-building-segmenter-v1','LundAISociety/hot-models','nilsho01/unet-effb4-dist3-buildings','geobase/dinov3s-buildings','kshitijrajsharma/dinov3-hot-buildings','Abhatta7/building-footprint-segmentation','mfaytin/mask2former-satellite','Uve1048/hrnet-w32-footprint']
def fetch(url):
 return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'GeoRaster-research-audit/14A10'}),timeout=90).read()
def main():
 (OUT/'sources').mkdir(parents=True,exist_ok=True)
 for repo in REPOS:
  folder=OUT/'sources'/repo.replace('/','__');folder.mkdir(exist_ok=True)
  try:
   data=json.loads(fetch('https://huggingface.co/api/models/'+repo+'?blobs=true'));(folder/'metadata.json').write_text(json.dumps(data,indent=2));revision=data['sha']
   card=fetch('https://huggingface.co/'+repo+'/resolve/'+revision+'/README.md');(folder/'README.md').write_bytes(card)
   files=[dict(name=f['rfilename'],size=f.get('size'),lfs=f.get('lfs')) for f in data.get('siblings',[]) if f['rfilename'].endswith(('.onnx','.json','.py')) and (repo!='LundAISociety/hot-models' or any(x in f['rfilename'] for x in ['v1.0/','v0.4.1-fast-distilled/','unet/']))]
   print(json.dumps(dict(repo=repo,revision=revision,files=files),indent=2),flush=True)
  except Exception as e:print('FAILED',repo,str(e),flush=True)
if __name__=='__main__':main()
