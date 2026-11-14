import hashlib
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps


def preprocess(path: Path) -> np.ndarray:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        # Cùng cửa sổ trung tâm 224/256 của cạnh ngắn, tránh cấp phát ảnh
        # trung gian cực lớn khi đầu vào có tỷ lệ chiều dài/rộng bất thường.
        image = ImageOps.fit(image, (224, 224), method=Image.Resampling.BILINEAR, bleed=0.0625)
        pixels = np.asarray(image, dtype=np.float32) / 255.0
    pixels = (pixels - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array([0.229, 0.224, 0.225], dtype=np.float32)
    return np.ascontiguousarray(pixels.transpose(2, 0, 1)[None], dtype=np.float32)


class MobileNetPredictor:
    def __init__(self, settings):
        digest = hashlib.sha256(settings.model_path.read_bytes()).hexdigest()
        if digest != settings.model_sha256:
            raise ValueError("SHA256 của model không khớp cấu hình.")
        self.sha256 = digest
        self.version = settings.model_version
        self.top_k = settings.top_k
        label_bytes = settings.labels_path.read_bytes()
        if hashlib.sha256(label_bytes).hexdigest() != settings.labels_sha256:
            raise ValueError("SHA256 của nhãn không khớp cấu hình.")
        self.labels = label_bytes.decode("utf-8").splitlines()
        if len(self.labels) != 1000:
            raise ValueError("MobileNetV2 cần đúng 1000 nhãn ImageNet.")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        self.session = ort.InferenceSession(str(settings.model_path), sess_options=options, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def predict(self, path: Path) -> list[dict]:
        logits = np.asarray(self.session.run(None, {self.input_name: preprocess(path)})[0], dtype=np.float64).reshape(-1)
        if logits.size != len(self.labels) or not np.isfinite(logits).all():
            raise ValueError("Đầu ra model không hợp lệ.")
        exp = np.exp(logits - logits.max())
        probabilities = exp / exp.sum()
        indices = np.argsort(-probabilities)[:self.top_k]
        return [{"class_id": int(i), "label": self.labels[i].split(" ", 1)[1],
                 "confidence": float(probabilities[i])} for i in indices]
