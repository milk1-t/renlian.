# encoding:utf-8
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import base64
import requests
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# MySQL 数据库模块
try:
    from db import (
        init_db, get_user_by_username, create_user,
        save_analysis, load_analysis_list, load_analysis_by_id,
        delete_analysis, delete_analysis_batch
    )
    USE_MYSQL = True
except ImportError:
    USE_MYSQL = False

app = Flask(__name__)
app.secret_key = 'face_recognition_secret_key'

# 百度API配置
API_KEY = 'ql21uVftf13jXL0FGEkFCCzH'
SECRET_KEY = '81L7L2FRTMcEkuMr3opuyx8cccXsEw20'

# 上传图片保存路径（图片持久保存，供统计看板查看）
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
SEAT_LAYOUT_PATH = os.environ.get('SEAT_LAYOUT_PATH', 'seat_layout.json')

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 兼容旧版：无 MySQL 时的内置用户
USERS_FALLBACK = {
    'admin': {'password': '123456', 'name': '管理员', 'role': 'admin'},
    'user': {'password': '123456', 'name': '普通用户', 'role': 'user'}
}

# 性别中文映射
GENDER_MAP = {
    'male': '男性',
    'female': '女性'
}

# 眼镜类型中文映射
GLASSES_MAP = {
    'none': '无眼镜',
    'common': '普通眼镜',
    'sun': '墨镜'
}

# 情绪类型中文映射
EMOTION_MAP = {
    'angry': '愤怒',
    'disgust': '厌恶',
    'fear': '恐惧',
    'happy': '高兴',
    'sad': '伤心',
    'surprise': '惊讶',
    'neutral': '无表情',
    'pouty': '撅嘴',
    'grimace': '鬼脸'
}

# 二级情绪（便于心理检测场景展示）。注意：百度原生情绪类型有限，这里是对其“再归类”。
SECONDARY_EMOTION_MAP = {
    'happy': '开心',
    'neutral': '平静',
    'surprise': '惊讶',
    'angry': '生气',
    'disgust': '厌恶',
    'sad': '悲伤',
    'fear': '焦虑',
    'pouty': '不满',
    'grimace': '搞怪'
}

# 人脸类型中文映射
FACE_TYPE_MAP = {
    'human': '真实人脸',
    'cartoon': '卡通人脸'
}

# 口罩状态中文映射
MASK_MAP = {
    0: '没戴口罩',
    1: '戴口罩'
}

# 脸型中文映射
FACE_SHAPE_MAP = {
    'square': '方形',
    'triangle': '三角形',
    'oval': '椭圆',
    'heart': '心形',
    'round': '圆形'
}


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def load_seat_layout(path: str) -> Dict[str, Any]:
    try:
        if not os.path.exists(path):
            return {"version": 1, "seats": []}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"version": 1, "seats": []}
        seats = data.get("seats", [])
        if not isinstance(seats, list):
            seats = []
        data["seats"] = seats
        return data
    except Exception:
        return {"version": 1, "seats": []}


SEAT_LAYOUT = load_seat_layout(SEAT_LAYOUT_PATH)

if USE_MYSQL:
    try:
        init_db()
    except Exception:
        pass


def _face_center(location: Dict[str, Any]) -> Tuple[float, float]:
    """计算人脸中心坐标（用于自动定位，不依赖固定座位）"""
    left = _safe_float(location.get("left"))
    top = _safe_float(location.get("top"))
    width = _safe_float(location.get("width"))
    height = _safe_float(location.get("height"))
    return (left + width / 2.0, top + height / 2.0)


def _prob_to_interval(prob: float) -> Dict[str, float]:
    """将置信度转为置信区间（±5%）"""
    p = max(0.0, min(1.0, float(prob or 0)))
    low = max(0.0, p - 0.05)
    high = min(1.0, p + 0.05)
    return {"center": p, "low": low, "high": high}


