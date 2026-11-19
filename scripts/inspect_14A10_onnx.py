"""Inspect graph contracts in a standalone CPU process; never read GOLD."""
from pathlib import Path
import os,json,time
os.environ['OMP_NUM_THREADS']='4'
import onnxruntime as ort
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A10_specialized_benchmark'
def main():
 candidates=dict(DINO_FAST=OUT/'sources/LundAISociety__hot-models/v0.4.1-fast-distilled/onnx/model_fp32.onnx',UNET_DIST3=OUT/'sources/nilsho01__unet-effb4-dist3-buildings/model.onnx',DINO_S=ROOT/'backend/data/models/building/experimental/benchmark_13Q0B/model_g_dinov3s/model.onnx')
 rows=[]
 for name,path in candidates.items():
  t=time.perf_counter();o=ort.SessionOptions();o.intra_op_num_threads=4;o.inter_op_num_threads=1
  try:
   s=ort.InferenceSession(str(path),sess_options=o,providers=['CPUExecutionProvider'])
   row=dict(model=name,path=str(path.relative_to(ROOT)),inputs=[dict(name=x.name,shape=x.shape,type=x.type) for x in s.get_inputs()],outputs=[dict(name=x.name,shape=x.shape,type=x.type) for x in s.get_outputs()],metadata=s.get_modelmeta().custom_metadata_map,load_seconds=time.perf_counter()-t);rows.append(row);print(json.dumps(row,indent=2),flush=True);s=None
  except Exception as e:print(name,'FAILED',str(e),flush=True)
 (OUT/'contracts.json').write_text(json.dumps(rows,indent=2))
if __name__=='__main__':main()
