# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback
import time
import threading

# third-party

# sjva 공용
from framework import db, scheduler, path_app_root
from framework.job import Job
from framework.util import Util

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting
from .logic_normal import LogicNormal
#########################################################

class Logic(object):
    db_default = {
        'db_version': '1',
        'auto_start': 'False',
        'interval': '1',
        'allow_duplicate': 'True',
        'algumon_url' : 'https://algumon.com',
        'algumon_regex' : r'<a href=\"(?P<link>.*?)\"\s.+data-label=\"(?P<title>.*?)\"\sdata-product=\"\d+\"[\w\W]*?\s(?:<img src=\"(?P<poster_url>.+)\"\salt=[\w\W]*?)*\<span class=\"label\sshop\"\>(?:\<a\shref=\".*?\"\>(?P<market>.+)<\/a\>|.{5})\<\/span\>\s+\<span class=\"label\ssite\"\>(?P<community>.+)\<\/span\>[\w\W]*?<\/i>\s(?P<pub_date>.+\s+.|.{2})\n',
        'algumon_header':'<li class=\"left clearfix',
        'include_keyword' : '',
        'exclude_keyword' : '',
        'include_all': 'True',
        'message_format': '[{title}] : {link}',
        'bot_id' : 'bot_sjva_deal_alarm'
    }

    @staticmethod
    def db_init():
        try:
            for key, value in Logic.db_default.items():
                logger.debug('%s : %s', key, value)
                logger.debug(ModelSetting.__tablename__)
                if db.session.query(ModelSetting).filter_by(key=key).count() == 0:
                    db.session.add(ModelSetting(key, value))
            db.session.commit()
            Logic.migration()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def plugin_load():
        try:
            logger.debug('db init start')
            Logic.db_init()
            if ModelSetting.get_bool('auto_start'):
                Logic.scheduler_start()
            from .plugin import plugin_info
            Util.save_from_dict_to_json(plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def plugin_unload():
        pass

    @staticmethod
    def scheduler_start():
        try:
            logger.debug('%s scheduler_start' % package_name)
            job = Job(package_name, package_name, ModelSetting.get('interval'), Logic.scheduler_function, u"핫딜 알리미",
                      False)
            scheduler.add_job_instance(job)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def scheduler_stop():
        try:
            logger.debug('%s scheduler_stop' % package_name)
            scheduler.remove_job(package_name)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def scheduler_function():
        try:
            LogicNormal.scheduler_function()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def reset_db():
        try:
            from .model import ModelFeed
            db.session.query(ModelFeed).delete()
            db.session.commit()
            return True
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False

    @staticmethod
    def one_execute():
        try:
            if scheduler.is_include(package_name):
                if scheduler.is_running(package_name):
                    ret = 'is_running'
                else:
                    scheduler.execute_job(package_name)
                    ret = 'scheduler'
            else:
                def func():
                    time.sleep(2)
                    Logic.scheduler_function()

                threading.Thread(target=func, args=()).start()
                ret = 'thread'
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret = 'fail'
        return ret

    @staticmethod
    def migration():
        try:
            pass
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
