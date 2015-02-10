# TODO license

from theatre.library import *

logger = logging.getLogger("theatre.gui")

import curses
import subprocess


class Gui():
    def __init__(self, l, config):
        logger.debug("Initializing GUI")
        self.l = l
        self.config = config
        self.menu_level = 0
        self.sel_series = None
        self.sel_season = None
        self.sel_episode = None
        self.y_viewport = 0
        self.pos = 0
        self.titles = ["Series", "Seasons", "Episodes"]

    def get_items(self):
        """ Return items by menu depth (series > season > episodes) """
        if self.menu_level == 0:
            return self.l.find_series()
        elif self.menu_level == 1:
            return self.l.find_seasons(self.sel_series)
        elif self.menu_level == 2:
            return self.l.find_episodes(self.sel_series, self.sel_season)
    
    def save_chosen(self, item):
        levels = ["sel_series", "sel_season", "sel_episode"]
        setattr(self, levels[self.menu_level], item)

    def draw_menu(self, items, pos, title=""):
        win_y, win_x = self.screen.getmaxyx()
        win_y -=1 # Substract title from vertical size
        self.y_viewport = max(pos - win_y+1, min(self.y_viewport, pos))
        self.screen.clear()
        self.screen.addstr(0, 0, title)
        for n, i in enumerate(items[self.y_viewport:self.y_viewport+win_y]):
            self.screen.addstr(n+1, 2, str(i) if i else "<empty>", self.h_s if n+self.y_viewport == pos else self.n_s)

    def play(self):
        language = self.config['sub_language']
        sub = self.l.find_sub(self.sel_episode, language)
        if not sub:
            path = self.sel_episode.download_sub(language)
            sub = self.l.scan_file(path)[0]
            self.l.analyze([sub])
        logger.info('Playing %s with sub %s', self.sel_episode.path, sub.path)
        self.reset_screen()
        subprocess.call(['mpv', '--sub-file=%s' % (sub.path,), self.sel_episode.path])
        self.init_screen()

    def init_screen(self):
        self.h_s = curses.color_pair(1)
        self.n_s = curses.A_NORMAL
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        self.screen.keypad(True)
        self.screen.clear()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)

    def reset_screen(self):
        curses.nocbreak()
        self.screen.keypad(False)
        curses.echo()
        curses.endwin()
    def refresh_screen(self):
        self.items = self.get_items()
        self.draw_menu(self.items, self.pos, self.titles[self.menu_level])

    def gui(self, stdscr):
        self.screen = stdscr
        self.init_screen()
        x = None
        saved_pos = 0
        self.refresh_screen()
        while x != ord('q'):
            x = stdscr.getch()
            if x == curses.KEY_DOWN and len(self.items) > 0:
                self.pos = (self.pos + 1) % len(self.items)
            elif x == curses.KEY_NPAGE and len(self.items) > 0:
                self.pos = (self.pos + self.y_viewport) % len(self.items)
            elif x == curses.KEY_UP and len(self.items) > 0:
                self.pos = (self.pos - 1) % len(self.items)
            elif x == curses.KEY_PPAGE and len(self.items) > 0:
                self.pos = (self.pos - self.y_viewport) % len(self.items)
            elif x == ord('u'):
                logger.debug('Updating database from TUI')
                self.l.update(callback=self.refresh_screen)
                logger.debug('Finished updating')
            elif x == ord('\n') or x == curses.KEY_RIGHT:
                self.save_chosen(self.items[self.pos])
                saved_pos = self.pos
                self.pos = 0
                if self.menu_level >= 2:
                    self.play()
                else:
                    self.menu_level = min(self.menu_level + 1, 2)
            elif x in (8, 127) or x == curses.KEY_LEFT:  # backspace
                self.pos = saved_pos
                self.menu_level = max(self.menu_level - 1, 0)
            self.refresh_screen()
        exit()

    def start(self):
        curses.wrapper(self.gui)
