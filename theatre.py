#!/usr/bin/env python3

from theatre.library import *
from theatre.gui import Gui
from theatre import __title__
logger = logging.getLogger("theatre")

import os
import sys
import click
import subprocess
from xdg import BaseDirectory
import configparser


@click.group()
@click.option('-v', '--verbose',
              help="Verbosity level",
              default='warning')
@click.option('--log',
              help="Where to write log output",
              type=click.File(mode='w'),
              default=sys.stderr)
@click.option('-c', '--config',
              help="Path to a config file",
              type=click.Path(exists=True, dir_okay=False),
              default=os.path.join(BaseDirectory.load_first_config(__title__), 'config'))
@click.option('-d', '--db',
              help="Path to the sqlite database file",
              type=click.Path(dir_okay=False, writable=True),
              default=os.path.join(BaseDirectory.load_first_config(__title__), 'db.sqlite'))
# TODO allow multiple library paths
@click.option('--library',
              help="Path to the media library",
              type=click.Path(exists=True, file_okay=False))
def cli(config, db, library, verbose, log):
    """Manage a media library"""
    global l, _config

    log_levels = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL,
    }
    if verbose not in log_levels:
        logger.error('Wrong log level : %s', verbose)
        verbose = 'warning'
    logger.setLevel(log_levels[verbose])
    logger.addHandler(logging.StreamHandler(log))

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
    bind_db(db_path)

    if len(_config['library']['sub_language']) == 2:
        pass  # Should try to convert with babelfish

    l = Library()
    if library:
        l.path = library
    elif 'path' in _config['library']:
        l.path = _config['library']['path']
    else:
        logger.critical("Media library path not defined")
        sys.exit(1)
    logger.info('Library path : %s', l.path)


@cli.command()
def scan():
    l.find_obsolete()
    l.scan_fs()
    l.analyze(LibraryItem.select())


@cli.command()
@click.option('-t', '--title',
              help="Title of the series",
              prompt=True)
@click.option('-s', '--season',
              help="Season",
              type=int)
@click.option('-e', '--episode',
              help="Episode",
              type=int)
def find(title, season, episode):
    if not episode:
        try:
            season = int(click.prompt('Season [any]', type=str, default=''))
        except ValueError:
            season = None
    if not episode:
        try:
            episode = int(click.prompt('Episode [any]', type=str, default=''))
        except ValueError:
            episode = None
    for i in l.find(title, season, episode):
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
    media = l.find(title=title, season=season, episode=episode)
    if len(media) == 0:
        logger.warn("No media found")
        sys.exit(0)
    if len(media) > 1:
        print('Multiple episode found, please choose one :')
        for i, m in enumerate(media):
            print('%d. %s' % (i, m))
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
    subprocess.call(['mpv', '--sub-file=%s' % (sub.path,), media[choice].path])


@cli.command()
def gui():
    g = Gui(l, _config)
    g.start()

if __name__ == '__main__':
    cli()
