#!/usr/bin/env python

import os
from optparse import OptionParser
import kelvin


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
                      callback = lambda w, x, y, z: kelvin.enable_logging())
    (options, args) = parser.parse_args()
    dirname = os.path.dirname(__file__)
    source_dir = os.path.join(dirname, '.site')
    dest_dir = os.path.join(dirname, '_site')
    if len(args) == 2:
        source_dir = args[0]
        dest_dir = args[1]
    elif len(args) == 1:
        dest_dir = args[0]

    site = kelvin.Site(source_dir, dest_dir)
    site.transform()

if __name__ == "__main__":
    main()
