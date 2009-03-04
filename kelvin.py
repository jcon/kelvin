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

import textile
import yaml

#SOURCE_DIR = os.path.join(DIRNAME, '.site')
#DEST_DIR = os.path.join(DIRNAME, '_site')
#TEMPLATE_DIR = os.path.join(SOURCE_DIR, '_layouts')

from django import template
from django.template import loader
from django.conf import settings


class File:
    def __init__(self, source_dir, dest_dir, dir, name):
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.dir = dir
        self.name = name
        self.outdir = os.path.join(self.dest_dir, self.dir)
        self.outfile = self.name

    def open(self):
        return open(os.path.join(self.source_dir, self.dir, self.name))

    def mkdirs(self):
        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)
        return self.outdir

    def destination(self):
        return os.path.join(self.outdir, self.outfile)

    def output(self, site):
        outdir = self.mkdirs()
        source = os.path.join(self.source_dir, self.dir, self.name)
        shutil.copy(source, self.destination()) 

class Page(File):
    def __init__(self, source_dir, dest_dir, dir, name):
        File.__init__(self, source_dir, dest_dir, dir, name)
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
                tf = open(os.path.join(site.template_dir, self.layout))
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
    def __init__(self, source_dir, dest_dir, dir, name):
        Page.__init__(self, source_dir, dest_dir, dir, name)
#        m = re.match(r'^(\d+)-(\d+)-(\d+)-(.*)$', self.name)
        m = re.match(r'^(\d+)-(\d+)-(\d+)-([^.]*).*$', self.name)
        date_string = "%s %s %s" % (m.group(1), m.group(2), m.group(3))
        self.date = datetime.strptime(date_string, "%Y %m %d")
        self.url = "/%s/%s/%s/%s.html" % (m.group(1), m.group(2), m.group(3), m.group(4))
        self.outdir = os.path.join(self.dest_dir, m.group(1), m.group(2), m.group(3))
        self.outfile = "%s.html" % m.group(4)
        
    def topics(self):
        return re.split(r'/', self.dir)[1:]

class Site:
    def __init__(self, source_dir, dest_dir):
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.template_dir = os.path.join(self.source_dir, '_layouts')
        self.posts = []
        self.pages = []
        self.files = []
        self.items = None
        self.time = datetime.now()
        settings.configure(
            DEBUG=True, 
            TEMPLATE_DEBUG=True,
            TEMPLATE_DIRS = (    
                self.template_dir,
                ),
            INSTALLED_APPS = (
                'django.contrib.markup',
                )
            )


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
            with open(os.path.join(self.template_dir, "topic.html")) as f:
                t = template.Template(f.read())
                outdir = os.path.join(self.dest_dir, "category", topic)
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
        for root, dirs, files in os.walk(self.source_dir):
            basedir = root[6:]
            if re.match('^\.site/.git', root):
                continue

            for f in files:
                if re.match(r'(?:.*~$|\.DS_Store|\.gitignore)', f):
                    continue
                elif re.match(r'^\.site/_layouts', root):
                    continue
                elif re.match(r'^\.site/_posts', root):
                    post = Post(self.source_dir, self.dest_dir, basedir, f)
                    self.posts.append(post)
                    for topic in post.topics():
                        if not self.topics.has_key(topic):
                            self.topics[topic] = []
                        self.topics[topic].append(post)
                elif self.is_page(basedir, f):
                    self.pages.append(Page(self.source_dir, self.dest_dir, basedir, f))
                else:
                    self.files.append(File(self.source_dir, self.dest_dir, basedir, f))

        def post_cmp(left, right):
            return -1 * cmp(left.date, right.date)
        self.posts.sort(post_cmp)
        for topic in self.topics:
            self.topics[topic].sort(post_cmp)

    def is_page(self, dir, name):
        header = open(os.path.join(self.source_dir, dir, name)).read(3)
        return header == "---"


def main():
    SOURCE_DIR = os.path.join(DIRNAME, '.site')
    DEST_DIR = os.path.join(DIRNAME, '_site')

    site = Site(SOURCE_DIR, DEST_DIR)
    site.transform()

if __name__ == "__main__":
    main()
