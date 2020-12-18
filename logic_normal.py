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
            LogicNormal.process_analysis()

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    @staticmethod
    def get_crawl(url, regex, header):
        datas = []
        getdata = requests.get(url=url)
        parsed_datas = getdata.text.split(header)[1:]
        check_regex = re.compile(regex, re.MULTILINE)
        for text in parsed_datas:
            search_result = check_regex.search(text)
            if search_result:
                data = search_result.groupdict()
                link = ModelSetting.get('algumon_url')
                if link[-1] == '/':
                    link = link[:-1]
                link += data['link']
                data['link'] = LogicNormal.get_redirect_url(link)
                data['title'] = data['title']
                datas.append(data)
        if len(datas) == 0:
            logger.error('Did not regex parsing.')
            logger.error(parsed_datas)
        return datas
    @staticmethod
    def get_redirect_url(url):
        return requests.get(url=url).url
    @staticmethod
    def process_insert_feed():
        algumon_url = ModelSetting.get('algumon_url')
        algumon_regex = ModelSetting.get('algumon_regex')
        algumon_header = ModelSetting.get('algumon_header')
        datas = LogicNormal.get_crawl(algumon_url, algumon_regex, algumon_header)

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
        ModelFeed.update_feed(update_datas)
    @staticmethod
    def get_message_by_format(data):
        data.title = data.title.replace('&nbsp;', ' ').replace('&lt;','<').replace('&gt;','>')
        logger.debug(data.__repr__())
        message_format = ModelSetting.get('message_format')\
            .replace('{title}', data.title)\
            .replace('{link}', data.link)\
            .replace('{pub_date}', str(data.pub_date))\
            .replace('{community}', data.community)\
            .replace('{market}', data.market if data.market else '정보 없음')
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

    @staticmethod
    def process_analysis():
        datas = ModelFeed.get_analysis_target()
        update_datas = []
        for data in datas:
            getdata = requests.get(url=data.link)
            check_title_regex = None
            title_text = None
            if u'뽐뿌' == data.community:
                title_text = getdata.text.split('<div class="bookmark-three-rung-menu-box">')[0]
                check_title_regex = re.compile(r'<div class=wordfix>.{2}\:\s\<a\shref=.+target=_blank>(?P<market_url>.+)</a>')
            elif u'쿨엔조이' == data.community:
                if '<section id="bo_v_link">' in getdata.text:
                    title_text = getdata.text.split('<section id="bo_v_link">')[1].split('</section>')[0]
                    check_title_regex = re.compile(r'<strong>(?P<market_url>.+)<\/strong>')
            elif u'퀘이사존' == data.community:
                if u'<th>링크</th>' in getdata.text:
                    title_text = getdata.text.split(u'<th>링크</th>')[1].split('</tr>')[0]
                    check_title_regex = re.compile(r'\s>(?P<market_url>.+)</a></td>')
                    if check_title_regex.search(title_text) is None and u'<div class="view-content">' in getdata.text:
                        title_text = getdata.text.split(u'<div class="view-content">')[1].split('</div>')[0]
                        check_title_regex = re.compile(r'.*?>(?P<market_url>https*:[\w\.\/\?\&\;\=\-\_]+)')
                else:
                    logger.error(getdata.text)
            elif u'클리앙' == data.community:
                title_text = getdata.text.split('<link rel="stylesheet')[0]
                if u'<span class="attached_subject">구매링크</span>' in getdata.text:
                    title_text = getdata.text.split('<span class="attached_subject">구매링크</span>')[1].split('</div>')
                    check_title_regex = re.compile(r'>(?P<market_url>https*:[\w\.\/\?\&\;\=\-\_]+)</a>')
                elif 'http' in title_text:
                    check_title_regex = re.compile(
                        r'<meta name=\"description\" content=\".+(?P<market_url>https*:[\w\.\/\?\&\;\=\-\_]+)')
                else:
                    check_title_regex = None
            elif u'루리웹' == data.community:
                if u'원본출처<span class="text_bar"> | </span>' in getdata.text:
                    title_text = getdata.text.split('원본출처<span class="text_bar"> | </span>')[1].split('</a>')[0]
                    check_title_regex = re.compile(r'>.*?(?P<market_url>https*:[\w\.\/\?\&\;\=\-\_]+)')
            elif u'어미새' == data.community:
                if u'<meta name="description" content="' in getdata.text:
                    title_text = getdata.text.split('<meta name="description" content="')[1].split('/>')[0]
                    check_title_regex = re.compile(r'.*?(?P<market_url>https*:[\w\.\/\?\&\;\=\-\_]+)')
            elif u'딜바다' == data.community:
                if u'alt=\"관련링크\"' in getdata.text:
                    title_text = getdata.text.split(u'alt=\"관련링크\"')[1].split('</strong>')[0]
                    check_title_regex = re.compile(r'.*?>(?P<market_url>https*:[\w\.\/\?\&\;\=\-\_]+)')
                elif u'<div id="bo_v_con">' in getdata.text:
                    title_text = getdata.text.split('<div id="bo_v_con">')[1].split('</div>')[0]
                    check_title_regex = re.compile(r'.*?>(?P<market_url>https*:[\w\.\/\?\&\;\=\-\_]+)')
            else:
                continue
            matches = check_title_regex.search(title_text) if check_title_regex and title_text else None
            market_url = matches.groupdict()['market_url'].split('&amp;')[0].split('&nbsp;')[0] if matches else None
            data.market_link = market_url
            data.update_time_2 = datetime.now()
            update_datas.append(data)
        ModelFeed.update_feed(update_datas)
        pass