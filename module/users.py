from flask import session
from sqlalchemy import Table, Column, Integer, String, DateTime
from common.database import dbconnect
import time, random
from werkzeug.security import generate_password_hash, check_password_hash  # 密码加密

class Users:
    def __init__(self):
        self.dbsession, self.md, self.DBase, self.bind = dbconnect()
        # 显式定义 users 表字段（password 已定义为 String(100)，建议改为 255 更稳妥）
        self.table = Table(
            'users',
            self.md,
            Column('userid', Integer, primary_key=True, autoincrement=True),
            Column('username', String(50), unique=True, nullable=False),
            Column('password', String(255), nullable=False),  # 修复：扩展为 255 字符（适配加密后长度）
            Column('nickname', String(50), nullable=False),
            Column('avatar', String(20), default='1.png'),
            Column('role', String(10), default='user'),
            Column('credit', Integer, default=50),
            Column('createtime', DateTime),
            Column('updatetime', DateTime),
            autoload_with=self.bind,
            extend_existing=True
        )

    # 查询用户名（注册/登录校验）
    def find_by_username(self, username):
        result = self.dbsession.query(self.table).filter_by(username=username).all()
        return [self._row_to_dict(row) for row in result]

    # 注册功能（密码加密存储）
    def do_register(self, username, password):
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        nickname = username.split('@')[0]
        avatar = str(random.randint(1, 15)) + '.png'
        # 密码加密（pbkdf2:sha256 算法，安全且兼容）
        password_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        insert_stmt = self.table.insert().values(
            username=username,
            password=password_hash,  # 存储加密后的密码
            nickname=nickname,
            avatar=avatar,
            role='user',
            credit=50,
            createtime=now,
            updatetime=now
        )
        result = self.dbsession.execute(insert_stmt)
        self.dbsession.commit()
        return self.find_by_userid(result.inserted_primary_key[0])

    # 验证密码（登录时使用）
    def verify_password(self, username, password):
        user_list = self.find_by_username(username)
        if not user_list:
            return False
        user = user_list[0]
        # 核心修复：现在 user 字典包含 'password' 字段，可正常访问
        return check_password_hash(user['password'], password)

    # 修改用户积分
    def update_credit(self, credit):
        # 修复：使用 SQLAlchemy Core 的更新方式，避免 __getitem__/__setitem__ 兼容性问题
        update_stmt = self.table.update().where(
            self.table.c.userid == session.get('userid')
        ).values(
            # 积分不低于 0，使用 SQL 函数更高效
            credit=self.table.c.credit + credit,
            updatetime=time.strftime('%Y-%m-%d %H:%M:%S')
        )
        # 执行更新并确保积分不低于 0
        self.dbsession.execute(update_stmt)
        # 二次修正：确保积分 >=0（兜底逻辑）
        self.dbsession.execute(
            self.table.update().where(
                (self.table.c.userid == session.get('userid')) &
                (self.table.c.credit < 0)
            ).values(credit=0)
        )
        self.dbsession.commit()

    # 通过 userid 查询用户
    def find_by_userid(self, userid):
        user = self.dbsession.query(self.table).filter_by(userid=userid).one()
        return self._row_to_dict(user)

    # 辅助方法：Row 对象转字典（核心修复：添加 'password' 字段）
    def _row_to_dict(self, row):
        return {
            'userid': row.userid,
            'username': row.username,
            'password': row.password,  # 必须添加！否则 verify_password 会报 KeyError
            'nickname': row.nickname,
            'avatar': row.avatar,
            'role': row.role,
            'credit': row.credit,
            'createtime': str(row.createtime) if row.createtime else None,
            'updatetime': str(row.updatetime) if row.updatetime else None
        }