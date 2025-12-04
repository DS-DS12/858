from flask import session
from sqlalchemy import Table, Column, Integer, DateTime
from common.database import dbconnect
import time


class Favorite:
    def __init__(self):
        self.dbsession, self.md, self.DBase, self.bind = dbconnect()
        # 显式定义 favorite 表字段（SQLAlchemy Core 方式）
        self.table = Table(
            'favorite',
            self.md,
            Column('favoriteid', Integer, primary_key=True, autoincrement=True),
            Column('userid', Integer),
            Column('articleid', Integer),
            Column('canceled', Integer, default=0),  # 0=正常，1=已取消
            Column('createtime', DateTime),
            Column('updatetime', DateTime),
            autoload_with=self.bind,
            extend_existing=True
        )

    # 插入/激活收藏
    def insert_favorite(self, articleid):
        row = self.dbsession.query(self.table).filter_by(
            articleid=articleid,
            userid=session.get('userid')
        ).first()

        if row is not None:
            # 激活收藏（使用 SQLAlchemy Core 更新，更稳定）
            update_stmt = self.table.update().where(
                self.table.c.favoriteid == row.favoriteid
            ).values(
                canceled=0,
                updatetime=time.strftime('%Y-%m-%d %H:%M:%S')
            )
            self.dbsession.execute(update_stmt)
        else:
            # 新增收藏
            now = time.strftime('%Y-%m-%d %H:%M:%S')
            insert_stmt = self.table.insert().values(
                articleid=articleid,
                userid=session.get('userid'),
                canceled=0,
                createtime=now,
                updatetime=now
            )
            self.dbsession.execute(insert_stmt)

        self.dbsession.commit()

    # 取消收藏
    def cancel_favorite(self, articleid):
        update_stmt = self.table.update().where(
            (self.table.c.articleid == articleid) &
            (self.table.c.userid == session.get('userid')) &
            (self.table.c.canceled == 0)
        ).values(
            canceled=1,
            updatetime=time.strftime('%Y-%m-%d %H:%M:%S')
        )
        result = self.dbsession.execute(update_stmt)
        self.dbsession.commit()
        return result.rowcount > 0

    # 判断是否已收藏
    def check_favorite(self, articleid):
        row = self.dbsession.query(self.table).filter_by(
            articleid=articleid,
            userid=session.get('userid'),
            canceled=0
        ).first()
        return row is not None

    # 查询我的收藏（核心修复：直接使用 Article 的 table 属性）
    def find_my_favorite(self):
        from module.article import Article
        article_model = Article()

        # 直接使用 Article 模型的 table 属性（与 Favorite 类定义一致）
        article_table = article_model.table

        # 关联查询：收藏表 + 文章表
        result = self.dbsession.query(self.table, article_table).join(
            article_table,  # 关联的文章表
            # 关联条件：收藏表.articleid = 文章表.articleid（确保字段名一致）
            self.table.c.articleid == article_table.c.articleid
        ).filter(
            self.table.c.userid == session.get('userid'),  # 当前登录用户
            self.table.c.canceled == 0,  # 未取消的收藏
            article_table.c.hidden == 0,  # 文章未隐藏
            article_table.c.drafted == 0,  # 非草稿
            article_table.c.checked == 1  # 已审核
        ).order_by(
            self.table.c.updatetime.desc()  # 按收藏更新时间倒序
        ).all()

        # 转换为字典列表（适配前端渲染）
        favorite_list = []
        for fav_row, art_row in result:
            # 收藏记录转字典
            fav_dict = {
                'favoriteid': fav_row.favoriteid,
                'userid': fav_row.userid,
                'articleid': fav_row.articleid,
                'canceled': fav_row.canceled,
                'createtime': str(fav_row.createtime) if fav_row.createtime else None,
                'updatetime': str(fav_row.updatetime) if fav_row.updatetime else None
            }
            # 文章记录转字典（使用 Article 自带的 _row_to_dict 方法，确保字段一致）
            art_dict = article_model._row_to_dict(art_row)
            favorite_list.append({'favorite': fav_dict, 'article': art_dict})

        return favorite_list

    # 切换收藏状态
    def switch_favorite(self, favoriteid):
        update_stmt = self.table.update().where(
            self.table.c.favoriteid == favoriteid
        ).values(
            canceled=func.case(
                [(self.table.c.canceled == 0, 1)],
                else_=0
            ),
            updatetime=time.strftime('%Y-%m-%d %H:%M:%S')
        )
        self.dbsession.execute(update_stmt)
        self.dbsession.commit()
        # 查询最新状态并返回
        row = self.dbsession.query(self.table.c.canceled).filter_by(favoriteid=favoriteid).first()
        return row.canceled if row else 1

    # 辅助方法：通用 Row 转字典（备用）
    def _row_to_dict(self, row):
        if not row:
            return {}
        return {col: getattr(row, col) for col in row.keys()}