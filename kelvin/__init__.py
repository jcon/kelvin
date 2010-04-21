#!/usr/bin/env python

from __future__ import with_statement

import os
import sys
import re
import shutil
import logging
from datetime import datetime

logger = logging.getLogger("kelvin")
def enable_logging():
    """
    Configures console logging for the application's logger.  By
    default, logging operations will not output log statements
    unless the logger has been configured.
    """
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def load_app_engine_paths():
    # (drive, tail) = os.path.splitdrive(__file__)
    # gae_basedir = None
    # if drive == '':
    #     gae_basedir = os.path.join('/', 'usr', 'local')
    # else:
    #     gae_basedir = os.path.join(drive, 'Program Files')
    # app_engine_dir = os.path.join(gae_basedir, 'google_appengine')
    # for x in ((), ('lib', 'django'), ('lib', 'yaml', 'lib'), ('lib', 'webob')):
    #     path = app_engine_dir
    #     for c in x:
    #         path = os.path.join(path, c)
    #     sys.path.append(os.path.join(app_engine_dir, path))
  sys.path.append(os.path.join('dependencies', 'django'))
  sys.path.append(os.path.join('dependencies', 'pyyaml', 'lib'))
  sys.path.append(os.path.join('dependencies', 'textile'))
load_app_engine_paths()

import yaml

from django import template
from django.template import loader
from django.conf import settings

    
class File:
    """
    Base class for any time of object on the site.  The file object
    provides basic file related options for translating a file from
    the source folder to the destination site folder.
    """
    def __init__(self, source_dir, dest_dir, dir, name):
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.dir = dir
        self.name = name
        self.outdir = os.path.join(self.dest_dir, self.dir)
        self.outfile = self.name

    def open(self):
        """
        Returns a file object referencing the source file option
        suitable for reading.
        """
        return open(os.path.join(self.source_dir, self.dir, self.name))

    def mkdirs(self):
        """
        Optionally creates the directories in this file's outdir
        path.
        """
        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)
        return self.outdir

    def destination(self):
        """
        The fully qualified destination path for this file.
        """
        return os.path.join(self.outdir, self.outfile)

    def output(self, site):
        """
        Translates the source file to its destination form.  For
        a plain file, this operation is a purely a copy.  For 
        deratives of this class, additional transformation may 
        occur by overriding this method.  This method takes a reference
        to the underlying site so that it may apply site data
        as part of its transformation.
        """
        outdir = self.mkdirs()
        source = os.path.join(self.source_dir, self.dir, self.name)
        shutil.copy(source, self.destination()) 

class Page(File):
    """
    A Page is a special type of file that contains a metadata header
    and content.  In order to promote re-use, pages use Django's 
    template mechnaism.
    
    The metadata header included in a page uses YAML for simplified
    data definition.  Below is a sample header section.
    The YAML metdata properties are accessible in the Django templates
    under the page variable.  The only special YAML property is the
    layout property.  If layout is defined, page will expect to find
    a template under <site>/_layouts with that name.  If layout is
    undefined, the page itself is considered a root Django template.
    ---
    title: My Interesting Page
    blurb: Some text that I can refer to using {{ page.blurb }} in 
    my template
    ---
    """
    def __init__(self, source_dir, dest_dir, dir, name):
        File.__init__(self, source_dir, dest_dir, dir, name)
        self.content = self.open().read()
        self.read_data()
        m = re.match(r'([^.]*)\.([^.]*)$', self.name)
        if m and m.group(2) == "textile":
            self.outfile = "%s.html" % m.group(1)

    def read_data(self):
        """
        Read the metdata and parse it using the YAML parser. 
        It's variables are exposed as attributes directly on this
        page instance.
        """
        m = re.match(r'^---\s*\n(.*?)\n---\s*\n', 
                     self.content, re.MULTILINE | re.DOTALL)
        if m:
            self.data = yaml.load(m.group(1))
            self.body = self.content[len(m.group(0)):]
        else:
            logger.debug("no match in %(content)s" % vars(self))

    def output(self, site):
        """
        Translate this page in memory and output it to its
        destination.
        """
        outdir = self.mkdirs()
        with open(self.destination(), 'w') as f:
            logger.debug("data is %s" % self.data)
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
        logger.debug("Site#init source %s; dest %s" % (source_dir, dest_dir))
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
        logger.info("doing Site.transform()")
        self.load_items()
        items = []
        items.extend(self.posts)
        items.extend(self.files)
        items.extend(self.pages)
        for p in items:
            logger.debug(p.__class__.__name__ + "|%(dir)s|%(name)s" % vars(p))
            p.output(self)
            

    def load_items(self):
        self.topics = { }
        for root, dirs, files in os.walk(self.source_dir):
            basedir = root[len(self.source_dir) + 1:]
            if re.match('^\.site/.git', root):
                continue
            print "basedir: %s" % basedir
            for f in files:
                if re.match(r'(?:.*~$|\.DS_Store|\.gitignore)', f):
                    continue
                elif re.match(r'^_extensions$', basedir):
                    continue
                elif re.match(r'^_layouts', basedir):
                    continue
                elif re.match(r'^_posts', basedir):
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
		print "%s: %s" % (dir, name)
		header = open(os.path.join(self.source_dir, dir, name)).read(3)
		return header == "---"

