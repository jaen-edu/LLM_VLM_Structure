from pathlib import Path
from PIL import Image, ImageDraw
import torch
from transformers import AutoProcessor, Qwen3VLForConditionalGeneration


MODEL_PATH = Path("/workspace/AE.2.1/models/Qwen3-VL-8B-Instruct")

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        "로컬 모델이 없습니다. 11교시에서 Qwen3-VL-8B-Instruct를 먼저 준비하세요: "
        "/workspace/AE.2.1/models/Qwen3-VL-8B-Instruct"
    )

model_name = str(MODEL_PATH)
local_files_only = True

print("모델 경로:", model_name)

# 샘플 이미지 생성
sample_image = Image.new("RGB", (640, 360), color=(245, 248, 255))
draw = ImageDraw.Draw(sample_image)
draw.rectangle((80, 80, 560, 280), outline=(54, 116, 255), width=6)
draw.text((95, 95), "Qwen3VL Demo", fill=(54, 116, 255))
sample_image.save("qwen3vl_sample.png")
print("샘플 이미지 저장 완료: qwen3vl_sample.png")

# 모델 및 프로세서 로드
torch_dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
processor = AutoProcessor.from_pretrained(model_name, local_files_only=local_files_only)
model = Qwen3VLForConditionalGeneration.from_pretrained(
    model_name,
    torch_dtype=torch_dtype,
    device_map="auto" if torch.cuda.is_available() else None,
    local_files_only=local_files_only,
)
model.eval()

messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": sample_image},
            {"type": "text", "text": "이 그림을 보고 한 줄로 설명해줘."},
        ],
    }
]

prompt = processor.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True,
)
inputs = processor(text=[prompt], images=[sample_image], return_tensors="pt", padding=True)

if torch.cuda.is_available():
    inputs = {k: v.to("cuda") if hasattr(v, "to") else v for k, v in inputs.items()}
    model.to("cuda")

with torch.no_grad():
    generated_ids = model.generate(**inputs, max_new_tokens=80, do_sample=False)

answer = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
print("\n[응답]")
print(answer)
