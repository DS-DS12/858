from flask import current_app
from flask_sqlalchemy import SQLAlchemy

def dbconnect():
    db = current_app.extensions['sqlalchemy']
    # 核心修改：返回 session、metadata、Model、连接对象（新增 bind 参数）
    return db.session, db.metadata, db.Model, db.session.bind