#!/usr/bin/env python

from __future__ import with_statement

import os
import sys
import re
import shutil
import logging
from optparse import OptionParser
from datetime import datetime

logger = logging.getLogger("kelvin")
def enable_logging():
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def load_app_engine_paths():
    (drive, tail) = os.path.splitdrive(__file__)
    gae_basedir = None
    if drive == '':
        gae_basedir = os.path.join('/', 'usr', 'local')
    else:
        gae_basedir = os.path.join(drive, 'Program Files')
    app_engine_dir = os.path.join(gae_basedir, 'google_appengine')
    for x in ((), ('lib', 'django'), ('lib', 'yaml', 'lib'), ('lib', 'webob')):
        path = app_engine_dir
        for c in x:
            path = os.path.join(path, c)
        sys.path.append(os.path.join(app_engine_dir, path))
load_app_engine_paths()

import yaml

from django import template
from django.template import loader
from django.conf import settings

import textile

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
                t = loader.get_template(self.layout)
            else:
                logger.debug("using file as its own layout: [%s]" % self.body)
                t = loader.get_template_from_string(self.body)
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
        self.posts = []
        self.pages = []
        self.files = []
        self.items = None
        self.time = datetime.now()
        settings.configure(
            DEBUG = True, 
            TEMPLATE_DEBUG = True,
            TEMPLATE_LOADERS = (
                'django.template.loaders.filesystem.load_template_source',
                ),
            TEMPLATE_DIRS = (
                os.path.join(self.source_dir, '_layouts'),
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
            outdir = os.path.join(self.dest_dir, "category", topic)
            if not os.path.exists(outdir):
                os.makedirs(outdir)
            with open(os.path.join(outdir, "index.html"), "w") as outfile:
                output = loader.render_to_string("topic.html",
                                                 {'page': {'title':'All %s Posts' % topic},
                                                  'site': self,
                                                  'topic' : topic,
                                                  'posts' : self.topics[topic]})
                outfile.write(output)
            

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
    usage = """

Command Line variants:
%prog [options]                                     # current dir -> _site
%prog [options] <path to output>                    # current dir -> <output>
%prog [options] <path to source> <path to output>   # <input> -> <output>
"""
    parser = OptionParser(usage = usage)
    # Enables trace logging.  our callback needs 4 parameters, so we just use a
    # lambda function as a wrapper
    parser.add_option("-d", "--debug",
                      help = "print out debugging trace information",
                      action = "callback",
                      callback = lambda w, x, y, z: enable_logging())
    (options, args) = parser.parse_args()
    dirname = os.path.dirname(__file__)
    source_dir = os.path.join(dirname, '.site')
    dest_dir = os.path.join(dirname, '_site')
    if len(args) == 2:
        source_dir = args[0]
        dest_dir = args[1]
    elif len(args) == 1:
        dest_dir = args[0]

    site = Site(source_dir, dest_dir)
    site.transform()

if __name__ == "__main__":
    main()
