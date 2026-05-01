import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ.setdefault('OMP_NUM_THREADS', '4')
os.environ.setdefault('MKL_NUM_THREADS', '4')
import numpy as np
import cv2
import onnxruntime as ort

EMO_LABELS = ['angry','disgust','fear','happy','sad','surprise','neutral']

_so = ort.SessionOptions()
_so.intra_op_num_threads = 4
_so.inter_op_num_threads = 1
_so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
EMO_SESSION = ort.InferenceSession('emotion_model.onnx', sess_options=_so, providers=['CPUExecutionProvider'])
EMO_INPUT = EMO_SESSION.get_inputs()[0].name

_MEAN = np.array([0.5, 0.5, 0.5], dtype=np.float32).reshape(1, 1, 3)
_STD = np.array([0.5, 0.5, 0.5], dtype=np.float32).reshape(1, 1, 3)


def _preprocess_face(bgr_face):
    rgb = cv2.cvtColor(bgr_face, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (96, 96), interpolation=cv2.INTER_AREA)
    arr = rgb.astype(np.float32) / 255.0
    arr = (arr - _MEAN) / _STD
    arr = np.transpose(arr, (2, 0, 1))
    return arr


def override_emotion_with_local(image_path, baidu_result):
    if not isinstance(baidu_result, dict):
        return
    face_list = (baidu_result.get('result') or {}).get('face_list') or []
    if not face_list:
        return
    bgr = cv2.imread(image_path)
    if bgr is None:
        return
    H, W = bgr.shape[:2]

    tensors = []
    targets = []
    for face in face_list:
        loc = face.get('location') or {}
        l = int(max(0, loc.get('left', 0)))
        t = int(max(0, loc.get('top', 0)))
        w = int(loc.get('width', 0))
        h = int(loc.get('height', 0))
        if w <= 0 or h <= 0:
            continue
        pad = int(max(w, h) * 0.15)
        x1 = max(0, l - pad); y1 = max(0, t - pad)
        x2 = min(W, l + w + pad); y2 = min(H, t + h + pad)
        crop = bgr[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        tensors.append(_preprocess_face(crop))
        targets.append(face)

    if not tensors:
        return
    batch = np.stack(tensors).astype(np.float32)
    logits = EMO_SESSION.run(None, {EMO_INPUT: batch})[0]
    e = np.exp(logits - logits.max(axis=1, keepdims=True))
    probs = e / e.sum(axis=1, keepdims=True)
    for face, p in zip(targets, probs):
        idx = int(p.argmax())
        face['emotion'] = {'type': EMO_LABELS[idx], 'probability': float(p[idx])}
