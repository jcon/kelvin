#!/usr/bin/env python

from __future__ import with_statement

from typing import Any, TextIO, cast, Callable, Dict, List, Match
import os
import re
import shutil
import logging
from datetime import datetime

from yaml import load as yaml_load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader  # type: ignore
from jinja2 import Environment, FileSystemLoader, Template

DEFAULT_SETTINGS = {
    "CATEGORY_TEMPLATE": "category.html",
    "CATEGORY_OUTPUT_DIR": "category",
}


class NullHandler(logging.Handler):
    """
    Simple bit-bucket handler to use for when debugging is not enabled
    """

    def emit(self, record: Any) -> None:
        """Discards all logging records"""
        pass


logger = logging.getLogger("kelvin")
logger.addHandler(NullHandler())


def enable_logging() -> None:
    """
    Configures console logging for the application's logger.  By, Dumper
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


def datetimeformat(value: datetime, format: str = "%d %b %Y") -> str:
    """
    Simple filter for jinja2 to help print out dates nicely
    """
    return value.strftime(format)


class File:
    source_dir: str
    dest_dir: str
    dir: str
    name: str
    outdir: str
    outfile: str

    """
    Base class for any time of object on the site.  The file object
    provides basic file related options for translating a file from
    the source folder to the destination site folder.
    """

    def __init__(self, source_dir: str, dest_dir: str, dir: str, name: str):
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.dir = dir
        self.name = name
        self.outdir = os.path.join(self.dest_dir, self.dir)
        self.outfile = self.name

    def open(self) -> TextIO:
        """
        Returns a file object referencing the source file option
        suitable for reading.
        """
        return open(os.path.join(self.source_dir, self.dir, self.name))

    def mkdirs(self) -> str:
        """
        Optionally creates the directories in this file's outdir
        path.
        """
        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)
        return self.outdir

    def destination(self) -> str:
        """
        The fully qualified destination path for this file.
        """
        return os.path.join(self.outdir, self.outfile)

    def output(self, site: "Site") -> None:
        """
        Translates the source file to its destination form.  For
        a plain file, this operation is a purely a copy.  For
        deratives of this class, additional transformation may
        occur by overriding this method.  This method takes a reference
        to the underlying site so that it may apply site data
        as part of its transformation.
        """
        _ = self.mkdirs()
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

    content: str
    body: str
    data: Dict[str, str]

    def __init__(self, source_dir: str, dest_dir: str, dir: str, name: str) -> None:
        File.__init__(self, source_dir, dest_dir, dir, name)
        self.content = self.open().read()
        self.read_data()
        m = re.match(r"([^.]*)\.([^.]*)$", self.name)
        if m and m.group(2) == "textile":
            self.outfile = "%s.html" % m.group(1)

    def read_data(self) -> None:
        """
        Read the metdata and parse it using the YAML parser.
        It's variables are exposed as attributes directly on this
        page instance.
        """
        m = re.match(
            r"^---\s*\n(.*?)\n---\s*\n", self.content, re.MULTILINE | re.DOTALL
        )
        if m:
            self.data = yaml_load(m.group(1), Loader=Loader)
            self.body = self.content[len(m.group(0)) :]
        else:
            logger.debug("no match in %(content)s" % vars(self))

    def output(self, site: "Site") -> None:
        """
        Translate this page in memory and output it to its
        destination.
        """
        _ = self.mkdirs()
        with open(self.destination(), "w") as f:
            logger.debug("data is %s" % self.data)
            if "layout" in self.data:
                logger.debug("using layout: %s" % self.layout)
                t = site.env.get_template(self.layout)
            else:
                logger.debug("using file as its own layout: [%s]" % self.body)
                t = site.env.from_string(self.body)
            # data: Dict[str, Any] = {
            #     'tuple':(('one', '1'), ('two', '2'), ('three', '3')),
            #     'site':site,
            #     'page':self
            #     }
            logger.debug(site.posts)
            self.content = t.render(site=site, page=self)
            logger.debug("****\n%s\n****" % self.content)
            f.write(self.content)

    #            logger.debug("writing source! %(name)s" % vars(self))

    def __getattr__(self, name: str) -> str:
        #        logging.debug("Page:getattr(%s):" % name)
        if name in self.data:
            return self.data[name]
        else:
            raise AttributeError("%s is not found in %s" % (name, type(self)))


class Post(Page):
    def __init__(self, source_dir: str, dest_dir: str, dir: str, name: str):
        Page.__init__(self, source_dir, dest_dir, dir, name)
        m = re.match(r"^(\d+)-(\d+)-(\d+)-([^.]*).*$", self.name)
        if m == None:
            raise Exception("Unexpected name format")
        m = cast(Match[str], m)  # Needed by mypy, pyright says its unnecessary
        date_string = "%s %s %s" % (m.group(1), m.group(2), m.group(3))
        self.date = datetime.strptime(date_string, "%Y %m %d")
        self.url = "/%s/%s/%s/%s.html" % (
            m.group(1),
            m.group(2),
            m.group(3),
            m.group(4),
        )
        self.outdir = os.path.join(self.dest_dir, m.group(1), m.group(2), m.group(3))
        self.outfile = "%s.html" % m.group(4)

    def categories(self) -> List[str]:
        return re.split(r"/", self.dir)[1:]

    def __str__(self) -> str:
        return "%s (%s)" % (self.title, self.url)


class Site:
    posts: List[Post]
    files: List[File]
    pages: List[Page]
    categories: Dict[str, List[Post]]
    env: Environment

    def __init__(self, source_dir: str, dest_dir: str):
        logger.debug("Site#init source %s; dest %s" % (source_dir, dest_dir))
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.posts = []
        self.pages = []
        self.files = []
        self.items = None
        self.time = datetime.now()
        self.template_dirs = (os.path.join(self.source_dir, "_layouts"),)
        self.env = Environment(loader=FileSystemLoader(self.template_dirs))
        self.env.filters["datetimeformat"] = datetimeformat

        self.settings = dict(DEFAULT_SETTINGS)
        try:
            # allow sites to override settings by adding all properties
            # defined within _extensions.settings
            from _extensions import settings  # type: ignore

            for setting in dir(
                settings
            ):  # not needed by mypy, but an error for pyright
                if setting == setting.upper():
                    self.settings[setting] = getattr(settings, setting)
        except:
            # In case someone needs to debug a problem in the site's settings files
            logger.exception("no site specific settings or overrides found")

    def transform(self) -> None:
        logger.info("doing Site.transform()")
        self.load_items()
        items: List[File] = []
        items.extend(self.posts)
        items.extend(self.files)
        items.extend(self.pages)
        for p in items:
            logger.debug(p.__class__.__name__ + "|%(dir)s|%(name)s" % vars(p))
            p.output(self)

        self.render_categories(
            self.categories,
            self.settings["CATEGORY_TEMPLATE"],
            self.settings["CATEGORY_OUTPUT_DIR"],
        )

    def render_categories(
        self, categories: Dict[str, List[Post]], template_name: str, basedir: str
    ) -> None:
        try:
            t = self.get_template(template_name)
        except:
            logger.warning(
                "No category template defined: %s, skipping output" % template_name
            )
            return

        for category in categories.keys():
            logger.info("Creating category: %s" % category)
            outdir = os.path.join(self.dest_dir, basedir, category)
            if not os.path.exists(outdir):
                os.makedirs(outdir)
            with open(os.path.join(outdir, "index.html"), "w") as outfile:
                output = t.render(
                    page={"title": "All %s Posts" % category},
                    site=self,
                    category=category,
                    posts=categories[category],
                )
                outfile.write(output)

    def load_items(self) -> None:
        self.categories = {}
        for root, _, files in os.walk(self.source_dir):
            basedir = root[len(self.source_dir) + 1 :]
            # skip all dot directories
            if re.match("^\..*", basedir):
                logger.debug("skipping tree %s" % basedir)
                continue
            logger.debug("basedir: %s" % basedir)
            for f in files:
                if re.match(r"(?:.*~$|\.DS_Store|\.gitignore|\.git)", f):
                    logger.debug("skipping file %s" % f)
                    continue
                elif re.match(r"^_extensions$", basedir):
                    continue
                elif re.match(r"^_layouts", basedir):
                    continue
                elif re.match(r"^_posts", basedir):
                    post = Post(self.source_dir, self.dest_dir, basedir, f)
                    self.posts.append(post)
                    for category in post.categories():
                        if not category in self.categories:
                            self.categories[category] = []
                        self.categories[category].append(post)
                elif self.is_page(basedir, f):
                    self.pages.append(Page(self.source_dir, self.dest_dir, basedir, f))
                else:
                    self.files.append(File(self.source_dir, self.dest_dir, basedir, f))

        post_date: Callable[[Post], datetime] = lambda p: p.date
        self.posts.sort(key=post_date, reverse=True)
        for category in self.categories:
            self.categories[category].sort(key=post_date, reverse=True)

    def is_page(self, dir: str, name: str) -> bool:
        logger.debug("is page: %s: %s" % (dir, name))
        header = open(os.path.join(self.source_dir, dir, name)).read(3)
        return header == "---"

    def get_template(self, template: str) -> Template:
        return self.env.get_template(template)
