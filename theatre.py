#!/usr/bin/env python3

PROGRAM_NAME="cli_theatre"

#import npyscreen

# debug stuff
from pprint import pprint

import os
import sys
from xdg import BaseDirectory
import configparser
import logging
import time
import guessit
from imdb import IMDb
import fuzzysearch
from pony.orm import *

max_threads = 4

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
            properties = {
                'episode': ['season', 'series', 'episodeNumber'],
                'episodesubtitle': ['season', 'series', 'episodeNumber'],
                'movie': [],
                'moviesubtitle': [],
            }
            new_cols = {}
            for p in properties.get(data['type'], []):
                logger.debug('Set %s as %s on %s', p, info[p], obj.fileName)
                new_cols[p] = info[p]
            obj.set(**new_cols)
        info = guessit.guess_file_info(self.fileName)
        with db_session:
            merge_info(info, self)


    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if not hasattr(self, 'info') :
            return self.fileName
        if self.info['type'] in ('movie', 'moviesubtitle'):
            return self.info['title']
        elif self.info['type'] in ('episode', 'episodesubtitle'):
            return self.info['series'] + ' S' + str(self.info['season']).zfill(2) + 'E' + str(self.info['episodeNumber']).zfill(2)
        else:
            return Object.__repr__()

db.generate_mapping(create_tables=True)

class Library():
    def __init__(self, path, db):
        self.path = path
        self.media = []
        self.db = db

    def is_media(self, f):
        return f.lower().endswith(extension_media) or f.lower().endswith(extension_subs)

    def scan_collection(self):
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
        for root, dirs, files in os.walk(self.path, followlinks=True):
            with db_session:
                for f in files:
                    if not self.is_media(f):
                        continue
                    if len(select( p for p in LibraryItem if p.fileName == f)) == 0:
                        # Item doesn't exist in DB yet, add it
                        i = LibraryItem(root=root, fileName=f)
                        logger.debug("Added %s", i)

    @db_session
    def find(name=None, season=None, episode=None):
        for i in select(li for li in LibraryItem):
            pprint(i)

if __name__ == '__main__':
    l_path='/mnt/series'
    config = configparser.ConfigParser()
    config_path = BaseDirectory.load_first_config(PROGRAM_NAME)
    if config_path == None:
        logger.error("Configuration not defined")
        sys.exit(1)
    config.read(os.path.join(config_path, 'config'))
    l_path = config['library']['path']
    l = Library(l_path, db)
    if sys.argv[1] == 'scan':
        l.scan_collection()
    elif sys.argv[1] == 'find':
        l.find()
