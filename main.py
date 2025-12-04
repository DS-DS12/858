from flask import Flask, abort, render_template, request, session
import os
from flask_sqlalchemy import SQLAlchemy
import pymysql

# 解决 MySQLdb 缺失问题
pymysql.install_as_MySQLdb()

# 1. 先创建 SQLAlchemy 实例（不直接绑定 app，延迟初始化）
db = SQLAlchemy()

# 创建 Flask 应用实例
app = Flask(
    __name__,
    template_folder='template',
    static_url_path='/',
    static_folder='resource'
)

# 应用配置
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:6666@localhost:3306/woniunote?charset=utf8'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_POOL_SIZE'] = 100

# 2. 关键修改：延迟绑定 app，确保 db 与当前 app 实例唯一关联
db.init_app(app)

# -------------------------- 关键修改：添加表创建逻辑（可选，首次运行用）--------------------------
# 首次运行时，取消注释以下代码，创建数据库表（创建后注释掉）
# with app.app_context():
#     db.create_all()  # 自动创建所有表（需确保 MySQL 中 woniunote 数据库已存在）

# -------------------------- 其他代码保持不变 --------------------------
# 404 错误页面
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error-404.html')

# 500 错误页面
@app.errorhandler(500)
def server_error(e):
    return render_template('error-500.html')

# 全局拦截器（自动登录）- 动态导入 Users 类
@app.before_request
def before():
    url = request.path
    pass_list = ['/user', '/login', '/logout']

    # 放行白名单和静态资源
    if url in pass_list or url.endswith('.js') or url.endswith('.jpg'):
        return

    # 未登录时尝试自动登录 - 动态导入 Users（打破循环导入）
    elif session.get('islogin') is None:
        username = request.cookies.get('username')
        password = request.cookies.get('password')
        if username and password:
            from module.users import Users
            user_model = Users()
            result = user_model.find_by_username(username)
            if len(result) == 1 and result[0].password == password:
                session['islogin'] = 'true'
                session['userid'] = result[0].userid
                session['username'] = username
                session['nickname'] = result[0].nickname
                session['role'] = result[0].role

# 自定义截断过滤器
def mytruncate(s, length, end='...'):
    count = 0
    new = ''
    for c in s:
        new += c
        count += 0.5 if ord(c) <= 128 else 1
        if count > length:
            break
    return new + end

app.jinja_env.filters.update(truncate=mytruncate)

# 全局上下文处理器（文章类型）
@app.context_processor
def gettype():
    article_type = {
        '1': 'PHP开发',
        '2': 'Java开发',
        '3': 'Python开发',
        '4': 'Web前端',
        '5': '测试开发',
        '6': '数据科学',
        '7': '网络安全',
        '8': '蜗牛杂谈'
    }
    return dict(article_type=article_type)

# 文件上传相关路由
@app.route('/preupload')
def pre_upload():
    return render_template('file-upload.html')

@app.route('/upload', methods=['POST'])
def do_upload():
    headline = request.form.get('headline')
    content = request.form.get('content')
    file = request.files.get('upfile')
    print(headline, content)

    if not file or file.filename == '':
        return 'No file selected'

    suffix = file.filename.split('.')[-1].lower()
    allowed_suffix = ['jpg', 'jpeg', 'png', 'rar', 'zip', 'doc', 'docx']
    if suffix not in allowed_suffix:
        return 'Invalid file type'

    save_path = f'D:/test001.{suffix}'
    file.save(save_path)
    return f'Done! File saved to {save_path}'

# -------------------------- 注册蓝图 --------------------------
if __name__ == '__main__':
    from controller.index import index
    app.register_blueprint(index)

    from controller.user import user
    app.register_blueprint(user)

    from controller.article import article
    app.register_blueprint(article)

    from controller.favorite import favorite
    app.register_blueprint(favorite)

    from controller.comment import comment
    app.register_blueprint(comment)

    from controller.ueditor import ueditor
    app.register_blueprint(ueditor)

    from controller.admin import admin
    app.register_blueprint(admin)

    from controller.ucenter import ucenter
    app.register_blueprint(ucenter)

    app.run(debug=True, host='0.0.0.0', port=5000)