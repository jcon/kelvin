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

def is_page(dir, name):
    header = open(os.path.join(SOURCE_DIR, dir, name)).read(3)
    return header == "---"

class File:
    def __init__(self, dir, name):
        self.dir = dir
        self.name = name

    def open(self):
        return open(os.path.join(SOURCE_DIR, self.dir, self.name))

    def outdir(self):
        return os.path.join(DEST_DIR, self.dir)

    def outfile(self):
        return self.name

    def mkdirs(self):
        if not os.path.exists(self.outdir()):
            os.makedirs(self.outdir())
        return self.outdir()

    def source(self):
        return os.path.join(SOURCE_DIR, self.dir, self.name)

    def destination(self):
        return os.path.join(self.outdir(), self.outfile())

    def output(self, site):
        outdir = self.mkdirs()
        shutil.copy(self.source(), os.path.join(outdir, self.outfile()))

class Page(File):
    def __init__(self, dir, name):
        File.__init__(self, dir, name)
        self.content = self.open().read()
        self.read_data()

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

    def outfile(self):
        m = re.match(r'([^.]*)\.([^.]*)$', self.name)
        if m and m.group(2) == "textile":
            return "%s.html" % m.group(1)
        else:
            return self.name

class Post(Page):
    def __init__(self, dir, name):
        Page.__init__(self, dir, name)
#        m = re.match(r'^(\d+)-(\d+)-(\d+)-(.*)$', self.name)
        m = re.match(r'^(\d+)-(\d+)-(\d+)-([^.]*).*$', self.name)
        date_string = "%s %s %s" % (m.group(1), m.group(2), m.group(3))
        self.date = datetime.strptime(date_string, "%Y %m %d")
        self.url = "/%s/%s/%s/%s.html" % (m.group(1), m.group(2), m.group(3), m.group(4))
        
    def topics(self):
        return re.split(r'/', self.dir)[1:]

    def outdir(self):
        dirs = os.path.split(self.dir)
        if len(dirs) > 1:
            dir = dirs[1:]
        else:
            dir = '/'
        m = re.match(r'^(\d+)-(\d+)-(\d+)-(.*)$', self.name)
        return os.path.join(DEST_DIR, m.group(1), m.group(2), m.group(3))

    def outfile(self):
        m = re.match(r'^(\d+)-(\d+)-(\d+)-([^.]*).*$', self.name)
        return "%s.html" % m.group(4)

class Site:
    def __init__(self):
        self.posts = []
        self.pages = []
        self.files = []
        self.items = None

    def all_items(self):
        if self.items == None:
            self.load_items()
            self.items = []
            self.items.extend(self.files)
            self.items.extend(self.pages)
            self.items.extend(self.posts)

        return self.items

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
                elif is_page(basedir, f):
                    self.pages.append(Page(basedir, f))
                else:
                    self.files.append(File(basedir, f))

        def post_cmp(left, right):
            return -1 * cmp(left.date, right.date)
        self.posts.sort(post_cmp)
        for topic in post.topics():
            self.topics[topic].sort(post_cmp)


def main():
    site = Site()
    for p in site.all_items():
        logger.debug(p.__class__.__name__ + "|%(dir)s|%(name)s" % vars(p))
        p.output(site)
    for topic in site.topics.keys():
        logger.info("Creating topic: %s" % topic)
        with open(os.path.join(TEMPLATE_DIR, "topic.html")) as f:
            t = template.Template(f.read())
            outdir = os.path.join(DEST_DIR, "category", topic)
            if not os.path.exists(outdir):
                os.makedirs(outdir)
            with open(os.path.join(outdir, "index.html"), "w") as outfile:
                outfile.write(t.render(template.Context(
                    {'page': {'title':'All %s Posts' % topic},
                     'site': site,
                     'topic' : topic,
                     'posts' : site.topics[topic]}
                    )))
                        

if __name__ == "__main__":
    main()
