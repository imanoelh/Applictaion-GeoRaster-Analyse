"""Isolated read-only import/shutdown probes. No checkpoints or gold images loaded."""
from pathlib import Path
import json,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A7_gold_set/qa/14A7B_runtime'
SHIM="lib=torch.library.Library('torchvision','DEF');lib.define('nms(Tensor boxes, Tensor scores, float iou_threshold) -> Tensor');lib.define('qnms(Tensor boxes, Tensor scores, float iou_threshold) -> Tensor')"

def run(name,code):
    start=time.perf_counter();env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
    try:
        p=subprocess.run([sys.executable,'-P','-u','-c',"print('PROCESS_STARTED',flush=True)\n"+code+"\nprint('BODY_COMPLETED',flush=True)"],cwd=ROOT,env=env,capture_output=True,text=True,timeout=45)
        result=dict(name=name,returncode=p.returncode,exit_hex=f'0x{p.returncode&0xffffffff:08X}',stdout=p.stdout,stderr=p.stderr,elapsed_seconds=time.perf_counter()-start,stage='SHUTDOWN' if 'BODY_COMPLETED' in p.stdout and p.returncode else 'IMPORT_OR_BODY' if p.returncode else 'NORMAL_EXIT')
    except subprocess.TimeoutExpired as exc:
        result=dict(name=name,returncode=None,stdout=str(exc.stdout),stderr=str(exc.stderr),stage='TIMEOUT',elapsed_seconds=time.perf_counter()-start)
    print(name,result['returncode'],result['stage'],flush=True);return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    probes=[('torch_only','import torch'),('rasterio_only','import rasterio'),('onnxruntime_only','import onnxruntime'),
      ('torch_then_rasterio','import torch;import rasterio'),('torchvision_no_shim','import torch;import torchvision'),
      ('historical_global_shim','import torch;import rasterio;'+SHIM+';import torchvision'),
      ('local_shim_scope','import torch;import rasterio;exec("def load():\\n import torch\\n lib=torch.library.Library(\'torchvision\',\'DEF\')\\n lib.define(\'nms(Tensor boxes, Tensor scores, float iou_threshold) -> Tensor\')\\n lib.define(\'qnms(Tensor boxes, Tensor scores, float iou_threshold) -> Tensor\')\\n import torchvision".replace("\\\\n","\\n"));load()')]
    rows=[]
    for name,code in probes:
        rows.append(run(name,code));(OUT/'import_shutdown_probes.json').write_text(json.dumps(dict(python=sys.executable,probes=rows,no_inference=True,no_models_loaded=True),indent=2),encoding='utf-8')
    # Capture versions and thread-pool settings separately; do not import the application.
    rows.append(run('thread_pools','import torch;import onnxruntime;print(torch.__version__);print(torch.__config__.parallel_info());print(onnxruntime.__version__)'))
    (OUT/'import_shutdown_probes.json').write_text(json.dumps(dict(python=sys.executable,probes=rows,no_inference=True,no_models_loaded=True),indent=2),encoding='utf-8')

def smoke():
    OUT.mkdir(parents=True,exist_ok=True)
    code=r'''
import json,gc,hashlib
from pathlib import Path
import numpy as np,torch,rasterio,onnxruntime as ort,torchvision
from torchvision.models.segmentation import deeplabv3_resnet50
root=Path.cwd();base=root/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A7_gold_set'
pool=json.loads((base/'manifest/AI_ASSISTED_POOL.json').read_text(encoding='utf-8'))['patches']
gold=json.loads((base/'manifest/GOLD_SET_LOCK.json').read_text(encoding='utf-8'))['patches'];p=pool[0]
assert p['patch_id'] not in {g['patch_id'] for g in gold}
path=root/p['rgb_path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==p['sha256']
with rasterio.open(path) as ds:x=ds.read((1,2,3)).astype('float32')
x=(x-float(x.min()))/max(1e-6,float(x.max()-x.min()));torch.set_num_threads(4)
assert torchvision.ops.nms(torch.empty((0,4)),torch.empty(0),.5).numel()==0
# Lifecycle check: normal torchvision construction/disposal; no building checkpoint or C3/C6 forward.
fixture_model=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True);del fixture_model;gc.collect()
fixture=torch.nn.Conv2d(3,1,1,bias=False).eval()
with torch.no_grad():fixture.weight.fill_(1/3)
with torch.inference_mode():y=fixture(torch.from_numpy(x[None])).numpy()
assert y.shape==(1,1,512,512) and np.isfinite(y).all();np.testing.assert_allclose(y[0,0],x.mean(axis=0),rtol=1e-5,atol=1e-6)
del fixture;gc.collect()
onnx=root/'backend/data/models/building/experimental/spacenet2-deeplab/onnx/spacenet2_deeplab_main.onnx'
before=hashlib.sha256(onnx.read_bytes()).hexdigest();options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
session=ort.InferenceSession(str(onnx),sess_options=options,providers=['CPUExecutionProvider']);z=session.run(None,{session.get_inputs()[0].name:x[None]})[0]
assert z.shape[-2:]==(512,512) and np.isfinite(z).all();del session;gc.collect()
assert hashlib.sha256(onnx.read_bytes()).hexdigest()==before
dst=base/'qa/14A7B_runtime/smoke_fixture_outputs.npz';np.savez_compressed(dst,torch_fixture=y,onnx_logits=z)
with np.load(dst) as saved:assert saved['torch_fixture'].shape==y.shape and np.isfinite(saved['onnx_logits']).all()
print(json.dumps(dict(fixture_patch=p['patch_id'],rgb_unchanged=hashlib.sha256(path.read_bytes()).hexdigest()==p['sha256'],torch_fixture='PASS',native_nms='PASS',onnx_model_c_session='PASS',model_c3_inference='NOT_RUN',model_c6_inference='NOT_RUN',gold_inference='NOT_RUN',weights_unchanged=True,child_processes_started=0)),flush=True)
'''
    rows=[run('normal_torchvision_shutdown_repeat_'+str(i),'import torch;import rasterio;import torchvision') for i in range(1,4)]
    rows.append(run('non_gold_lifecycle_smoke',code))
    result=dict(python=sys.executable,results=rows,passed=all(r['returncode']==0 for r in rows),benchmark_started=False,training_started=False)
    (OUT/'fixed_runtime_smoke.json').write_text(json.dumps(result,indent=2),encoding='utf-8')

if __name__=='__main__':smoke() if '--smoke' in sys.argv else main()
