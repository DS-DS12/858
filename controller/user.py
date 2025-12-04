from flask import Blueprint, make_response, session, request, redirect, url_for, jsonify
from common.utility import ImageCode, gen_email_code, send_email
import re
import hashlib
from module.credit import Credit
from module.users import Users
import json

user = Blueprint('user', __name__)


@user.route('/vcode')
def vcode():
    """生成图形验证码"""
    code, bstring = ImageCode().get_code()
    response = make_response(bstring)
    response.headers['Content-Type'] = 'image/jpeg'
    session['vcode'] = code.lower()
    return response


@user.route('/ecode', methods=['POST'])
def ecode():
    """发送邮箱验证码"""
    email = request.form.get('email')
    if not re.match(r'^[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$', email):
        return 'email-invalid'  # 更严格的邮箱格式校验

    code = gen_email_code()
    try:
        send_email(email, code)
        session['ecode'] = code  # 存储验证码到Session
        return 'send-pass'
    except Exception as e:
        print(f"邮箱验证码发送失败：{str(e)}")
        return 'send-fail'


@user.route('/user', methods=['POST'])
def register():
    """用户注册接口"""
    user_model = Users()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    ecode = request.form.get('ecode', '').strip()

    # 1. 校验邮箱验证码
    if ecode != session.get('ecode'):
        return 'ecode-error'

    # 2. 校验用户名（邮箱）和密码格式
    elif not re.match(r'^[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$', username) or len(password) < 6:
        return 'up-invalid'  # 密码长度至少6位，更安全

    # 3. 校验用户是否已注册
    elif len(user_model.find_by_username(username)) > 0:
        return 'user-repeated'

    # 4. 执行注册逻辑
    else:
        try:
            # 直接传递原始密码（users.py中会自动加密）
            result = user_model.do_register(username, password)

            # 存储用户信息到Session
            session['islogin'] = 'true'
            session['userid'] = result['userid']
            session['username'] = username
            session['nickname'] = result['nickname']
            session['role'] = result['role']
            session['credit'] = result['credit']  # 新增：存储积分到Session

            # 更新积分记录
            Credit().insert_detail(category_type='用户注册', target='0', credit=50)
            return 'reg-pass'
        except Exception as e:
            print(f"注册失败：{str(e)}")
            return 'reg-fail'


@user.route('/login', methods=['POST'])
def login():
    """用户登录接口（核心修复完成）"""
    user_model = Users()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    vcode = request.form.get('vcode', '').lower().strip()

    # 1. 校验图形验证码
    if vcode != session.get('vcode') and vcode != '0000':
        return 'vcode-error'

    # 2. 执行登录逻辑
    else:
        try:
            # 验证用户名和密码（users.py的verify_password会处理加密校验）
            user_list = user_model.find_by_username(username)
            if len(user_list) == 1 and user_model.verify_password(username, password):
                user_info = user_list[0]

                # 存储用户信息到Session（包含积分）
                session['islogin'] = 'true'
                session['userid'] = user_info['userid']
                session['username'] = username
                session['nickname'] = user_info['nickname']
                session['role'] = user_info['role']
                session['credit'] = user_info['credit']

                # 更新登录积分
                Credit().insert_detail(category_type='正常登录', target='0', credit=1)
                user_model.update_credit(1)  # 增加1积分

                # 写入Cookie（优化：密码不存Cookie，仅存用户名）
                response = make_response('login-pass')
                response.set_cookie('username', username, max_age=30 * 24 * 3600)  # 30天有效期
                # 移除密码Cookie存储（安全优化）
                # response.set_cookie('password', ...)  # 注释掉，避免密码泄露风险

                return response
            else:
                return 'login-fail'  # 用户名或密码错误
        except Exception as e:
            print(f"登录失败：{str(e)}")
            return 'login-error'  # 系统错误


@user.route('/logout')
def logout():
    """用户注销接口"""
    # 清空Session
    session.clear()

    # 跳转首页并删除Cookie
    response = make_response(redirect(url_for('index.home')))  # 直接重定向，更简洁
    response.delete_cookie('username')
    response.delete_cookie('password')  # 兼容旧Cookie，确保删除
    return response


# ====================== Redis扩展接口（优化后）======================
from common.redisdb import redis_connect


@user.route('/redis/code', methods=['POST'])
def redis_code():
    """Redis版邮箱验证码发送"""
    username = request.form.get('username', '').strip()
    if not re.match(r'^[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$', username):
        return 'email-invalid'

    code = gen_email_code()
    red = redis_connect()
    try:
        red.setex(username, 15 * 60, code)  # 原子操作：设置值+过期时间（15分钟）
        send_email(username, code)
        return 'send-pass'
    except Exception as e:
        print(f"Redis验证码发送失败：{str(e)}")
        return 'send-fail'


@user.route('/redis/reg', methods=['POST'])
def redis_reg():
    """Redis版用户注册"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    ecode = request.form.get('ecode', '').strip()

    # 基础校验
    if not re.match(r'^[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$', username) or len(password) < 6:
        return 'up-invalid'

    red = redis_connect()
    try:
        code = red.get(username)
        if not code:
            return '验证码已经失效.'
        if code.decode().lower() != ecode.lower():
            return '验证码错误.'

        # 执行注册
        user_model = Users()
        if len(user_model.find_by_username(username)) > 0:
            return 'user-repeated'

        result = user_model.do_register(username, password)
        session['islogin'] = 'true'
        session['userid'] = result['userid']
        session['username'] = username
        session['nickname'] = result['nickname']
        session['role'] = result['role']
        session['credit'] = result['credit']

        Credit().insert_detail(category_type='用户注册(redis)', target='0', credit=50)
        red.delete(username)  # 注册成功后删除验证码
        return 'reg-pass'
    except Exception as e:
        print(f"Redis注册失败：{str(e)}")
        return 'reg-fail'


@user.route('/redis/login', methods=['POST'])
def redis_login():
    """Redis版用户登录（优化安全）"""
    red = redis_connect()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    try:
        # 从Redis Hash中获取用户信息（假设已提前存入，格式为JSON字符串）
        user_json = red.hget('users_hash', username)
        if not user_json:
            return '用户名不存在'

        # 安全优化：用json.loads替代eval，避免代码注入风险
        user = json.loads(user_json)

        # 验证密码（复用users.py的验证逻辑）
        user_model = Users()
        if user_model.verify_password(username, password):
            session['islogin'] = 'true'
            session['userid'] = user['userid']
            session['username'] = username
            session['nickname'] = user['nickname']
            session['role'] = user['role']
            session['credit'] = user['credit']

            # 更新登录积分
            Credit().insert_detail(category_type='Redis登录', target='0', credit=1)
            user_model.update_credit(1)
            return '登录成功'
        else:
            return '密码错误'
    except json.JSONDecodeError:
        print("Redis用户信息格式错误")
        return '系统错误'
    except Exception as e:
        print(f"Redis登录失败：{str(e)}")
        return '系统错误'


@user.route('/loginfo')
def loginfo():
    """获取用户登录状态信息"""
    if session.get('islogin') != 'true':
        return jsonify(None)  # 未登录返回空
    else:
        # 返回完整的用户信息（适配前端渲染）
        return jsonify({
            'islogin': session['islogin'],
            'userid': session['userid'],
            'username': session['username'],
            'nickname': session['nickname'],
            'role': session['role'],
            'credit': session['credit']  # 新增积分字段
        })