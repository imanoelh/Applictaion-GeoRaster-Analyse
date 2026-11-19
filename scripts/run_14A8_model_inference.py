"""Isolated CPU benchmark workers. Frozen settings, no training or GOLD edits."""
from pathlib import Path
import os,sys,json,time,hashlib,subprocess,csv,gc,traceback,importlib.metadata
os.environ['OMP_NUM_THREADS']='4';os.environ['MKL_NUM_THREADS']='4';os.environ['OPENBLAS_NUM_THREADS']='4'
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/qa/14A8_model_shootout'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def peak_mb():
    import ctypes
    from ctypes import wintypes
    class Counts(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    c=Counts();c.cb=ctypes.sizeof(c);handle=ctypes.windll.kernel32.GetCurrentProcess();ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(handle),ctypes.byref(c),c.cb)
    return c.PeakWorkingSetSize/(1024**2)
def worker(mid):
    import numpy as np
    protocol=json.loads((OUT/'14A8_frozen_protocol.json').read_text());assert sha(OUT/'14A8_frozen_protocol.json')==(OUT/'14A8_frozen_protocol.sha256').read_text()
    spec=next(s for s in protocol['models'] if s['model']==mid);paths=spec['path'].split(';');expected=spec['sha256'].split(';')
    assert all(sha(ROOT/p)==h for p,h in zip(paths,expected));start=time.perf_counter();load_start=time.perf_counter()
    sessions=[];model=None
    if 'ONNX' in spec['engine']:
        import onnxruntime as ort
        for path in paths:
            options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1;options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
            session=ort.InferenceSession(str(ROOT/path),sess_options=options,providers=['CPUExecutionProvider']);assert session.get_inputs()[0].shape[1:]==[3,512,512];sessions.append(session)
        contracts=[dict(input_name=s.get_inputs()[0].name,input_shape=s.get_inputs()[0].shape,output_name=s.get_outputs()[0].name,output_shape=s.get_outputs()[0].shape) for s in sessions]
    else:
        import torch
        from torchvision.models.segmentation import deeplabv3_resnet50
        from torchvision.models.segmentation.deeplabv3 import DeepLabHead
        torch.set_num_threads(4);torch.set_num_interop_threads(1)
        model=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True);model.classifier=DeepLabHead(2048,1)
        ck=torch.load(ROOT/paths[0],map_location='cpu',weights_only=True);model.load_state_dict(ck['state_dict'],strict=True);del ck;model.eval();contracts=[dict(input_shape=[1,3,512,512],output='out',strict_load='PASS')]
    load_seconds=time.perf_counter()-load_start
    def prepare(rgb,kind):
        x=rgb.astype('float32')
        if kind=='rgb_div255':return x/255.
        lo,hi=float(x.min()),float(x.max());return (x-lo)/max(1e-6,hi-lo)
    def activate(z,two=False):
        assert z.shape[-2:]==(512,512)
        if two:
            assert z.shape[1]==2;q=z[0]-z[0].max(axis=0,keepdims=True);q=np.exp(q);return q[1]/q.sum(axis=0)
        assert z.shape[1]==1;return 1/(1+np.exp(-np.clip(z[0,0],-80,80)))
    def forward(x,xd=None):
        if sessions:
            z=sessions[0].run(None,{sessions[0].get_inputs()[0].name:x[None]})[0];p=activate(z,mid=='MODEL_D')
            if mid=='MODEL_E':
                d=sessions[1].run(None,{sessions[1].get_inputs()[0].name:xd[None]})[0];p=np.maximum(p,activate(d,True))
            return p
        with torch.inference_mode():return torch.sigmoid(model(torch.from_numpy(x[None]))['out'][0,0]).numpy()
    zero=np.zeros((3,512,512),dtype='float32');t=time.perf_counter();warm=forward(zero,zero);assert np.isfinite(warm).all();warmup=time.perf_counter()-t;del warm
    print(mid,'LOAD_PASS',round(load_seconds,3),'WARMUP',round(warmup,3),flush=True)
    rows=[]
    for patch in protocol['patches']:
        pid=patch['patch_id'];item_start=time.perf_counter()
        with np.load(OUT/'inputs'/(pid+'.npz')) as f:rgb=f['rgb']
        prep_start=time.perf_counter();x=prepare(rgb,'rgb_div255' if mid=='MODEL_D' else 'minmax');xd=prepare(rgb,'rgb_div255') if mid=='MODEL_E' else None;prep=time.perf_counter()-prep_start
        t=time.perf_counter();p=forward(x,xd).astype('float32');elapsed=time.perf_counter()-t
        assert p.shape==(512,512) and np.isfinite(p).all() and p.min()>=0 and p.max()<=1
        t=time.perf_counter();np.savez_compressed(OUT/'inference'/(mid+'__'+pid+'.npz'),probability=p);write=time.perf_counter()-t
        rows.append(dict(model=mid,patch_id=pid,preprocessing_seconds=prep,inference_seconds=elapsed,write_seconds=write,worker_patch_seconds=time.perf_counter()-item_start,peak_working_set_mb=peak_mb()))
        print(mid,pid,round(elapsed,3),'seconds',flush=True)
    model=None;sessions.clear();gc.collect()
    assert all(sha(ROOT/p)==h for p,h in zip(paths,expected))
    result=dict(model=mid,loadable=True,strict_load='PASS',load_seconds=load_seconds,warmup_seconds=warmup,worker_total_seconds=time.perf_counter()-start,peak_working_set_mb=peak_mb(),runtime=sys.executable,
      versions={n:importlib.metadata.version(n) for n in ('torch','torchvision','onnxruntime','numpy')},contracts=contracts,threads=4,inter_op_threads=1,patches=rows,weights_unchanged=True,training=False)
    (OUT/'models'/(mid+'_runtime.json')).write_text(json.dumps(result,indent=2),encoding='utf-8');print(mid,'BODY_COMPLETED',flush=True)
def all_models():
    protocol=json.loads((OUT/'14A8_frozen_protocol.json').read_text());runs=[]
    for spec in protocol['models']:
        mid=spec['model'];log=OUT/'logs'/(mid+'.log');t=time.perf_counter();print('START',mid,flush=True)
        with log.open('w',encoding='utf-8') as f:
            p=subprocess.run([sys.executable,'-P','-u',str(Path(__file__).resolve()),'--model',mid],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=360)
        runs.append(dict(model=mid,exit_code=p.returncode,wall_seconds=time.perf_counter()-t,log=str(log.relative_to(ROOT)),benchmark_status='BENCHMARKED' if p.returncode==0 else 'NOT_REPRODUCIBLE'))
        (OUT/'14A8_worker_exits.json').write_text(json.dumps(runs,indent=2),encoding='utf-8');print('END',mid,p.returncode,round(runs[-1]['wall_seconds'],2),flush=True)
    rows=list(csv.DictReader((OUT/'14A8_model_availability.csv').open(encoding='utf-8-sig')))
    for r in rows:
        executed=next((x for x in runs if x['model']==r['MODEL']),None)
        if executed:
            r['LOADABLE']='YES' if executed['exit_code']==0 else 'NO';r['BENCHMARK_STATUS']=executed['benchmark_status'];r['REASON']='LOAD_FORWARD_AND_NORMAL_EXIT_PASS' if executed['exit_code']==0 else 'SEE_WORKER_LOG'
    with (OUT/'14A8_model_availability.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
if __name__=='__main__':
    if '--all' in sys.argv:all_models()
    else:worker(sys.argv[sys.argv.index('--model')+1])
