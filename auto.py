# -*- coding: utf-8 -*-
import datetime
import getpass
import os
import time
import schedule

import json
import re
import requests
import urllib3
from apscheduler.schedulers.blocking import BlockingScheduler
from halo import Halo


class DaKa(object):
    def __init__(self, username, password, eai_sess, UUkey):
        self.username = username
        self.password = password
        self.login_url = "http://ca.its.csu.edu.cn/home/login/215"
        self.redirect_url = "http://ca.its.csu.edu.cn/SysInfo/SsoService/215"
        self.base_url = "https://wxxy.csu.edu.cn/ncov/wap/default/index"
        self.save_url = "https://wxxy.csu.edu.cn/ncov/wap/default/save"
        self.eai_sess = eai_sess
        self.UUkey = UUkey
        self.cookie1 = None
        self.cookie2 = None
        self.header = None
        self.info = None
        self.sess = requests.Session()

    def login(self):
        """Login to CSU platform"""
        res1 = self.sess.get(self.login_url)
        self.cookie1 = res1.headers['Set-Cookie'].split(";")[0]
        header1 = {'Cookie': self.cookie1}
        data = {
            "userName": self.username,
            "passWord": self.password,
            "enter": 'true',
        }
        res2 = self.sess.post(url=self.login_url, headers=header1, data=data, allow_redirects=False)
        print(self.sess.headers)
        print(res2.headers)
        self.cookie2 = res2.headers['Set-Cookie'].split(";")[0]
        self.header = {
            'Cookie': "eai-sess=" + self.eai_sess + ";" + "UUkey=" + self.UUkey + ";" + self.cookie1 + ";" + self.cookie2}
        return self.sess

    def get_info(self, html=None):
        """Get hitcard info, which is the old info with updated new time."""
        if not html:
            urllib3.disable_warnings()
            res = self.sess.get(self.base_url, headers=self.header, verify=False)
            html = res.content.decode()

        jsontext = re.findall(r'oldInfo: [\s\S]*tipMsg', html)[0]
        jsontext = eval(jsontext[jsontext.find("{"):jsontext.rfind(",")].replace(" ", ""))
        jsontext["geo_api_info"] = json.loads(jsontext["geo_api_info"])
        name = re.findall(r'realname: "([^\"]+)",', html)[0]
        number = re.findall(r"number: '([^\']+)',", html)[0]

        new_info = jsontext.copy()
        new_info['name'] = name
        new_info['number'] = number
        new_info["date"] = self.get_date()
        new_info["created"] = round(time.time())
        self.info = new_info
        return new_info

    def get_date(self):
        today = datetime.date.today()
        return "%4d%02d%02d" % (today.year, today.month, today.day)

    def post(self):
        """Post the hitcard info"""
        res = self.sess.post(self.save_url, data=self.info, headers=self.header)
        return json.loads(res.text)


def main(username, password, eai_sess, UUkey):
    print("\n[Time] %s" % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("🚌 打卡任务启动")
    spinner = Halo(text='Loading', spinner='dots')
    spinner.start('正在新建打卡实例...')
    dk = DaKa(username, password, eai_sess, UUkey)
    spinner.succeed('已新建打卡实例')

    spinner.start(text='登录到中南大学信息门户...')
    dk.login()
    spinner.succeed('已登录到中南大学信息门户')

    spinner.start(text='正在获取个人信息...')
    dk.get_info()
    spinner.succeed('%s %s同学, 你好~' % (dk.info['number'], dk.info['name']))

    spinner.start(text='正在为您打卡打卡打卡')
    res = dk.post()
    if str(res['e']) == '0':
        spinner.stop_and_persist(symbol='🦄 '.encode('utf-8'), text='已为您打卡成功！')
    else:
        spinner.stop_and_persist(symbol='🦄 '.encode('utf-8'), text=res['m'])


if __name__ == "__main__":
    if os.path.exists('./config.json'):
        configs = json.loads(open('./config.json', 'r', encoding='utf-8').read())
        username = configs["username"]
        password = configs["password"]
        hour = configs["schedule"]["hour"]
        minute = configs["schedule"]["minute"]
        eai_sess = configs["cookie"]["eai_sess"]
        UUkey = configs["cookie"]["UUkey"]
    else:
        username = input("👤 中南大学学工号: ")
        password = getpass.getpass('🔑 中南大学信息门户密码: ')
        print("⏲ 请输入定时时间（默认每天7:05）")
        hour = input("\thour: ") or 7
        minute = input("\tminute: ") or 5
        eai_sess = input("请输入eai-sess cookie: ")
        UUkey = input("请输入UUkey cookie: ")

    # Schedule task
    scheduler = BlockingScheduler()
    scheduler.add_job(main, 'cron', args=[username, password, eai_sess, UUkey], hour=hour, minute=minute)
    print('⏰ 已启动定时程序，每天 %02d:%02d 为您打卡' % (int(hour), int(minute)))
    print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
