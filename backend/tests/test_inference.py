from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from backend.app.config import Settings
from worker.inference import MobileNetPredictor, preprocess


def test_preprocessing_shape_dtype_and_normalization(tmp_path):
    path = tmp_path / "white.png"
    Image.new("RGB", (300, 400), (255, 255, 255)).save(path)
    batch = preprocess(path)
    assert batch.shape == (1, 3, 224, 224)
    assert batch.dtype == np.float32
    np.testing.assert_allclose(batch[0, :, 0, 0], (np.ones(3) - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225], rtol=1e-5)


def test_model_checksum_mismatch_is_rejected(tmp_path):
    path = tmp_path / "bad.onnx"
    path.write_bytes(b"not the model")
    with pytest.raises(ValueError, match="SHA256"):
        MobileNetPredictor(Settings(_env_file=None, model_path=path))


def test_extreme_aspect_ratio_has_bounded_preprocessing(tmp_path):
    path = tmp_path / "panorama.png"
    Image.new("RGB", (1, 30000), (120, 80, 40)).save(path)
    assert preprocess(path).shape == (1, 3, 224, 224)


@pytest.mark.model
def test_real_mobilenet_inference(tmp_path):
    settings = Settings(_env_file=None)
    if not settings.model_path.is_file() or not settings.labels_path.is_file():
        pytest.skip("Chạy scripts/download_model.py để kiểm thử model thật.")
    path = tmp_path / "sample.png"
    Image.new("RGB", (300, 240), (180, 90, 30)).save(path)
    model = MobileNetPredictor(settings)
    predictions = model.predict(path)
    assert len(predictions) == 5
    scores = [p["confidence"] for p in predictions]
    assert scores == sorted(scores, reverse=True)
    assert 0 < sum(scores) <= 1.000001
    assert all(0 <= p["class_id"] < 1000 and p["label"] for p in predictions)