def classify_psych_status(emotion_type: str, emotion_prob: float) -> Dict[str, Any]:
    """
    输出：
    - status: good / watch / focus
    - reason: 用于老师理解的简要原因
    """
    p = float(emotion_prob or 0.0)
    negative_high = {"angry", "disgust", "fear", "sad"}
    negative_mid = {"pouty"}

    if emotion_type in negative_high and p >= 0.5:
        return {"status": "focus", "status_cn": "需要重点关注", "reason": "负面情绪显著"}
    if emotion_type in negative_high and p >= 0.3:
        return {"status": "watch", "status_cn": "需要关注", "reason": "存在负面情绪倾向"}
    if emotion_type in negative_mid and p >= 0.4:
        return {"status": "watch", "status_cn": "需要关注", "reason": "表现出不满/抵触"}
    if emotion_type == "grimace" and p >= 0.6:
        return {"status": "watch", "status_cn": "需要关注", "reason": "表情异常较明显"}
    return {"status": "good", "status_cn": "状态良好", "reason": "情绪较平稳"}


def enrich_faces_with_seats(raw_result: Dict[str, Any], seat_layout: Dict[str, Any]) -> Dict[str, Any]:
    """人脸分析增强：只使用人脸坐标定位，不依赖固定座位"""
    if raw_result.get("error_msg") != "SUCCESS":
        return {"error": raw_result.get("error_msg", "检测失败")}

    result = raw_result.get("result", {}) or {}
    face_list = result.get("face_list", []) or []

    enriched_faces: List[Dict[str, Any]] = []
    for face in face_list:
        location = face.get("location", {}) or {}
        emotion = face.get("emotion", {}) or {}
        emotion_type = emotion.get("type", "unknown")
        emotion_prob = _safe_float(emotion.get("probability"), 0.0)
        psych = classify_psych_status(emotion_type, emotion_prob)

        # 只保存人脸坐标，不分配固定座位
        face_center = {"x": _face_center(location)[0], "y": _face_center(location)[1]}
        enriched_faces.append({
            "emotion_type": emotion_type,
            "emotion_cn": EMOTION_MAP.get(emotion_type, emotion_type),
            "secondary_emotion_cn": SECONDARY_EMOTION_MAP.get(emotion_type, EMOTION_MAP.get(emotion_type, emotion_type)),
            "emotion_prob": emotion_prob,
            "emotion_interval": _prob_to_interval(emotion_prob),
            "location": {
                "left": _safe_float(location.get("left")),
                "top": _safe_float(location.get("top")),
                "width": _safe_float(location.get("width")),
                "height": _safe_float(location.get("height")),
                "rotation": _safe_float(location.get("rotation"))
            },
            "face_center": face_center,
            "psych": psych
        })

    stats: Dict[str, Any] = {
        "total_faces": len(enriched_faces),
        "emotion_counts": {},
        "secondary_emotion_counts": {},
        "status_counts": {"状态良好": 0, "需要关注": 0, "需要重点关注": 0},
        "focus_students": []
    }

    for f in enriched_faces:
        emo = f.get("emotion_cn", "未知")
        sec = f.get("secondary_emotion_cn", emo)
        stats["emotion_counts"][emo] = stats["emotion_counts"].get(emo, 0) + 1
        stats["secondary_emotion_counts"][sec] = stats["secondary_emotion_counts"].get(sec, 0) + 1
        status_cn = (f.get("psych") or {}).get("status_cn", "状态良好")
        stats["status_counts"][status_cn] = stats["status_counts"].get(status_cn, 0) + 1

        if status_cn == "需要重点关注":
            stats["focus_students"].append({
                "face_center": f.get("face_center"),
                "emotion": f.get("secondary_emotion_cn"),
                "emotion_prob": f.get("emotion_prob"),
                "reason": (f.get("psych") or {}).get("reason")
            })

    return {
        "faces": enriched_faces,
        "stats": stats,
        "seat_layout_meta": {
            "path": SEAT_LAYOUT_PATH,
            "image_size": (seat_layout or {}).get("image_size")
        }
    }

def get_access_token():
    """获取百度API访问令牌"""
    auth_url = 'https://aip.baidubce.com/oauth/2.0/token'
    params = {
        'grant_type': 'client_credentials',
        'client_id': API_KEY,
        'client_secret': SECRET_KEY
    }
    
    response = requests.post(auth_url, params=params)
    if response:
        result = response.json()
        return result.get('access_token')
    return None

