#!/usr/bin/env python3

import os
import sys

with open(sys.argv[1]) as f:
    for p in f:
        p = p.rstrip('\n')
        try:
            os.makedirs(os.path.join('mock', os.path.dirname(p)))
        except FileExistsError:
            pass
        open(os.path.join('mock', p), 'a').close()
