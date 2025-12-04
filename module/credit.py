from flask import session
from sqlalchemy import Table, Column, Integer, String, DateTime
from common.database import dbconnect
import time

class Credit:
    def __init__(self):
        self.dbsession, self.md, self.DBase, self.bind = dbconnect()
        # 显式定义 credit 表字段
        self.table = Table(
            'credit',
            self.md,
            Column('creditid', Integer, primary_key=True, autoincrement=True),
            Column('userid', Integer),
            Column('category', Integer),  # 1=消费，2=获取
            Column('target', Integer),  # 关联目标ID（文章ID等）
            Column('credit', Integer),  # 积分数量（正数=增加，负数=减少）
            Column('createtime', DateTime),
            Column('updatetime', DateTime),
            autoload_with=self.bind,
            extend_existing=True
        )

    # 插入积分明细数据
    def insert_detail(self, category_type, target, credit):
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        insert_stmt = self.table.insert().values(
            userid=session.get('userid'),
            category=category_type,  # 避免使用 type 关键字
            target=target,
            credit=credit,
            createtime=now,
            updatetime=now
        )
        self.dbsession.execute(insert_stmt)
        self.dbsession.commit()

    # 判断用户是否已经为某篇文章消耗积分（category=1 表示消费）
    def check_payed_article(self, articleid):
        result = self.dbsession.query(self.table).filter_by(
            userid=session.get('userid'),
            target=articleid,
            category=1
        ).all()
        return len(result) > 0

    # 查询用户积分明细（分页）
    def find_user_credit(self, start, count):
        result = self.dbsession.query(self.table).filter_by(
            userid=session.get('userid')
        ).order_by(self.table.c.createtime.desc()).limit(count).offset(start).all()
        return [self._row_to_dict(row) for row in result]

    # 统计用户积分明细总数
    def get_user_credit_count(self):
        count = self.dbsession.query(self.table).filter_by(
            userid=session.get('userid')
        ).count()
        return count

    # 辅助方法：Row 对象转字典
    def _row_to_dict(self, row):
        return {
            'creditid': row.creditid,
            'userid': row.userid,
            'category': row.category,
            'target': row.target,
            'credit': row.credit,
            'createtime': str(row.createtime) if row.createtime else None,
            'updatetime': str(row.updatetime) if row.updatetime else None
        }