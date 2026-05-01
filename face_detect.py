# encoding:utf-8
import base64
import requests
import json

'''
人脸检测与属性分析 - 百度AI开放平台
'''

# 百度API配置
# 请替换为你的API Key和Secret Key
API_KEY = 'ql21uVftf13jXL0FGEkFCCzH'
SECRET_KEY = '81L7L2FRTMcEkuMr3opuyx8cccXsEw20'

# 图片路径
IMAGE_PATH = '1.jpg'

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

def get_access_token():
    """
    获取百度API访问令牌
    """
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
    """
    人脸检测与属性分析
    """
    # 读取图片并进行Base64编码
    with open(image_path, 'rb') as f:
        image_base64 = base64.b64encode(f.read()).decode('utf-8')
    
    # 获取access_token
    access_token = get_access_token()
    if not access_token:
        print("获取access_token失败，请检查API_KEY和SECRET_KEY")
        return
    
    # 调用人脸检测API
    request_url = "https://aip.baidubce.com/rest/2.0/face/v3/detect"
    # 百度接口默认最多返回 1 张人脸；提高上限以尽量返回全部脸（最大 20）
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
    
    response = requests.post(request_url, data=params, headers=headers)
    
    if response:
        result = response.json()
        print("=" * 50)
        print("API原始返回结果:")
        print("=" * 50)
        print(json.dumps(result, indent=4, ensure_ascii=False))
        
        # 解析并显示关键信息
        if result.get('error_msg') == 'SUCCESS':
            face_list = result.get('result', {}).get('face_list', [])
            if face_list:
                print("\n" + "=" * 50)
                print("人脸检测结果（中文）")
                print("=" * 50)
                for i, face in enumerate(face_list, 1):
                    print(f"\n【人脸 {i}】")
                    location = face.get('location', {})
                    print(f"  ▼ 位置信息:")
                    print(f"    左上角坐标: ({location.get('left')}, {location.get('top')})")
                    print(f"    宽度: {location.get('width')}, 高度: {location.get('height')}")
                    print(f"    旋转角度: {location.get('rotation')}度")
                    
                    # 性别
                    gender = face.get('gender', {})
                    gender_type = gender.get('type', 'unknown')
                    gender_prob = gender.get('probability', 0)
                    gender_cn = GENDER_MAP.get(gender_type, gender_type)
                    print(f"    性别: {gender_cn} (置信度: {gender_prob:.2%})")
                    
                    # 眼镜
                    glasses = face.get('glasses', {})
                    glasses_type = glasses.get('type', 'unknown')
                    glasses_prob = glasses.get('probability', 0)
                    glasses_cn = GLASSES_MAP.get(glasses_type, glasses_type)
                    print(f"    眼镜: {glasses_cn} (置信度: {glasses_prob:.2%})")
                    
                    # 双眼状态
                    eye_status = face.get('eye_status', {})
                    left_eye = eye_status.get('left_eye', 0)
                    right_eye = eye_status.get('right_eye', 0)
                    left_eye_status = "睁开" if left_eye > 0.5 else "闭合"
                    right_eye_status = "睁开" if right_eye > 0.5 else "闭合"
                    print(f"    左眼状态: {left_eye_status} ({left_eye:.2f})")
                    print(f"    右眼状态: {right_eye_status} ({right_eye:.2f})")
                    
                    # 情绪
                    emotion = face.get('emotion', {})
                    emotion_type = emotion.get('type', 'unknown')
                    emotion_prob = emotion.get('probability', 0)
                    emotion_cn = EMOTION_MAP.get(emotion_type, emotion_type)
                    print(f"    情绪: {emotion_cn} (置信度: {emotion_prob:.2%})")
                    
                    # 脸型
                    face_shape = face.get('face_shape', {})
                    shape_type = face_shape.get('type', 'unknown')
                    print(f"    脸型: {shape_type}")
                    
                    # 人脸类型
                    face_type = face.get('face_type', {})
                    face_type_val = face_type.get('type', 'unknown')
                    face_type_prob = face_type.get('probability', 0)
                    face_type_cn = FACE_TYPE_MAP.get(face_type_val, face_type_val)
                    print(f"    人脸类型: {face_type_cn} (置信度: {face_type_prob:.2%})")
                    
                    # 口罩
                    mask = face.get('mask', {})
                    mask_type = mask.get('type', -1)
                    mask_prob = mask.get('probability', 0)
                    mask_cn = MASK_MAP.get(mask_type, '未知')
                    print(f"    口罩: {mask_cn} (置信度: {mask_prob:.2%})")
                    
                    # 关键点
                    landmark = face.get('landmark', [])
                    if landmark:
                        print(f"  ▼ 关键点坐标:")
                        landmark_names = ['左眼中心', '右眼中心', '鼻尖', '嘴中心']
                        for j, point in enumerate(landmark):
                            name = landmark_names[j] if j < len(landmark_names) else f"点{j+1}"
                            print(f"    {name}: ({point.get('x')}, {point.get('y')})")
            else:
                print("\n未检测到人脸")
        else:
            print(f"\n检测失败: {result.get('error_msg')}")

if __name__ == '__main__':
    # 检测人脸
    detect_face(IMAGE_PATH)