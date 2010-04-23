#!/usr/bin/env python

from __future__ import with_statement

import os
import sys
import re
import shutil
import logging
from datetime import datetime

import yaml
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger("kelvin")
def enable_logging():
    """
    Configures console logging for the application's logger.  By
    default, logging operations will not output log statements
    unless the logger has been configured.  The main driver of
    kelvin will control this with a commandline flag.
    """
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def datetimeformat(value, format='%d %b %Y'):
    """
    Simple filter for jinja2 to help print out dates nicely
    """
    return value.strftime(format)

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
                t = site.env.get_template(self.layout)
            else:
                logger.debug("using file as its own layout: [%s]" % self.body)
                t = site.env.from_string(self.body)
            data = {
                'tuple':(('one', '1'), ('two', '2'), ('three', '3')),
                'site':site,
                'page':self
                }
            logger.debug(site.posts)
            self.content = t.render(site=site, page=self)
            logger.debug("****\n%s\n****" % self.content)
            f.write(self.content)
#            logger.debug("writing source! %(name)s" % vars(self))

    def __getattr__(self, name):
#        logging.debug("Page:getattr(%s):" % name)
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
        
    def categories(self):
        return re.split(r'/', self.dir)[1:]
        
    def __str__(self):
        return "%s (%s)" % (self.title, self.url)

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
        self.template_dirs = (
            os.path.join(self.source_dir, '_layouts'),
        )
        self.env = Environment(loader=FileSystemLoader(self.template_dirs))
        self.env.filters['datetimeformat'] = datetimeformat


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

        self.render_categories(self.categories, "category.html", "category")    
    
    def render_categories(self, categories, template_name, basedir):
        try:
            t = self.get_template(template_name)
        except:
            logger.warning("No category template defined: %s, skipping output" % template_name)
            return
            
        for category in categories.keys():
            logger.info("Creating category: %s" % category)
            outdir = os.path.join(self.dest_dir, basedir, category)
            if not os.path.exists(outdir):
                os.makedirs(outdir)
            with open(os.path.join(outdir, "index.html"), "w") as outfile:
                output = t.render(page={'title':'All %s Posts' % category},
                                    site=self,
                                    category=category,
                                    posts=categories[category])
                outfile.write(output)
                    
    def load_items(self):
        self.categories = { }
        for root, dirs, files in os.walk(self.source_dir):
            basedir = root[len(self.source_dir) + 1:]
            if re.match('^.git', basedir):
                logging.debug("skipping tree %s" % basedir)
                continue
            logging.debug("basedir: %s" % basedir)
            for f in files:
                if re.match(r'(?:.*~$|\.DS_Store|\.gitignore|\.git)', f):
                    logging.debug("skipping file %s" % f)
                    continue
                elif re.match(r'^_extensions$', basedir):
                    continue
                elif re.match(r'^_layouts', basedir):
                    continue
                elif re.match(r'^_posts', basedir):
                    post = Post(self.source_dir, self.dest_dir, basedir, f)
                    self.posts.append(post)
                    for category in post.categories():
                        if not self.categories.has_key(category):
                            self.categories[category] = []
                        self.categories[category].append(post)
                elif self.is_page(basedir, f):
                    self.pages.append(Page(self.source_dir, self.dest_dir, basedir, f))
                else:
                    self.files.append(File(self.source_dir, self.dest_dir, basedir, f))

        def post_cmp(left, right):
            return -1 * cmp(left.date, right.date)
        self.posts.sort(post_cmp)
        for category in self.categories:
            self.categories[category].sort(post_cmp)

    def is_page(self, dir, name):
		logging.debug("is page: %s: %s" % (dir, name))
		header = open(os.path.join(self.source_dir, dir, name)).read(3)
		return header == "---"

    def get_template(self, template):
        return self.env.get_template(template)