def detect_face(image_path):
    import time
    timings = {}
    t0 = time.time()

    with open(image_path, 'rb') as f:
        image_base64 = base64.b64encode(f.read()).decode('utf-8')
    timings['1.read+b64'] = time.time() - t0
    img_size_kb = len(image_base64) * 3 // 4 // 1024

    t = time.time()
    access_token = get_access_token()
    timings['2.access_token'] = time.time() - t
    if not access_token:
        print(f'[detect_face] sizes={img_size_kb}KB timings={timings}')
        return {'error': '获取access_token失败'}

    request_url = "https://aip.baidubce.com/rest/2.0/face/v3/detect"
    max_face_num = int(os.environ.get('MAX_FACE_NUM', '20'))
    max_face_num = max(1, min(20, max_face_num))
    params = {
        'image': image_base64,
        'image_type': 'BASE64',
        'face_field': 'gender,glasses,eye_status,emotion,face_type,mask,landmark,faceshape,facetype',
        'max_face_num': max_face_num
    }
    request_url = request_url + "?access_token=" + access_token
    headers = {'content-type': 'application/json'}

    t = time.time()
    response = requests.post(request_url, data=params, headers=headers)
    timings['3.baidu_api'] = time.time() - t
    if not response:
        print(f'[detect_face] sizes={img_size_kb}KB timings={timings}')
        return {'error': '请求失败'}
    result = response.json()

    t = time.time()
    try:
        from local_face import override_emotion_with_local
        override_emotion_with_local(image_path, result)
    except Exception as e:
        print('emotion override skipped:', e)
    timings['4.emotion_override'] = time.time() - t

    timings['TOTAL'] = time.time() - t0
    face_num = (result.get('result') or {}).get('face_num', 0)
    print(f'[detect_face] img={img_size_kb}KB faces={face_num} timings={ {k: f"{v:.2f}s" for k,v in timings.items()} }')
    return result

