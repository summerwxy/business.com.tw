#!/usr/bin/env python
# -*- coding: utf-8 -*-

from urllib.request import urlopen
import urllib.request
import os.path
import json
from lxml import etree, cssselect
import codecs
import sqlite3
import sys, os, re
import urllib.parse
import chardet
import time


HOME_PAGE = 'http://business.com.tw/prod/productc1.htm'
SQLITE_FILE_NAME = 'data.db'

def dropAndCreateTable():
  conn = sqlite3.connect(SQLITE_FILE_NAME)
  c = conn.cursor()
  c.execute('DROP TABLE IF EXISTS lv1')
  c.execute('CREATE TABLE IF NOT EXISTS lv1(id INTEGER PRIMARY KEY ASC, name TEXT, url TEXT, status TEXT)')
  c.execute('DROP TABLE IF EXISTS lv2')
  c.execute('CREATE TABLE IF NOT EXISTS lv2(id INTEGER PRIMARY KEY ASC, lv1id INTEGER, name TEXT, url TEXT, status TEXT)')
  c.execute('DROP TABLE IF EXISTS lv3')
  c.execute('CREATE TABLE IF NOT EXISTS lv3(id INTEGER PRIMARY KEY ASC, lv1id INTEGER, lv2id INTEGER, name TEXT, url TEXT, desc TEXT, status TEXT)')
  c.execute('DROP TABLE IF EXISTS lv4')
  c.execute('CREATE TABLE IF NOT EXISTS lv4(id INTEGER PRIMARY KEY ASC, lv1id INTEGER, lv2id INTEGER, lv3id INTEGER, logo TEXT, name TEXT, page TEXT, info TEXT, desc TEXT, others TEXT, midd TEXT, email TEXT)')
  conn.commit()
  conn.close()

def getLevel1():
  # 抓首頁的 html source code
  string = urllib.request.urlopen(HOME_PAGE).read()
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
  rows = c.execute("SELECT id, name, url FROM lv1 WHERE status = 'no' ") # TODO: remove limit
  # 因為後面會用到 cursor, 所以要先暫存起來
  lvs = []
  for row in rows:
    lvs.append((row[0], row[1], row[2]))

  i = 1
  for lv in lvs:
    url = urllib.parse.urljoin(HOME_PAGE, lv[2])
    print('get %s(%s/%s): %s' % (lv[1], i, len(lvs), url))
    i = i + 1
    string = urllib.request.urlopen(url).read()
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
  rows = c.execute("SELECT id, lv1id, name, url FROM lv2 WHERE status = 'no' limit 50") # TODO: remove limit
  # 因為後面會用到 cursor, 所以要先暫存起來
  lvs = []
  for row in rows:
    lvs.append((row[0], row[1], row[2], row[3]))

  i = 1
  for lv in lvs:
    url = urllib.parse.urljoin(HOME_PAGE, lv[3])
    print('get %s(%s/%s): %s' % (lv[2], i, len(lvs), url))
    i = i + 1
    string = urllib.request.urlopen(url).read()
    parser = etree.HTMLParser()
    html = etree.fromstring(string, parser)
    select = cssselect.CSSSelector(r'li a')
    items = select(html)
    result = []
    for item in items:
      name = item.text
      url = item.get('href')
      foo = item.getparent().getchildren()
      desc = (len(foo) == 3 and [foo[2].text] or [item.getparent().getnext().text])[0]
      result.append((lv[1], lv[0], name, url, desc))
    c.executemany("INSERT INTO lv3(lv1id, lv2id, name, url, desc, status) VALUES(?, ?, ?, ?, ?, 'no')", result)
    c.execute("UPDATE lv2 SET status = 'yes' WHERE id = %s" % (lv[0]))
    conn.commit() # 每一批就存一次
  conn.close() 

