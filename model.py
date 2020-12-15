# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback
import json
import datetime
import re
import time
# third-party
try:
    from sqlalchemy import or_, and_, func, not_, desc
    from sqlalchemy.orm import backref
except:
    import subprocess
    import sys
    subprocess.check_output([sys.executable, '-m', 'pip', 'install', 'sqlalchemy'], universal_newlines=True)
    from sqlalchemy import or_, and_, func, not_, desc
    from sqlalchemy.orm import backref
# sjva 공용
from framework import db, app, path_app_root
from framework.util import Util

# 패키지

from .plugin import logger, package_name

#########################################################

app.config['SQLALCHEMY_BINDS'][package_name] = 'sqlite:///%s' % (
    os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name))

class ModelSetting(db.Model):
    __tablename__ = '%s_setting' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String, nullable=False)

    def __init__(self, key, value):
        self.key = key
        self.value = value
        logger.debug("TABLE INIT :: %s", self.__tablename__)

    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        return {x.name: getattr(self, x.name) for x in self.__table__.columns}

    @staticmethod
    def get(key):
        try:
            return db.session.query(ModelSetting).filter_by(key=key).first().value.strip()
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def get_int(key):
        try:
            return int(ModelSetting.get(key))
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def get_bool(key):
        try:
            return (ModelSetting.get(key) == 'True')
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def set(key, value):
        try:
            item = db.session.query(ModelSetting).filter_by(key=key).with_for_update().first()
            if item is not None:
                item.value = value.strip()
                db.session.commit()
            else:
                db.session.add(ModelSetting(key, value.strip()))
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def to_dict():
        try:
            return Util.db_list_to_dict(db.session.query(ModelSetting).all())
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def setting_save(req):
        try:
            for key, value in req.form.items():
                logger.debug('Key:%s Value:%s', key, value)
                if key in ['scheduler', 'is_running', 'global_scheduler_sub']:
                    continue
                if key == 'default_username' and value.startswith('==='):
                    continue
                entity = db.session.query(ModelSetting).filter_by(key=key).with_for_update().first()
                entity.value = value
            db.session.commit()
            return True
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False

    @staticmethod
    def get_list(key):
        try:
            value = ModelSetting.get(key)
            values = [x.strip().replace(' ', '').strip() for x in value.replace('\n', '|').split('|')]
            values = Util.get_list_except_empty(values)
            return values
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

