from pathlib import Path
import json, torch, numpy as np
from torchvision.models.segmentation import deeplabv3_resnet50
from torchvision.models.segmentation.deeplabv3 import DeepLabHead
ROOT=Path(__file__).resolve().parents[1]; ck=ROOT/'backend/data/models/model_c2_experimental/final_model_c2.pth'; out=ROOT/'backend/data/models/model_c2_experimental/model_c2.onnx'
state=torch.load(ck,map_location='cpu',weights_only=True)['state_dict']; m=deeplabv3_resnet50(weights=None,weights_backbone=None,aux_loss=True); m.classifier=DeepLabHead(2048,1); m.load_state_dict(state,strict=True); m.eval()
class W(torch.nn.Module):
    def __init__(self,m): super().__init__(); self.m=m
    def forward(self,x): return self.m(x)['out']
torch.onnx.export(W(m),torch.randn(1,3,512,512),str(out),input_names=['image'],output_names=['out'],opset_version=17,dynamic_axes={'image':{0:'batch'},'out':{0:'batch'}})
import onnx, onnxruntime as ort
onnx.checker.check_model(onnx.load(str(out))); sess=ort.InferenceSession(str(out),providers=['CPUExecutionProvider']); z=sess.run(['out'],{'image':np.zeros((1,3,512,512),dtype='float32')})[0]; result={'onnx':str(out),'load':'PASS','input_shape':[1,3,512,512],'output_shape':list(z.shape),'probability_range':[float((1/(1+np.exp(-np.clip(z,-80,80)))).min()),float((1/(1+np.exp(-np.clip(z,-80,80)))).max())],'runtime':'ONNX Runtime CPU'}; (ROOT/'backend/data/fine_tuning/buildings/maxar_v2_high_precision/14A2_expansion/qa/14A3_model_c2_onnx_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result,indent=2))
