#!/usr/bin/env python

from __future__ import with_statement

import os
import sys
DIRNAME=os.path.dirname(__file__)
for x in ('/', '/lib/django', '/lib/yaml/lib', '/lib/webob'):
    sys.path.append(os.path.join(DIRNAME, '.google_appengine' + x))

import re
import shutil
import logging

logger = logging.getLogger("kelvin")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(levelname)s - %(message)s")
ch.setFormatter(formatter)
#logger.addHandler(ch)

from datetime import datetime

#from google.appengine.ext.webapp import template

import textile
import yaml

SOURCE_DIR = os.path.join(DIRNAME, '.site')
DEST_DIR = os.path.join(DIRNAME, '_site')
TEMPLATE_DIR = os.path.join(SOURCE_DIR, '_layouts')

from django import template
from django.template import loader
from django.conf import settings

settings.configure(
    DEBUG=True, 
    TEMPLATE_DEBUG=True,
    TEMPLATE_DIRS = (    
        TEMPLATE_DIR,
        ),
    INSTALLED_APPS = (
        'kelvin_tags',
        'django.contrib.markup',
        )
    )

class File:
    def __init__(self, dir, name):
        self.dir = dir
        self.name = name
        self.outdir = os.path.join(DEST_DIR, self.dir)
        self.outfile = self.name

    def open(self):
        return open(os.path.join(SOURCE_DIR, self.dir, self.name))

    def mkdirs(self):
        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)
        return self.outdir

    def destination(self):
        return os.path.join(self.outdir, self.outfile)

    def output(self, site):
        outdir = self.mkdirs()
        source = os.path.join(SOURCE_DIR, self.dir, self.name)
        shutil.copy(source, self.destination()) 

class Page(File):
    def __init__(self, dir, name):
        File.__init__(self, dir, name)
        self.content = self.open().read()
        self.read_data()
        m = re.match(r'([^.]*)\.([^.]*)$', self.name)
        if m and m.group(2) == "textile":
            self.outfile = "%s.html" % m.group(1)

    def read_data(self):
        m = re.match(r'^---\s*\n(.*?)\n---\s*\n', 
                     self.content, re.MULTILINE | re.DOTALL)
        if m:
            self.data = yaml.load(m.group(1))
            self.body = self.content[len(m.group(0)):]
        else:
            logger.debug("no match in %(content)s" % vars(self))

    def output(self, site):
        outdir = self.mkdirs()
        with open(self.destination(), 'w') as f:
#            if self.layout != 'nil':
            if self.data.has_key('layout'):
                logger.debug("using layout: %s" % self.layout)
                tf = open(os.path.join(TEMPLATE_DIR, self.layout))
                s = tf.read()
            else:
                logger.debug("using file as its own layout: [%s]" % self.body)
                s = self.body
            t = template.Template(s) #tf.read())
            data = {
                'site':site,
                'page':self
                }
            logger.debug(site.posts)
#            f.write(t.render(template.Context(data))) #self.content)
            self.content = t.render(template.Context(data))
            logger.debug("****\n%s\n****" % self.content)
            f.write(self.content)
#            logger.debug("writing source! %(name)s" % vars(self))

    def __getattr__(self, name):
        if self.data.has_key(name):
            return self.data[name]
        else:
            raise AttributeError("%s is not found in %s" % (name, type(self)))

class Post(Page):
    def __init__(self, dir, name):
        Page.__init__(self, dir, name)
#        m = re.match(r'^(\d+)-(\d+)-(\d+)-(.*)$', self.name)
        m = re.match(r'^(\d+)-(\d+)-(\d+)-([^.]*).*$', self.name)
        date_string = "%s %s %s" % (m.group(1), m.group(2), m.group(3))
        self.date = datetime.strptime(date_string, "%Y %m %d")
        self.url = "/%s/%s/%s/%s.html" % (m.group(1), m.group(2), m.group(3), m.group(4))
        self.outdir = os.path.join(DEST_DIR, m.group(1), m.group(2), m.group(3))
        self.outfile = "%s.html" % m.group(4)
        
    def topics(self):
        return re.split(r'/', self.dir)[1:]

class Site:
    def __init__(self):
        self.posts = []
        self.pages = []
        self.files = []
        self.items = None

    def transform(self):
        self.load_items()
        items = []
        items.extend(self.posts)
        items.extend(self.files)
        items.extend(self.pages)
        for p in items:
            logger.debug(p.__class__.__name__ + "|%(dir)s|%(name)s" % vars(p))
            p.output(self)

        for topic in self.topics.keys():
            logger.info("Creating topic: %s" % topic)
            with open(os.path.join(TEMPLATE_DIR, "topic.html")) as f:
                t = template.Template(f.read())
                outdir = os.path.join(DEST_DIR, "category", topic)
                if not os.path.exists(outdir):
                    os.makedirs(outdir)
                with open(os.path.join(outdir, "index.html"), "w") as outfile:
                    outfile.write(t.render(template.Context(
                                {'page': {'title':'All %s Posts' % topic},
                                 'site': self,
                                 'topic' : topic,
                                 'posts' : self.topics[topic]}
                                )))

    def load_items(self):
        self.topics = { }
        for root, dirs, files in os.walk(SOURCE_DIR):
            basedir = root[6:]
            if re.match('^\.site/.git', root):
                continue

            for f in files:
                if re.match(r'(?:.*~$|\.DS_Store|\.gitignore)', f):
                    continue
                elif re.match(r'^\.site/_layouts', root):
                    continue
                elif re.match(r'^\.site/_posts', root):
                    post = Post(basedir, f)
                    self.posts.append(post)
                    for topic in post.topics():
                        if not self.topics.has_key(topic):
                            self.topics[topic] = []
                        self.topics[topic].append(post)
                elif self.is_page(basedir, f):
                    self.pages.append(Page(basedir, f))
                else:
                    self.files.append(File(basedir, f))

        def post_cmp(left, right):
            return -1 * cmp(left.date, right.date)
        self.posts.sort(post_cmp)
        for topic in self.topics:
            self.topics[topic].sort(post_cmp)

    def is_page(self, dir, name):
        header = open(os.path.join(SOURCE_DIR, dir, name)).read(3)
        return header == "---"


def main():
    site = Site()
    site.transform()

if __name__ == "__main__":
    main()