def getLevel4():
  conn = sqlite3.connect(SQLITE_FILE_NAME)
  c = conn.cursor()
  rows = c.execute("SELECT id, lv1id, lv2id, name, url FROM lv3 WHERE status = 'no' limit 1") # TODO: remove limit
  # 因為後面會用到 cursor, 所以要先暫存起來
  lvs = []
  for row in rows:
    lvs.append((row[0], row[1], row[2], row[3], row[4]))
  i = 1
  for lv in lvs:
    result = {}
    result['lv1id'] = lv[1]
    result['lv2id'] = lv[2]
    result['lv3id'] = lv[0]
    url = urllib.parse.urljoin(HOME_PAGE, lv[4])
    print('get %s(%s/%s): %s' % (lv[3], i, len(lvs), url))
    i = i + 1
    string = urllib.request.urlopen(url).read()
    parser = etree.HTMLParser()
    html = etree.fromstring(string, parser)
    # 找 logo
    select = cssselect.CSSSelector(r'font img')
    items = select(html)
    result['logo'] = (items and [urllib.parse.urljoin(HOME_PAGE, items[0].get("src"))] or [''])[0]
    # 找 公司名 + 官網
    select = cssselect.CSSSelector(r'font a')
    items = select(html)
    if items:
      result['name'] = items[0].text
      result['page'] = items[0].get("href")
    else: # 有些公司沒官網
      select = cssselect.CSSSelector(r'font b nobr')
      items = select(html)
      result['name'] = items[0].text
      result['page'] = ''

    # 找 info + desc 
    select = cssselect.CSSSelector(r'table td')
    items = select(html)
    result['info'] = "|||".join([it for it in items[0].itertext()])
    result['desc'] = "|||".join([it for it in items[1].itertext()])
    # 找 others
    select = cssselect.CSSSelector(r'center')
    items = select(html)
    result['others'] = ((len(items) == 2) and ["|||".join([it for it in items[1].itertext()])] or [''])[0]
    # 找 midd
    select = cssselect.CSSSelector(r'form input[name=midd]')
    items = select(html)
    if items:
      result['midd'] = items[0].get('value')
    else: # 有些公司沒 email
      result['midd'] = ''
    # insert and update sqlite 
    c.execute("INSERT INTO lv4(lv1id, lv2id, lv3id, logo, name, page, info, desc, others, midd, email) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')", (result['lv1id'], result['lv2id'], result['lv3id'], result['logo'], result['name'], result['page'], result['info'], result['desc'], result['others'], result['midd']))
    c.execute("UPDATE lv3 SET status = 'yes' WHERE id = %s" % (lv[0]))
    conn.commit() # 每一批就存一次
  conn.close()


def getLevel5():
  conn = sqlite3.connect(SQLITE_FILE_NAME)
  c = conn.cursor()
  rows = c.execute("SELECT midd, email FROM lv4 WHERE midd <> '' and email IN ('', '1', '2') limit 7") # TODO: remove limit
  # 因為後面會用到 cursor, 所以要先暫存起來
  ids = []
  for row in rows:
    ids.append((row[0], row[1]))
  i = 1
  x = 0
  for id in ids:
    if x >= 5: # n 次錯誤就停止
      break
    try:
      params = urllib.parse.urlencode({'midd': id[0]}).encode(encoding='UTF8')
      url = "http://business.com.tw/scripts/mail.asp"
      req = urllib.request.Request(url, params)
      con = urllib.request.urlopen(req)
      html = con.read()
      email = re.sub(r'.*mailto:(.*)\?subject.*', r'\1', str(html))
      con.close()
      c.execute("UPDATE lv4 SET email = '%s' WHERE midd = '%s'" % (email, id[0]))
      conn.commit() # 每一批就存一次
      print("%s/%s: %s %s" % (i, len(ids), id[0], email))
      i = i + 1
      time.sleep(3) # sleep n 秒   7 NG  8 OK
    except Exception as err:
      # 照到道理說不會出現 4 的情況
      email = (id[1] == '' and ['1'] or id[1] == '1' and ['2'] or id[1] == '2' and ['3'] or ['4'])[0]
      c.execute("UPDATE lv4 SET email = '%s' WHERE midd = '%s'" % (email, id[0]))
      conn.commit()
      print("%s/%s: %s fail %s times" % (i, len(ids), id[0], email))
      i = i + 1
      x = x + 1
      time.sleep(3) # sleep n 秒   7 NG  8 OK

  conn.close()

def runit(msg):
  clear = lambda: os.system('cls')
  # clear()
  if msg:
    print(msg)
  print("""
    TABLES: 刪除table重新建(指令是大寫)
    13579: get level 1 data(每次都會抓新的)
    2: get level 2 data(如果中斷會繼續抓)
    3: get level 3 data(如果中斷會繼續抓)
    4: get level 4 data(如果中斷會繼續抓)
    5: get email data(如果中斷會繼續抓)
    (輸入其他不認識的命令): quit program
    注意基本上都是 insert 所以 level 1 資料抓取多次
    那後面的 2 3 4 會出現多份資料
    抓太多次(可能是 1000)會變成 404 錯誤
    換 ip 或是過好幾個小時 可以解決

  """)
  cmd = input("Please enter cmd: ")
  if cmd == 'TABLES':
    print(">> drop and create tables")
    dropAndCreateTable()
    msg = "== drop and create table okay =="
  elif cmd == '13579':
    print(">> get level 1 data...")
    getLevel1()
    msg = "== get level 1 data okay =="
  elif cmd == '2':
    print(">> get level 2 data...")
    getLevel2()
    msg = '== get level 2 data okay =='
  elif cmd == '3':
    print(">> get level 3 data...")
    getLevel3()
    msg = '== get level 3 data okay =='
  elif cmd == '4':
    print(">> get level 4 data...")
    getLevel4()
    msg = '== get level 4 data okay =='
  elif cmd == '5':
    print(">> get email data...")
    getLevel5()
    msg = '== get email data okay =='
  else:
    sys.exit()

  return msg


if __name__ == '__main__':
  msg = ''
  while True:
    msg = runit(msg)

