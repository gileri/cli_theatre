#!/usr/bin/env python3

PROGRAM_NAME="cli_theatre"

#import npyscreen

# debug stuff
from pprint import pprint

import os
import sys
import argparse
from xdg import BaseDirectory
import configparser
import logging
import time
import guessit
from imdb import IMDb
import fuzzysearch
from pony.orm import *

extension_subs = tuple(e.lower() for e in  ("sub", "srt"))
extension_media = tuple(e.lower() for e in ("mkv", "avi"))

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

db = Database('sqlite', 'test_db.sqlite', create_db=True)

class LibraryItem(db.Entity):
    root = Required(str)
    fileName = Required(str)
    type = Optional(str)
    series = Optional(str)
    season = Optional(int)
    episodeNumber = Optional(int)

    @db_session
    def guess_info(self):
        def merge_info(data, obj):
            if data['type'] == 'unknown':
                return
            properties = {
                'episode': ['season', 'series', 'episodeNumber'],
                'episodesubtitle': ['season', 'series', 'episodeNumber'],
                'movie': [],
                'moviesubtitle': [],
            }
            new_cols = {}
            for p in properties.get(data['type'], []):
                logger.debug('Set %s as %s on %s', p, data[p], obj)
                new_cols[p] = data[p]
            obj.type=data['type']
            obj.set(**new_cols)
        info = guessit.guess_file_info(self.fileName)
        with db_session:
            merge_info(info, self)


    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if self.type in ('movie', 'moviesubtitle'):
            return self.title if hasattr(self, 'title') else 'Movie %s' % self.fileName
        elif self.type in ('episode', 'episodesubtitle'):
            return '%s %s S%02dE%02d' % (self.type, self.series, self.season, self.episodeNumber)
        else:
            return "LibraryItem %s" % self.fileName

db.generate_mapping(create_tables=True)

class Library():
    def __init__(self, path=None, db=None):
        self.path = path
        self.db = db
        self.media = []

    def is_media(self, f):
        return f.lower().endswith(extension_media) or f.lower().endswith(extension_subs)

    def scan(self, args):
        self._find_obsolete()
        self._scan_fs()
        self._analyze(LibraryItem.select())
    
    @db_session
    def _analyze(self, items):
        for item in items:
            try:
                item.guess_info()
                logger.info("Analyzed %s", item)
            except Exception as e:
                logger.exception("Error while analyzing meta-data")

    @db_session
    def _find_obsolete(self):
        for i in LibraryItem.select():
            if os.path.isfile(os.path.join(i.root, i.fileName)):
                continue
            logger.info("Removed %s ", i.fileName)
            i.delete()

    def _scan_fs(self):
        logger.debug("Starting FS scan in %s", self.path)
        for root, dirs, files in os.walk(self.path, followlinks=True):
            with db_session:
                for f in files:
                    if not self.is_media(f):
                        logger.debug("File %s is not media", f)
                        continue
                    if not exists(p for p in LibraryItem if p.fileName == f):
                        i = LibraryItem(root=root, fileName=f)
                        logger.info("Found %s", i)

    @db_session
    def find(self, args):
        q = select(li for li in LibraryItem)
        if args.title:
            q = q.filter(lambda l: args.title.lower() in l.series.lower())
        if args.season:
            q = q.filter(lambda l: l.season == args.season)
        if args.episode:
            q = q.filter(lambda l: l.episodeNumber == args.episode)
        for i in q:
            print(i)

if __name__ == '__main__':
    l = Library()

    commands = {
        'find': l.find,
        'scan': l.scan,
    }
    parser = argparse.ArgumentParser(description='Manage a media library')
    parser.add_argument('command', choices=commands.keys())
    parser.add_argument('-t', '--title',   help="Title of the series")
    parser.add_argument('-s', '--season',  help="Season", type=int)
    parser.add_argument('-e', '--episode', help="Episode", type=int)
    parser.add_argument('-c', '--config',  help="Path to a config file", default=None)
    parser.add_argument('-d', '--db',      help="Path to a config file", default=None)
    # TODO allow multiple library paths
    parser.add_argument('-l', '--library', help="Path to the media library",default=None)
    args = parser.parse_args()

    config_path = args.config_path if args.config else BaseDirectory.load_first_config(PROGRAM_NAME) 
    if config_path == None:
        logger.error("Configuration not defined")
        sys.exit(1)
    config = configparser.ConfigParser()
    config.read(os.path.join(config_path, 'config'))

    if args.db:
        l.db = args.db
    elif 'db' in config['library']:
        l.db = config['library']['db']
    else:
        logger.critical("No database file specified")
        sys.exit(1)
    logger.info('DB path : %s', l.db)

    if args.library:
        l.path = args.library
    elif 'path' in config['library']:
        l.path = config['library']['path']
    else:
        logger.critical('No library path specified')
        sys.exit(1)
    logger.info('Library path : %s', l.path)

    commands[args.command](args)
