"""

newsreader module

Gets RSS-formatted text from a web-based news feed or from a local file and
extracts the content as plain text.

"""

import os
import time
try:
    from urllib.request import urlopen  # Python 3.3
except ImportError:
    from urllib import urlopen  # Python 2.7
import re
from pykob import log

def getArticles(url):
    if url[:7] == 'file://':
        s = open(os.getcwd() + '/' + url[7:]).read()
    else:
        retry = True
        while retry:
            try:
                s = urlopen(url).read().decode('utf-8')
                retry = False
            except:
                log.err('Can\'t open {}.'.format(url))
                time.sleep(5)
    articles = re.findall('<item>.*?</item>', s, re.IGNORECASE+re.DOTALL)
    for i in range(0, len(articles)):
        title, description, pubDate = None, None, None
        m = re.search('<title>(.*?)</title>',
                articles[i], re.IGNORECASE+re.DOTALL)
        if m:
            title = m.group(1)
        m = re.search('<description>(.*?)</description>',
                articles[i], re.IGNORECASE+re.DOTALL)
        if m:
            description = m.group(1)
            flags = re.IGNORECASE + re.DOTALL
            description = re.sub('&lt;.*?&gt;', '', description, 0, flags)
            description = re.sub('&amp;#039;', "'", description, 0, flags)
            description = re.sub('&amp;.*?;', ' ', description, 0, flags)
        m = re.search('<pubDate>(.*?)</pubDate>',
                articles[i], re.IGNORECASE+re.DOTALL)
        if m:
            pubDate = m.group(1)
        articles[i] = title, description, pubDate
    return articles
