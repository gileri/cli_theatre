#!/usr/bin/env python3

#import npyscreen

# debug stuff
from pprint import pprint

import os
import sys
import queue
import threading
from queue import Queue
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
    path = Required(str)
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
                logger.debug('Set %s as %s on %s', p, info[p], obj.path)
                new_cols[p] = info[p]
            obj.set(**new_cols)
        info = guessit.guess_file_info(self.path)
        merge_info(info, self)


    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if not hasattr(self, 'info') :
            return self.path
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
        q = Queue()
        self.fs_thread = threading.Thread(target=self._scan_fs, args=(q,))
        self.fs_thread.start()
        for i in range(max_threads - 1):
            threading.Thread(target=self._analyze, args=(q,)).start()
        q.join()
    
    def _analyze(self, q):
        while self.fs_thread.is_alive():
            try:
                item = q.get(block=True, timeout=0.5)
                item.guess_info()
                logger.debug("Added %s", item)
                q.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                logger.exception("Analyzing meta-data")

    def _scan_fs(self, q):
        for root, dirs, files in os.walk(self.path, followlinks=True):
            with db_session:
                for f in files:
                    if not self.is_media(f):
                        continue
                    if len(select( p for p in LibraryItem if p.path == f)) == 0:
                        # Item doesn't exist in DB yet, add it
                        i = LibraryItem(root=root, path=f)
                        q.put(item=i)

    @db_session
    def find(name=None, season=None, episode=None):
        for i in select(li for li in LibraryItem):
            pprint(i)

if __name__ == '__main__':
    # TODO configure this via external file
    l_path='/mnt/series'
    l = Library(l_path, db)
    if sys.argv[1] == 'scan':
        scan_thread = threading.Thread(target=l.scan_collection)
        scan_thread.start()

        scan_thread.join()
    elif sys.argv[1] == 'find':
        l.find()
