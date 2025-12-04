import random
import string
import time
import re
import requests
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageFont, ImageDraw
from smtplib import SMTP_SSL
from email.mime.text import MIMEText
from email.header import Header

# ====================== 验证码相关 ======================
class ImageCode:
    # 生成用于绘制字符串的随机颜色
    def rand_color(self):
        red = random.randint(32, 200)
        green = random.randint(22, 255)
        blue = random.randint(0, 200)
        return red, green, blue

    # 生成4位随机字符串（字母+数字）
    def gen_text(self):
        return ''.join(random.sample(string.ascii_letters + string.digits, 4))

    # 画干扰线（增强验证码安全性）
    def draw_lines(self, draw, num, width, height):
        for _ in range(num):
            x1 = random.randint(0, width // 2)
            y1 = random.randint(0, height // 2)
            x2 = random.randint(width // 2, width)
            y2 = random.randint(height // 2, height)
            draw.line(((x1, y1), (x2, y2)), fill=self.rand_color(), width=2)

    # 绘制验证码图片
    def draw_verify_code(self):
        code = self.gen_text()
        width, height = 120, 50  # 图片尺寸
        im = Image.new('RGB', (width, height), 'white')  # 白色背景

        # 加载字体（兼容无自定义字体场景）
        try:
            font = ImageFont.truetype('static/font/arial.ttf', 40)
        except:
            font = ImageFont.load_default(size=36)

        draw = ImageDraw.Draw(im)
        # 绘制验证码字符（随机位置偏移）
        for i in range(4):
            x = 5 + random.randint(-3, 3) + 23 * i
            y = 5 + random.randint(-3, 3)
            draw.text((x, y), code[i], fill=self.rand_color(), font=font)

        # 绘制干扰线
        self.draw_lines(draw, 4, width, height)
        return im, code

    # 生成图片验证码（返回字节流和验证码字符串）
    def get_code(self):
        image, code = self.draw_verify_code()
        buf = BytesIO()
        image.save(buf, 'jpeg', quality=85)  # 优化图片质量
        buf.seek(0)
        return code, buf.getvalue()

# ====================== 邮箱相关 ======================
def send_email(receiver, ecode):
    """发送QQ邮箱验证码（需替换为自己的邮箱配置）"""
    sender = 'WoniuNote <15903523@qq.com>'  # 发件人（邮箱+签名）
    # 邮件内容（HTML格式）
    content = f"""
    <br/>欢迎注册蜗牛笔记博客系统账号！<br/><br/>
    您的邮箱验证码为：<span style='color: red; font-size: 24px; font-weight: bold;'>{ecode}</span><br/><br/>
    验证码有效期为15分钟，请尽快复制到注册窗口完成注册。<br/>
    若不是您本人操作，请忽略此邮件，感谢您的支持！
    """
    # 构建邮件对象
    message = MIMEText(content, 'html', 'utf-8')
    message['Subject'] = Header('蜗牛笔记 - 注册验证码', 'utf-8')  # 邮件标题
    message['From'] = sender
    message['To'] = receiver

    try:
        # 连接QQ邮件服务器（SSL加密）
        smtpObj = SMTP_SSL('smtp.qq.com', 465)
        # 登录（用户名+授权码，授权码需在QQ邮箱设置中获取）
        smtpObj.login(user='15903523@qq.com', password='uczmmmqvpxwjbjaf')
        # 发送邮件
        smtpObj.sendmail(sender, receiver, str(message))
        smtpObj.quit()
        return True  # 发送成功
    except Exception as e:
        print(f"邮件发送失败：{str(e)}")
        return False  # 发送失败

def gen_email_code():
    """生成6位随机邮箱验证码（字母+数字）"""
    return ''.join(random.sample(string.ascii_letters + string.digits, 6))

# ====================== 数据格式转换 ======================
def model_list(result):
    """将SQLAlchemy单个模型查询结果转换为字典列表（支持JSON序列化）"""
    data_list = []
    for row in result:
        item = {}
        for k, v in row.__dict__.items():
            if not k.startswith('_sa_instance_state'):  # 排除SQLAlchemy内部属性
                # datetime类型转换为字符串
                if isinstance(v, datetime):
                    v = v.strftime('%Y-%m-%d %H:%M:%S')
                item[k] = v
        data_list.append(item)
    return data_list

def model_join_list(result):
    """将SQLAlchemy连接查询结果（两张表）转换为字典列表"""
    data_list = []
    for obj1, obj2 in result:
        item = {}
        # 处理第一张表数据
        for k1, v1 in obj1.__dict__.items():
            if not k1.startswith('_sa_instance_state') and k1 not in item:
                if isinstance(v1, datetime):
                    v1 = v1.strftime('%Y-%m-%d %H:%M:%S')
                item[k1] = v1
        # 处理第二张表数据（避免字段冲突）
        for k2, v2 in obj2.__dict__.items():
            if not k2.startswith('_sa_instance_state') and k2 not in item:
                if isinstance(v2, datetime):
                    v2 = v2.strftime('%Y-%m-%d %H:%M:%S')
                item[k2] = v2
        data_list.append(item)
    return data_list

# ====================== 图片处理 ======================
def compress_image(source, dest, width):
    """压缩图片（按宽度等比例缩放）"""
    try:
        im = Image.open(source)
        x, y = im.size
        # 仅当宽度超过指定值时缩放
        if x > width:
            ys = int(y * width / x)
            xs = width
            # 高质量缩放（ANTIALIAS抗锯齿）
            im = im.resize((xs, ys), Image.Resampling.LANCZOS)  # 兼容PIL 9.1.0+
        # 保存图片（80%质量，平衡清晰度和大小）
        im.save(dest, quality=80, optimize=True)
        return True
    except Exception as e:
        print(f"图片压缩失败：{str(e)}")
        return False

def parse_image_url(content):
    """从HTML内容中解析图片URL（排除GIF格式）"""
    if not content:
        return []
    # 正则匹配<img src="url">格式的图片地址
    temp_list = re.findall(r'<img[^>]*src="([^"]+)"', content, re.IGNORECASE)
    # 过滤GIF图片和空URL
    url_list = [url.strip() for url in temp_list if url.strip() and not url.strip().lower().endswith('.gif')]
    return url_list

def download_image(url, dest):
    """下载远程图片到本地"""
    try:
        # 设置请求超时（避免长时间阻塞）
        response = requests.get(url, timeout=10, stream=True)
        response.raise_for_status()  # 抛出HTTP错误
        # 二进制写入文件
        with open(dest, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
        return True
    except Exception as e:
        print(f"图片下载失败：{str(e)}")
        return False

def generate_thumb(url_list):
    """生成文章缩略图（优先使用本地上传图片，无则下载网络图片）"""
    if not url_list:
        return 'default_thumb.jpg'  # 默认缩略图（需提前放置在thumb目录）

    # 1. 优先处理本地上传图片（以/upload/开头）
    for url in url_list:
        if url.startswith('/upload/'):
            filename = url.split('/')[-1]
            # 本地图片路径（根据项目目录结构调整）
            source_path = f'./resource/upload/{filename}'
            dest_path = f'./resource/thumb/{filename}'
            # 压缩生成缩略图
            if compress_image(source_path, dest_path, 400):
                return filename
            continue

    # 2. 无本地图片时，下载网络图片生成缩略图
    url = url_list[0]
    suffix = url.split('.')[-1] if '.' in url else 'jpg'
    # 限制后缀名（避免非法文件）
    suffix = suffix.lower() if suffix.lower() in ['jpg', 'jpeg', 'png', 'webp'] else 'jpg'
    # 生成时间戳文件名（避免重复）
    thumbname = f'{time.strftime("%Y%m%d_%H%M%S")}.{suffix}'
    # 下载路径和缩略图路径
    download_path = f'./resource/download/{thumbname}'
    dest_path = f'./resource/thumb/{thumbname}'

    # 下载并压缩图片
    if download_image(url, download_path) and compress_image(download_path, dest_path, 400):
        return thumbname
    else:
        return 'default_thumb.jpg'  # 失败时返回默认缩略图

# ====================== 测试代码（可选） ======================
if __name__ == '__main__':
    # 测试验证码生成
    # img_code = ImageCode()
    # code, img_bytes = img_code.get_code()
    # print(f"验证码：{code}")

    # 测试邮箱发送（替换为测试邮箱）
    # ecode = gen_email_code()
    # print(f"邮箱验证码：{ecode}")
    # send_email('test@example.com', ecode)

    # 测试图片URL解析和缩略图生成
    test_content = '''
    <p><img src="/upload/202405.jpg" alt="本地图片"/></p>
    <p><img src="http://www.example.com/image.png" title="网络图片"/></p>
    <p><img src="http://example.com/anim.gif" alt="GIF图片（会被过滤）"/></p>
    '''
    url_list = parse_image_url(test_content)
    print(f"解析到的图片URL：{url_list}")
    thumb = generate_thumb(url_list)
    print(f"生成的缩略图：{thumb}")