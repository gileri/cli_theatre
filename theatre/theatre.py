#!/usr/bin/env python3

PROGRAM_NAME="cli_theatre"

#import npyscreen

# debug stuff
from pprint import pprint

import os
import sys
import click
import subprocess
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
logger.addHandler(logging.StreamHandler())

_db = Database()

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
    def find_sub(self, item, language):
        q = select(li for li in LibraryItem 
                if  li.type == 'episodesubtitle'
                and li.series == item.series
                and li.season == item.season
                and li.episodeNumber == item.episodeNumber)
        # TODO Aloow user to choose a subtitle if multiple are found
        return q.first()

@click.group()
@click.option('-v', '--verbose',
              help="Verbosity level",
              type=int,
              default=2)
@click.option('-c', '--config',
              help="Path to a config file",
              type=click.Path(exists=True, dir_okay=False),
              default=os.path.join(BaseDirectory.load_first_config(PROGRAM_NAME), 'config'))
@click.option('-d', '--db',
              help="Path to the sqlite database file",
              type=click.Path(dir_okay=False, writable=True),
              default=os.path.join(BaseDirectory.load_first_config(PROGRAM_NAME), 'db.sqlite'))
# TODO allow multiple library paths
@click.option('--library',
              help="Path to the media library",
              type=click.Path(exists=True, file_okay=False))
def cli(config, db, library, verbose):
    """Manage a media library"""
    global l,_config

    log_levels = [
        logging.CRITICAL,
        logging.ERROR,
        logging.WARNING,
        logging.INFO,
        logging.DEBUG,
    ]
    logger.setLevel(log_levels[verbose] if verbose <= len(log_levels) else logging.DEBUG)

    if not config:
        # TODO explain
        logger.warn("Configuration not found")
    logger.info('Config path: %s', config)
    _config = configparser.ConfigParser()
    _config.read(config)

    if db:
        db_path = str(db)
    elif 'db' in _config['library']:
        db_path = _config['library']['db']
    else:
        logger.critical("SQLite database file not defined")
        sys.exit(1)
    logger.info('DB path : %s', db_path)

    l = Library()
    if library:
        l.path = library
    elif 'path' in _config['library']:
        l.path = _config['library']['path']
    else:
        logger.critical("Media library path not defined")
        sys.exit(1)
    logger.info('Library path : %s', l.path)

    _db.bind('sqlite', db_path, create_db=True)
    _db.generate_mapping(create_tables=True)

@cli.command()
def scan():
    l._find_obsolete()
    l._scan_fs()
    l._analyze(LibraryItem.select())

@cli.command()
@click.option('-t', '--title',
              help="Title of the series",
              prompt=True)
@click.option('-s', '--season',
              help="Season",
              prompt=True,
              type=int)
@click.option('-e', '--episode',
              help="Episode",
              prompt=True,
              type=int)
def find(title, season, episode):
    for i in l._find(title, season, episode):
        print(i)

@cli.command()
@click.option('-t', '--title',
              prompt=True,
              help="Title of the series")

@click.option('-s', '--season',
              prompt=True,
              help="Season",
              type=click.INT)

@click.option('-e', '--episode',
              prompt=True,
              help="Episode",
              type=click.INT)

@click.option('-l', '--language',
              help="Language of subtitles wanted")
def play(title, season, episode, language):
    """Play a media file"""
    media = l._find(title=title, season=season, episode=episode)
    if len(media) == 0:
        logger.warn("No media found")
        sys.exit(0)
    if len(media) > 1:
        click.echo('Multiple episode found, please choose one :')
        for i,m in enumerate(media):
            click.echo('%d. %s' % (i, m))
        choice = click.prompt('Your choice :', type=int)
    else:
        choice = 0
    if not language:
        if 'sub_language' in _config['library']:
            language = _config['library']['sub_language']
        else:
            language = click.prompt("Subtitle language :")
    sub = l.find_sub(media[choice], language)
    if not sub:
        pass
    subprocess.call(['mpv', '--sub-file=%s' % (sub.path,), media[choice].path ])
    # execute actual player here

if __name__ == '__main__':
    cli()