class ModelFeed(db.Model):
    __tablename__ = '%s_feed' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name
    seq_feed_id = db.Sequence('seq_feed_id')
    feed_id = db.Column(db.Integer, seq_feed_id, server_default=seq_feed_id.next_value(), primary_key=True)
    created_time = db.Column(db.DateTime) # 최초 수집 시간
    update_time_1 = db.Column(db.DateTime) # 알람 검사 시간
    update_time_2 = db.Column(db.DateTime) # 분석시간
    pub_date = db.Column(db.DateTime)
    title = db.Column(db.String)
    link = db.Column(db.String)
    market = db.Column(db.String)
    community = db.Column(db.String)
    poster_url = db.Column(db.String)
    status = db.Column(db.Integer) # -1 : 통과, 0 : 최초, 1 : 알람준비, 2 : 알람완료
    def __init__(self):
        self.created_time = datetime.datetime.now()
        self.status = 0
    def __repr__(self):
        return repr(self.as_dict())
    def as_dict(self):
        ret = {x.name:getattr(self, x.name) for x in self.__table__.columns}
        ret['created_time'] = self.created_time.strftime('%m-%d %H:%M:%S') if self.created_time else None
        ret['update_time_1'] = self.update_time_1.strftime('%m-%d %H:%M:%S') if self.update_time_1 else None
        ret['update_time_2'] = self.update_time_2.strftime('%m-%d %H:%M:%S') if self.update_time_2 else None
        ret['pub_date'] = self.pub_date.strftime('%m-%d %H:%M:%S') if self.pub_date else None
        return ret

    @staticmethod
    def get_feed(data):
        try:
            if type(data) == dict:
                query = db.session.query(ModelFeed).filter(ModelFeed.title == data['title'])
            else:
                query = db.session.query(ModelFeed).filter(ModelFeed.title == data.title)
            return query.all()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return []

    @staticmethod
    def add_feed(datas, is_analysis=False): # is first : add, is exist : update
        try:
            for data in datas:
                entity = ModelFeed.get_feed(data)
                if entity is None or len(entity) == 0: # add
                    feed = ModelFeed()
                    check_time_regex = re.compile(r'(?P<amount>\d+)(?P<time_type>분|시간|일)\s+전')
                    check_time_result = check_time_regex.search(data['pub_date']).groupdict()
                    now = feed.created_time
                    if check_time_result['time_type'].strip() == u'분':
                        feed.pub_date = now - datetime.timedelta(minutes=int(check_time_result['amount']))
                    elif check_time_result['time_type'].strip() == u'시간':
                        feed.pub_date = now - datetime.timedelta(hours=int(check_time_result['amount']))
                    elif check_time_result['time_type'].strip() == u'일':
                        feed.pub_date = now - datetime.timedelta(days=int(check_time_result['amount']))
                    else:
                        continue
                    feed.title = data['title']
                    feed.link = data['link']
                    feed.community = data['community']
                    db.session.add(feed)
                else: # update
                    if type(data) == dict:
                        feed = db.session.query(ModelFeed).filter(ModelFeed.title==data['title']).first()
                        feed.status = data['status']
                    else:
                        feed = db.session.query(ModelFeed).filter(ModelFeed.title==data.title).first()
                        feed.status = data.status
                    if is_analysis:
                        feed.update_time_2 = datetime.datetime.now()
                    else:
                        feed.update_time_1 = datetime.datetime.now()
            db.session.commit()
            return 'success'
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return 'fail'
    @staticmethod
    def get_feeds_by_status(status):
        try:
            query = db.session.query(ModelFeed).filter(ModelFeed.status == int(status))
            return query.all()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return []
    @staticmethod
    def web_list(req):
        try:
            ret = {}
            page_size = 15
            page = int(req.form['page']) if 'page' in req.form else 1
            search = req.form['search_word'] if 'search_word' in req.form else ''
            option = req.form['option']
            order = req.form['order'] if 'order' in req.form else 'desc'
            query = ModelFeed.make_query(search=search, option=option, order=order)
            count = query.count()
            query = query.limit(page_size).offset((page-1)*page_size)
            lists = query.all()
            ret['list'] = [item.as_dict() for item in lists]
            ret['paging'] = Util.get_paging_info(count, page, page_size)
            return ret
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return {}
    @staticmethod
    def remove(title):
        try:
            db.session.query(ModelFeed).filter_by(title=title).delete()
            db.session.commit()
            return 'success'
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return 'fail'
    @staticmethod
    def make_query(search='', option='all', order='desc'):
        query = db.session.query(ModelFeed)
        if search is not None and search != '':
            if search.find('|') != -1:
                tmp = search.split('|')
                conditions = []
                for tt in tmp:
                    if tt != '':
                        conditions.append(ModelFeed.title.like('%' + tt.strip() + '%'))
                query = query.filter(or_(*conditions))
            elif search.find(',') != -1:
                tmp = search.split(',')
                for tt in tmp:
                    if tt != '':
                        query = query.filter(ModelFeed.title.like('%' + tt.strip() + '%'))
            else:
                query = query.filter(ModelFeed.title.like('%' + search + '%'))
        if option == 'wait':
            query = query.filter(ModelFeed.status == 0)
        elif option == 'true':
            query = query.filter(ModelFeed.status == 2)
        elif option == 'false':
            query = query.filter(ModelFeed.status == -1)

        if order == 'desc':
            query = query.order_by(desc(ModelFeed.feed_id))
        else:
            query = query.order_by(ModelFeed.feed_id)
        return query