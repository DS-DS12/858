from flask import session, request
from sqlalchemy import Table, Column, Integer, String, Text, DateTime
from common.database import dbconnect
import time

from common.utility import model_join_list

# 关键1：删除顶部模块级的 Users 导入（避免循环导入）
# 删掉：from module.users import Users

# 核心修改1：注释掉模块级连接（避免app未活跃时获取）
# dbsession, md, DBase = dbconnect()

class Comment:  # 移除 (DBase) 继承
    def __init__(self):
        # 核心修改：接收 session、metadata、Model、数据库连接（新增 bind 参数）
        self.dbsession, self.md, self.DBase, self.bind = dbconnect()
        # 核心修复：显式定义 comment 表字段（与数据库表结构一致）
        self.table = Table(
            "comment",  # 表名
            self.md,
            Column('commentid', Integer, primary_key=True, autoincrement=True),  # 主键
            Column('userid', Integer),  # 关联用户表 userid
            Column('articleid', Integer),  # 关联文章表 articleid
            Column('content', Text),  # 评论内容
            Column('ipaddr', String(20)),  # 访问IP
            Column('replyid', Integer, default=0),  # 回复关联的评论ID（0表示原始评论）
            Column('hidden', Integer, default=0),  # 是否隐藏（0=显示，1=隐藏）
            Column('createtime', DateTime),  # 创建时间
            Column('updatetime', DateTime),  # 更新时间
            autoload_with=self.bind,  # 保留自动映射（显式字段优先）
            extend_existing=True  # 允许重复定义（调试时避免冲突）
        )

    # 新增一条评论
    def insert_comment(self, articleid, content, ipaddr):
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        # 用表对象的 insert() 方法创建数据
        insert_stmt = self.table.insert().values(
            userid=session.get('userid'),
            articleid=articleid,
            content=content,
            ipaddr=ipaddr,
            createtime=now,
            updatetime=now,
            hidden=0,
            replyid=0
        )
        self.dbsession.execute(insert_stmt)
        self.dbsession.commit()

    # 根据文章编号查询所有原始评论
    def find_by_articleid(self, articleid):
        result = self.dbsession.query(self.table).filter_by(
            articleid=articleid, hidden=0, replyid=0
        ).all()
        return result

    # 检查用户当天评论是否超过5条限制
    def check_limit_per_5(self):
        start = time.strftime("%Y-%m-%d 00:00:00")
        end = time.strftime("%Y-%m-%d 23:59:59")
        result = self.dbsession.query(self.table).filter(
            self.table.c.userid == session.get('userid'),
            self.table.c.createtime.between(start, end)
        ).all()
        return len(result) >= 5

    # 分页查询评论+关联用户信息
    def find_limit_with_user(self, articleid, start, count):
        from module.users import Users  # 动态导入 Users 类
        result = self.dbsession.query(self.table, Users).join(Users,
            Users.userid == self.table.c.userid) \
            .filter(
                self.table.c.articleid == articleid,
                self.table.c.hidden == 0
            ) \
            .order_by(self.table.c.commentid.desc()) \
            .limit(count).offset(start).all()
        return result

    # 新增一条回复
    def insert_reply(self, articleid, commentid, content, ipaddr):
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        insert_stmt = self.table.insert().values(
            userid=session.get('userid'),
            articleid=articleid,
            content=content,
            ipaddr=ipaddr,
            replyid=commentid,
            createtime=now,
            updatetime=now,
            hidden=0
        )
        self.dbsession.execute(insert_stmt)
        self.dbsession.commit()

    # 分页查询原始评论+关联用户信息
    def find_comment_with_user(self, articleid, start, count):
        from module.users import Users  # 动态导入 Users 类
        result = self.dbsession.query(self.table, Users).join(Users,
            Users.userid == self.table.c.userid) \
            .filter(
                self.table.c.articleid == articleid,
                self.table.c.hidden == 0,
                self.table.c.replyid == 0
            ) \
            .order_by(self.table.c.commentid.desc()) \
            .limit(count).offset(start).all()
        return result

    # 查询某条原始评论的所有回复+关联用户信息
    def find_reply_with_user(self, replyid):
        from module.users import Users  # 动态导入 Users 类
        result = self.dbsession.query(self.table, Users).join(Users,
            Users.userid == self.table.c.userid) \
            .filter(
                self.table.c.replyid == replyid,
                self.table.c.hidden == 0
            ).all()
        return result

    # 生成原始评论+回复的关联列表（供前端展示）
    def get_comment_user_list(self, articleid, start, count):
        result = self.find_comment_with_user(articleid, start, count)
        comment_list = model_join_list(result)
        for comment in comment_list:
            # 查询当前原始评论的所有回复
            reply_result = self.find_reply_with_user(comment['commentid'])
            comment['reply_list'] = model_join_list(reply_result)
        return comment_list

    # 查询某篇文章的原始评论总数量（用于分页）
    def get_count_by_article(self, articleid):
        count = self.dbsession.query(self.table).filter_by(
            articleid=articleid, hidden=0, replyid=0
        ).count()
        return count