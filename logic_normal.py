# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback
from datetime import datetime
import re
import requests
# third-party
try:
    import feedparser
except:
    import subprocess
    import sys
    subprocess.check_output([sys.executable, '-m', 'pip', 'install', 'feedparser'], universal_newlines=True)
    import feedparser
# sjva 공용
from framework import app, db, scheduler, path_app_root
from framework.job import Job
from framework.util import Util
from framework.common.rss import RssUtil
from system.logic import SystemLogic
import framework.common.notify as Notify

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting, ModelFeed
#########################################################

class LogicNormal(object):
    @staticmethod
    def scheduler_function():
        try:
            logger.debug('scheduler_function')
            LogicNormal.process_insert_feed()
            LogicNormal.process_check_rule()
            LogicNormal.process_check_alarm()

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    @staticmethod
    def get_crawl(url, regex):
        datas = []
        getdata = requests.get(url=url)
        check_regex = re.compile(regex)
        for item in check_regex.finditer(getdata.text):
            data = item.groupdict()
            link = ModelSetting.get('algumon_url')
            if link[-1] == '/':
                link = link[:-1]
            link += data['link']
            data['link'] = LogicNormal.get_redirect_url(link)
            datas.append(data)
        if len(datas) == 0:
            logger.error('Did not regex parsing.')
            logger.error(getdata.text)
        return datas
    @staticmethod
    def get_redirect_url(url):
        return requests.get(url=url).url
    @staticmethod
    def process_insert_feed():
        algumon_url = ModelSetting.get('algumon_url')
        algumon_regex = ModelSetting.get('algumon_regex')
        datas = LogicNormal.get_crawl(algumon_url, algumon_regex)

        if len(datas) > 0 :
            if ModelFeed.add_feed(datas) == 'success':
                logger.debug('success')
            else:
                logger.error('fail')
        else:
            logger.error('No items.')

    @staticmethod
    def process_check_rule():
        datas = ModelFeed.get_feeds_by_status(0)
        update_datas = []
        include_keywords = ModelSetting.get('include_keyword').split(',')
        exclude_keywords = ModelSetting.get('exclude_keyword').split(',')
        include_all = ModelSetting.get_bool('include_all')
        for data in datas:
            is_pass = True
            title = data.title
            if include_all:
                is_pass = False
            for include_keyword in include_keywords:
                include_keyword = include_keyword.strip()
                if len(include_keyword) > 0 and is_pass:
                    if '/' == include_keyword[0] and '/' == include_keyword[-1]:
                        regex_keyword = re.compile(include_keyword)
                        if len(regex_keyword.findall(title)) > 0:
                            is_pass = False
                    else:
                        if include_keyword in title:
                            is_pass = False
            for exclude_keyword in exclude_keywords:
                exclude_keyword = exclude_keyword.strip()
                if len(exclude_keyword) > 0 and not is_pass:
                    if '/' == exclude_keyword[0] and '/' == exclude_keyword[-1]:
                        regex_keyword = re.compile(exclude_keyword)
                        if len(regex_keyword.findall(title)) > 0:
                            is_pass = True
                    else:
                        if exclude_keyword in title:
                            is_pass = True
            if is_pass:
                data.status = -1
                update_datas.append(data)
            else:
                data.status = 1
                update_datas.append(data)
        ModelFeed.add_feed(update_datas)
    @staticmethod
    def get_message_by_format(data):
        message_format = ModelSetting.get('message_format')\
            .replace('{title}', data.title)\
            .replace('{link}', data.link)\
            .replace('{pub_date}', str(data.pub_date))\
            .replace('{community}', data.community)\
            .replace('{market}', data.market)
        return message_format
    @staticmethod
    def process_check_alarm():
        datas = ModelFeed.get_feeds_by_status(1)
        update_datas = []
        for data in datas:
            message = LogicNormal.get_message_by_format(data)
            LogicNormal.process_send_alarm(message)
            data.status = 2
            update_datas.append(data)
        ModelFeed.update_feed(update_datas)

    @staticmethod
    def process_send_alarm(message):
        try:
            bot_id = ModelSetting.get('bot_id')
            Notify.send_message(message, message_id=bot_id)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())