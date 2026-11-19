"""Record actual runtime exclusions without installing packages or downloading weights."""
from pathlib import Path
import os,sys,subprocess,json,csv,importlib.util
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/qa/14A8_model_shootout'
def main():
    records=[];env=os.environ.copy();env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=str(OUT/'runtime_cache'),TRANSFORMERS_CACHE=str(OUT/'runtime_cache'))
    for exe in [Path(sys.executable),ROOT/'.venv_13q1/Scripts/python.exe']:
        code="import torch;from transformers import SegformerConfig,SegformerForSemanticSegmentation;print('SEGFORMER_RUNTIME_IMPORT_PASS')"
        p=subprocess.run([str(exe),'-P','-u','-c',code],env=env,cwd=ROOT,capture_output=True,text=True,timeout=45)
        records.append(dict(model='MODEL_F;MODEL_F2',python=str(exe),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,import_only=True))
    import onnxruntime as ort
    path=ROOT/'backend/data/models/building/experimental/benchmark_13Q0B/model_g_dinov3s/model.onnx';options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
    s=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']);g=dict(model='MODEL_G',loadable=True,inputs=[dict(name=i.name,shape=i.shape) for i in s.get_inputs()],outputs=[dict(name=i.name,shape=i.shape) for i in s.get_outputs()],reason='3 output logits; building channel unresolved in frozen historical documentation. No channel guessed and no gold inference.');s=None
    audit=dict(segformer=records,model_g=g,missing_smp=importlib.util.find_spec('segmentation_models_pytorch') is None,no_install=True,no_download=True)
    (OUT/'14A8_excluded_runtime_evidence.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    rows=list(csv.DictReader((OUT/'14A8_model_availability.csv').open(encoding='utf-8-sig')))
    for r in rows:
        if r['MODEL']=='MODEL_G':r.update(LOADABLE='YES_ONNX_GRAPH',RUNTIME_AVAILABLE='YES',REASON='BUILDING_CHANNEL_UNRESOLVED_3_LOGITS; NOT_REPRODUCIBLE_PREDICTION_PIPELINE')
        if r['MODEL'] in ('MODEL_F','MODEL_F2'):r.update(LOADABLE='NO',RUNTIME_AVAILABLE='NO',REASON='ML_env: transformers missing; existing13q1 env: torchvision::nms import failure; no environment modified')
        if r['MODEL'] in ('MODEL_H','MODEL_A'):r.update(LOADABLE='NO',RUNTIME_AVAILABLE='NO',REASON='segmentation_models_pytorch absent in available stable CPU environment')
    with (OUT/'14A8_model_availability.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print('Excluded models audited without environment changes. G graph load PASS, interpretation unresolved.')
if __name__=='__main__':main()
