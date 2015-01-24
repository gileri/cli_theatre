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
              type=click.Path(exists=True, dir_okay=False))
@click.option('-d', '--db',
              help="Path to the sqlite database file",
              type=click.Path(dir_okay=False, writable=True))
# TODO allow multiple library paths
@click.option('--library',
              help="Path to the media library",
              type=click.Path(exists=True, file_okay=False))
def cli(config, db, library, verbose, log):
    """Manage a media library"""
    global l, lib_config

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

    basedir = BaseDirectory.load_first_config(__title__)
    if not config:
        if basedir:
            config = os.path.join(basedir, 'config')
        else:
            logger.warn("Configuration file not found.")
    logger.info('Config path: %s', config)
    if config:
        _config = configparser.ConfigParser()
        _config.read(config)
        lib_config = _config['library'] if 'library' in _config else {}
    else:
        lib_config = {}
    if db:
        # DB passed as parameter
        db_path = str(db)
    elif 'db' in lib_config:
        # DB set in config file
        db_path = lib_config['db']
    else:
        working_dir = os.path.join(BaseDirectory.xdg_config_home, __title__)
        if not os.path.isdir(working_dir):
            os.makedirs(working_dir, exist_ok=True)
        db_path = os.path.join(working_dir, 'db.sqlite')
    logger.info('DB path : %s', db_path)
    bind_db(db_path)

    if 'sub_language' in lib_config and len(lib_config['sub_language']) == 2:
        pass  # Should try to convert with babelfish

    if library:
        library_path = library
    elif 'path' in lib_config:
        library_path = lib_config['path']
    else:
        logger.critical("Media library path not defined")
        sys.exit(1)
    l = Library(library_path)
    logger.info('Library path : %s', library_path)


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
        if 'sub_language' in lib_config['library']:
            language = lib_config['library']['sub_language']
        else:
            language = click.prompt("Subtitle language :")
    sub = l.find_sub(media[choice], language)
    if not sub:
        pass
    subprocess.call(['mpv', '--sub-file=%s' % (sub.path,), media[choice].path])


@cli.command()
def gui():
    g = Gui(l, lib_config)
    g.start()

if __name__ == '__main__':
    cli()