def parse_face_result(result):
    """解析人脸检测结果为中文"""
    if result.get('error_msg') != 'SUCCESS':
        return {'error': result.get('error_msg', '检测失败')}
    
    face_list = result.get('result', {}).get('face_list', [])
    if not face_list:
        return {'error': '未检测到人脸'}
    
    faces = []
    for face in face_list:
        face_info = {}
        
        # 性别
        gender = face.get('gender', {})
        gender_type = gender.get('type', 'unknown')
        face_info['gender'] = GENDER_MAP.get(gender_type, gender_type)
        face_info['gender_prob'] = gender.get('probability', 0)
        
        # 眼镜
        glasses = face.get('glasses', {})
        glasses_type = glasses.get('type', 'unknown')
        face_info['glasses'] = GLASSES_MAP.get(glasses_type, glasses_type)
        face_info['glasses_prob'] = glasses.get('probability', 0)
        
        # 双眼状态
        eye_status = face.get('eye_status', {})
        face_info['left_eye'] = eye_status.get('left_eye', 0)
        face_info['right_eye'] = eye_status.get('right_eye', 0)
        
        # 情绪
        emotion = face.get('emotion', {})
        emotion_type = emotion.get('type', 'unknown')
        face_info['emotion'] = EMOTION_MAP.get(emotion_type, emotion_type)
        face_info['emotion_prob'] = emotion.get('probability', 0)
        
        # 脸型
        face_shape = face.get('face_shape', {})
        shape_type = face_shape.get('type', 'unknown')
        face_info['face_shape'] = FACE_SHAPE_MAP.get(shape_type, shape_type)
        face_info['face_shape_prob'] = face_shape.get('probability', 0)
        
        # 人脸类型
        face_type = face.get('face_type', {})
        face_type_val = face_type.get('type', 'unknown')
        face_info['face_type'] = FACE_TYPE_MAP.get(face_type_val, face_type_val)
        face_info['face_type_prob'] = face_type.get('probability', 0)
        
        # 口罩
        mask = face.get('mask', {})
        mask_type = mask.get('type', -1)
        face_info['mask'] = MASK_MAP.get(mask_type, '未知')
        face_info['mask_prob'] = mask.get('probability', 0)
        
        # 位置信息
        location = face.get('location', {})
        face_info['location'] = {
            'left': location.get('left', 0),
            'top': location.get('top', 0),
            'width': location.get('width', 0),
            'height': location.get('height', 0),
            'rotation': location.get('rotation', 0)
        }
        
        # 关键点
        landmark = face.get('landmark', [])
        if landmark:
            landmark_names = ['左眼中心', '右眼中心', '鼻尖', '嘴中心']
            face_info['landmark'] = []
            for j, point in enumerate(landmark):
                name = landmark_names[j] if j < len(landmark_names) else f'点{j+1}'
                face_info['landmark'].append({
                    'name': name,
                    'x': point.get('x', 0),
                    'y': point.get('y', 0)
                })
        
        faces.append(face_info)
    
    return {'faces': faces, 'total': len(faces)}

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('detect'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user = None
        if USE_MYSQL:
            user = get_user_by_username(username)
        if not user and username in USERS_FALLBACK and USERS_FALLBACK[username]['password'] == password:
            user = USERS_FALLBACK[username]
        elif user and user.get('password') != password:
            user = None
        if user:
            session['username'] = username
            session['name'] = user.get('name') or username
            session['role'] = user.get('role') or 'user'
            flash('登录成功！', 'success')
            return redirect(url_for('detect'))
        flash('用户名或密码错误！', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        name = request.form.get('name', '').strip() or username
        if not username or not password:
            flash('请填写用户名和密码', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('密码至少6位', 'error')
            return render_template('register.html')
        if USE_MYSQL:
            if get_user_by_username(username):
                flash('用户名已存在', 'error')
                return render_template('register.html')
            if create_user(username, password, name):
                flash('注册成功，请登录', 'success')
                return redirect(url_for('login'))
            flash('注册失败，请重试', 'error')
        else:
            flash('当前未启用数据库，无法注册', 'error')
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('login'))


@app.route('/api/seat_layout', methods=['GET'])
def api_seat_layout():
    if 'username' not in session:
        return jsonify({'error': '未登录'}), 401
    return jsonify(SEAT_LAYOUT)


@app.route('/api/last_analysis', methods=['GET'])
def api_last_analysis():
    """获取最近一次分析（兼容旧前端）"""
    if 'username' not in session:
        return jsonify({'error': '未登录'}), 401
    username = session.get('username')
    if not USE_MYSQL or not username:
        return jsonify({'ok': True, 'has_data': False})
    records = load_analysis_list(username, limit=1)
    if not records:
        return jsonify({'ok': True, 'has_data': False})
    rec = load_analysis_by_id(records[0]['id'], username)
    if not rec or not rec.get('payload_json'):
        return jsonify({'ok': True, 'has_data': False})
    payload = rec['payload_json']
    payload['image_url'] = rec.get('image_path')
    payload['record_id'] = rec['id']
    return jsonify({'ok': True, 'has_data': True, **payload})


def _format_datetime(dt) -> str:
    """格式化为 年月日时分秒"""
    if dt is None:
        return '-'
    if hasattr(dt, 'strftime'):
        return dt.strftime('%Y年%m月%d日 %H:%M:%S')
    s = str(dt).replace('T', ' ')[:19]
    if len(s) >= 19:
        y, m, d = s[0:4], s[5:7], s[8:10]
        h, i, sec = s[11:13], s[14:16], s[17:19]
        return f'{y}年{m}月{d}日 {h}:{i}:{sec}'
    return s


@app.route('/api/analysis_list', methods=['GET'])
def api_analysis_list():
    """获取分析记录列表（持久化，支持查看历史）"""
    if 'username' not in session:
        return jsonify({'error': '未登录'}), 401
    username = session.get('username')
    if not USE_MYSQL:
        return jsonify({'ok': True, 'list': []})
    records = load_analysis_list(username, limit=200)
    for r in records:
        r['created_at_fmt'] = _format_datetime(r.get('created_at'))
    return jsonify({'ok': True, 'list': records})


@app.route('/api/analysis/<int:record_id>', methods=['GET'])
def api_analysis_detail(record_id):
    """获取单条分析详情（含图片）"""
    if 'username' not in session:
        return jsonify({'error': '未登录'}), 401
    username = session.get('username')
    if not USE_MYSQL:
        return jsonify({'error': '未启用数据库'}), 400
    rec = load_analysis_by_id(record_id, username)
    if not rec:
        return jsonify({'error': '记录不存在'}), 404
    payload = rec.get('payload_json') or {}
    payload['image_url'] = rec.get('image_path')
    payload['record_id'] = rec['id']
    payload['created_at'] = rec.get('created_at')
    return jsonify({'ok': True, **payload})


@app.route('/api/analysis/delete', methods=['POST'])
def api_analysis_delete():
    """删除单条或批量删除分析记录"""
    if 'username' not in session:
        return jsonify({'error': '未登录'}), 401
    username = session.get('username')
    if not USE_MYSQL:
        return jsonify({'error': '未启用数据库'}), 400
    data = request.get_json() or {}
    ids = data.get('ids') or data.get('id')
    if ids is None:
        return jsonify({'error': '缺少 ids 或 id'}), 400
    if isinstance(ids, int):
        ids = [ids]
    ids = [int(x) for x in ids if x is not None]
    if not ids:
        return jsonify({'error': '无效的 id'}), 400
    n = delete_analysis_batch(ids, username)
    return jsonify({'ok': True, 'deleted': n})


@app.route('/stats', methods=['GET'])
def stats():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('stats.html', username=session.get('name'))

@app.route('/detect', methods=['GET', 'POST'])
def detect():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # 如果是AJAX请求（通过X-Requested-With头判断）
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({'error': '请选择图片文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '未选择文件'}), 400
        
        # 保存上传的图片
        ext = os.path.splitext(file.filename)[1]
        filename = f'{uuid.uuid4().hex}{ext}'
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # 调用百度API进行人脸检测
            raw_result = detect_face(filepath)
            print(raw_result)
            # 如果有错误
            if raw_result.get('error_msg') != 'SUCCESS':
                return jsonify({'error': raw_result.get('error_msg', '检测失败')}), 400

            enriched = enrich_faces_with_seats(raw_result, SEAT_LAYOUT)
            if "error" in enriched:
                return jsonify({"error": enriched["error"]}), 400

            # 图片路径（持久保存，供统计看板查看）
            image_url = f'static/uploads/{filename}'

            payload = {
                "raw": raw_result,
                "faces": enriched.get("faces", []),
                "stats": enriched.get("stats", {}),
                "seat_layout_meta": enriched.get("seat_layout_meta", {}),
                "image_url": image_url
            }

            username = session.get("username")
            if username and USE_MYSQL:
                save_analysis(username, payload, image_path=image_url)

            return jsonify(payload)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    result_data = None
    image_url = None
    
    if request.method == 'POST':
        # 检查是否有文件上传
        if 'file' not in request.files:
            flash('请选择图片文件', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('未选择文件', 'error')
            return redirect(request.url)
        
        # 保存上传的图片
        if file:
            # 生成唯一文件名
            ext = os.path.splitext(file.filename)[1]
            filename = f'{uuid.uuid4().hex}{ext}'
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            image_url = f'static/uploads/{filename}'
            
            # 调用百度API进行人脸检测
            raw_result = detect_face(filepath)
            # 非 AJAX：继续走原来的中文解析，同时也尽量补齐统计（用于模板扩展）
            result_data = parse_face_result(raw_result)
            enriched = enrich_faces_with_seats(raw_result, SEAT_LAYOUT)
            if isinstance(result_data, dict) and "error" not in result_data:
                result_data["seat_analysis"] = enriched if isinstance(enriched, dict) and "error" not in enriched else None
                if USE_MYSQL and session.get("username"):
                    payload = {
                        "raw": raw_result,
                        "faces": enriched.get("faces", []) if isinstance(enriched, dict) else [],
                        "stats": enriched.get("stats", {}) if isinstance(enriched, dict) else {},
                        "seat_layout_meta": enriched.get("seat_layout_meta", {}) if isinstance(enriched, dict) else {},
                        "image_url": image_url
                    }
                    save_analysis(session["username"], payload, image_path=image_url)
            
            # 如果有错误
            if 'error' in result_data:
                flash(result_data['error'], 'error')
                result_data = None
    
    return render_template('detect.html', 
                           result=result_data, 
                           image_url=image_url,
                           username=session.get('name'))

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)