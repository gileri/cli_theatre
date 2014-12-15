#!/usr/bin/env python3

from pony.orm import *
import logging
import os
import guessit

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())

extension_subs = tuple(e.lower() for e in  ("sub", "srt"))
extension_media = tuple(e.lower() for e in ("mkv", "avi"))

_db = Database()

def bind_db(db_path):
    _db.bind('sqlite', db_path, create_db=True)
    _db.generate_mapping(create_tables=True)

class Library():
    def __init__(self, path=None):
        self.path = path

    def is_media(self, f):
        return f.lower().endswith(extension_media) or f.lower().endswith(extension_subs)
    
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
    def _find(self, title=None, season=None, episode=None):
        q = select(li for li in LibraryItem if li.type == 'episode')
        if title:
            q = q.filter(lambda i: title.lower() in i.series.lower())
        if season:
            q = q.filter(lambda i: i.season == season)
        if episode:
            q = q.filter(lambda i: i.episodeNumber == episode)
        logger.debug("Find query returned %d results", q.count())
        return q[:]

    @db_session
    def find_series(self):
        q = select(li.series for li in LibraryItem)
        return q[:]

    @db_session
    def find_sub(self, item, language):
        q = select(li for li in LibraryItem 
                if  li.type == 'episodesubtitle'
                and li.series == item.series
                and li.season == item.season
                and li.episodeNumber == item.episodeNumber)
        # TODO Aloow user to choose a subtitle if multiple are found
        return q.first()

class LibraryItem(_db.Entity):
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

    @property
    def path(self):
        return os.path.join(self.root, self.fileName)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if self.type in ('movie', 'moviesubtitle'):
            return self.title if hasattr(self, 'title') else 'Movie %s' % self.fileName
        elif self.type in ('episode', 'episodesubtitle'):
            return "{0.type} {0.series} S{0.season:02d}E{0.episodeNumber:02d} {0.fileName}".format(self)
        else:
            return "LibraryItem %s" % self.fileName