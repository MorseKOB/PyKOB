"""
MIT License

Copyright (c) 2020 PyKOB - MorseKOB in Python

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

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
        m = re.search('<title>(<!\[CDATA\[)?(.*?)(\]\]>)?</title>',
                articles[i], re.IGNORECASE+re.DOTALL)
        if m:
            title = m.group(2)
        m = re.search('<description>(<!\[CDATA\[)?(.*?)(\]\]>)?</description>',
                articles[i], re.IGNORECASE+re.DOTALL)
        if m:
            description = m.group(2)
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
