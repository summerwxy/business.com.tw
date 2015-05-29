#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib
import urllib2
import os.path
import json
from lxml import etree, cssselect
import codecs
import sqlite3
import sys, os, re
import urlparse
from bs4 import BeautifulSoup
import chardet

HOME_PAGE = 'http://business.com.tw/prod/productc1.htm'
SQLITE_FILE_NAME = 'data.db'


def dropAndCreateTable():
  conn = sqlite3.connect(SQLITE_FILE_NAME)
  c = conn.cursor()
  c.execute('DROP TABLE IF EXISTS lv1')
  c.execute('CREATE TABLE lv1(id INTEGER PRIMARY KEY ASC, name TEXT, url TEXT, status TEXT)')
  c.execute('DROP TABLE IF EXISTS lv2')
  c.execute('CREATE TABLE lv2(id INTEGER PRIMARY KEY ASC, lv1id INTEGER, name TEXT, url TEXT, status TEXT)')
  c.execute('DROP TABLE IF EXISTS lv3')
  c.execute('CREATE TABLE lv3(id INTEGER PRIMARY KEY ASC, lv1id INTEGER, lv2id INTEGER, name TEXT, url TEXT, desc TEXT, status TEXT)')
  # TODO: level4
  conn.commit()
  conn.close()

def getLevel1():
  # 抓首頁的 html source code
  string = urllib2.urlopen(HOME_PAGE).read()
  parser = etree.HTMLParser()
  html = etree.fromstring(string, parser)
  # 找出 a 標籤, 其中 href 以 /cop/com.asp?id= 開頭
  select = cssselect.CSSSelector(r'a[href^="/cop/com.asp?id="]')
  items = select(html)
  # 暫存在 list 裡面
  result = []
  for item in items:
    result.append((item.text, item.get("href")))
  # sqlite
  conn = sqlite3.connect(SQLITE_FILE_NAME)
  c = conn.cursor()
  c.execute('DELETE FROM lv1')
  c.executemany("INSERT INTO lv1(name, url, status) VALUES(?, ?, 'no')", result)
  conn.commit()
  conn.close()

def getLevel2():
  conn = sqlite3.connect(SQLITE_FILE_NAME)
  c = conn.cursor()
  rows = c.execute("SELECT id, name, url FROM lv1 WHERE status = 'no'") # TODO: remove limit
  # 因為後面會用到 cursor, 所以要先暫存起來
  lvs = []
  for row in rows:
    lvs.append((row[0], row[1], row[2]))

  i = 1
  for lv in lvs:
    url = urlparse.urljoin(HOME_PAGE, lv[2])
    print 'get %s(%s/%s): %s' % (lv[1], i, len(lvs), url)
    i = i + 1
    string = urllib2.urlopen(url).read()
    parser = etree.HTMLParser()
    html = etree.fromstring(string, parser)
    select = cssselect.CSSSelector(r'a[href^="/cop/com.asp?id="]')
    items = select(html)
    result = []
    for item in items:
      result.append((lv[0], item.text, item.get('href')))
    c.executemany("INSERT INTO lv2(lv1id, name, url, status) VALUES(?, ?, ?, 'no')", result)
    c.execute("UPDATE lv1 SET status = 'yes' WHERE id = %s" % (lv[0]))
    conn.commit() # 每一批就存一次
  conn.close()


def getLevel3():
  conn = sqlite3.connect(SQLITE_FILE_NAME)
  c = conn.cursor()
  rows = c.execute("SELECT id, lv1id, name, url FROM lv2 WHERE status = 'no' limit 3") # TODO: remove limit
  # 因為後面會用到 cursor, 所以要先暫存起來
  lvs = []
  for row in rows:
    lvs.append((row[0], row[1], row[2], row[3]))

  i = 1
  for lv in lvs:
    url = urlparse.urljoin(HOME_PAGE, lv[3])
    print 'get %s(%s/%s): %s' % (lv[2], i, len(lvs), url)
    i = i + 1
    string = urllib2.urlopen(url).read()

    # 處理亂碼的部分
    fsencode = sys.getfilesystemencoding() # 系统默认编码
    htmlencode = chardet.detect(string).get('encoding', 'utf-8') # 通过第3方模块来自动提取网页的编码
    string = string.decode(htmlencode, 'ignore').encode(fsencode) # 先转换成unicode编码，然后转换系统编码输出

    # replace all font tags
    string = re.sub(ur'\<\/?font[^>]*>', '', string)
    # get all elements in ul
    string = re.sub(ur'.*\<ul>(.*)\<\/ul>.*', r'\1', string)
    # match elemtns in li tag
    match = re.findall(ur"\<li>\<a href='(.*?)'>(.*?)\<\/a>(.*?)\<\/li>", string)
    result = []
    for url, name, desc in match:
      name = name.decode('GB2312', 'ignore')
      desc = desc.decode('GB2312', 'ignore')
      result.append((lv[0], lv[1], name, url, desc))
    c.executemany("INSERT INTO lv3(lv1id, lv2id, name, url, desc, status) VALUES(?, ?, ?, ?, ?, 'no')", result)
    c.execute("UPDATE lv2 SET status = 'yes' WHERE id = %s" % (lv[0]))
    conn.commit() # 每一批就存一次
  conn.close()

def getLevel4():
  conn = sqlite3.connect(SQLITE_FILE_NAME)
  c = conn.cursor()
  rows = c.execute("SELECT id, lv1id, lv2id, name, url FROM lv3 WHERE status = 'no' LIMIT 1") # TODO: remove limit
  # 因為後面會用到 cursor, 所以要先暫存起來
  lvs = []
  for row in rows:
    lvs.append((row[0], row[1], row[2], row[3], row[4]))
  i = 1
  for lv in lvs:
    result = {}
    url = urlparse.urljoin(HOME_PAGE, lv[4])
    url = 'http://business.com.tw/com/com.asp?id=1yiepp7ns9h8m6j'
    print 'get %s(%s/%s): %s' % (lv[3], i, len(lvs), url)
    i = i + 1
    string = urllib2.urlopen(url).read()
    parser = etree.HTMLParser()
    html = etree.fromstring(string, parser)
    # 找 logo
    select = cssselect.CSSSelector(r'font img')
    items = select(html)
    result['logo'] = (items and [urlparse.urljoin(HOME_PAGE, items[0].get("src"))] or [''])[0]
    # 找 公司名 + 官網
    select = cssselect.CSSSelector(r'font a')
    items = select(html)
    result['name'] = items[0].text
    result['page'] = items[0].get("href")
    # 找 





    print '------------------'
    print result

def runit(msg):
  clear = lambda: os.system('cls')
  #clear()
  if msg:
    print msg
  print """
    1: drop and create table
    2: get level 1 data
    3: get level 2 data 
    4: get level 3 data
    5: get level 4 data
    others/empty: quit()
  """
  cmd = raw_input("Please enter cmd: ")
  if cmd == '1':
    print ">> drop and create tables"
    dropAndCreateTable()
    msg = "== drop and create table okay =="
  elif cmd == '2':
    print ">> get level 1 data..."
    getLevel1()
    msg = "== get level 1 data okay =="
  elif cmd == '3':
    print ">> get level 2 data..."
    getLevel2()
    msg = '== get level 2 data okay =='
  elif cmd == '4':
    print ">> get level 3 data..."
    getLevel3()
    msg = '== get level 3 data okay =='
  elif cmd == '5':
    print ">> get level 4 data..."
    getLevel4()
    msg = '== get level 4 data okay =='
  else:
    sys.exit()

  return msg


if __name__ == '__main__':
  msg = ''
  while True:
    msg = runit(msg)

