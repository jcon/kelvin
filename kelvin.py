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

#from google.appengine.ext.webapp import template

import textile
import yaml

SOURCE_DIR = os.path.join(DIRNAME, '.site')
DEST_DIR = os.path.join(DIRNAME, '_site')
TEMPLATE_DIR = os.path.join(SOURCE_DIR, '_layouts')
# TEMPLATE_DIRS = (
#      os.path.join(SOURCE_DIR, '_layouts')
# )


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
#os.environ['DJANGO_SETTINGS_MODULE'] = u"settings"
#register = template.Library()

#os.environ['DJANGO_SETTINGS_MODULE'] = u"settings"
#from django.templategoogle.appengine.ext.webapp.template import loader
#print loader.get_template("post.html")

# def render(template_file, values = {}):
#         path = os.path.join(os.path.dirname(__file__), 'templates', template_file)
#         return template.render(path, values)

#template.add_to_builtins(__name__)
#template.add_to_builtins('django.contrib.markup.templatetags.markup') #__name__)

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
            logging.debug("no match in %(content)s" % vars(self))

#     def translate(self):
# #        print("**** [%(name)s]" % vars(self))
#         if re.search(r'\.textile$', self.name):
# #            print("**** TRANSLATING: %(name)s" % vars(self))
# #            print("**** %(name)s *****\n\n %(content)s\n\n ****" % vars(self))
#             self.body = textile.textile(str(self.content))
# #        else:
#             self.body = self.content

    def output(self, site):
        outdir = self.mkdirs()
        with open(self.destination(), 'w') as f:
            if self.layout != 'nil':
                tf = open(os.path.join(TEMPLATE_DIR, self.layout))
                s = tf.read()
            else:
                s = self.body

#                print "*** template\n%s\n*****" % s
            t = template.Template(s) #tf.read())
            data = {
                'site':site,
                'page':self
                }
            print site.posts
#            data.update(self.data)
#            f.write(t.render(template.Context(data))) #self.content)
            self.content = t.render(template.Context(data))
            print "****\n%s\n****" % self.content
#            else:
#                self.content = self.body
#            print("**** %(content)s" % vars(self))
#            self.translate()
            f.write(self.content)
#            print ("writing source! %(name)s" % vars(self))

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
    
    def categories(self):
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
            self.items = []
            for i in self.walk():
                self.items.append(i)
        return self.items
            
    def walk(self):
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
                    self.posts.append(Post(basedir, f))
                    yield self.posts[-1:][0]
                elif is_page(basedir, f):
                    self.pages.append(Page(basedir, f))
                    yield self.pages[-1:][0]
                else:
                    self.files.append(File(basedir, f))
                    yield self.files[-1:][0]


def main():
    site = Site()
#    for p in site.walk():
    for p in site.all_items():
        print p.__class__.__name__ + "|%(dir)s|%(name)s" % vars(p)

#        if hasattr(p, "translate"):
#            getattr(p, "translate")()

        p.output(site)

if __name__ == "__main__":
    main()
