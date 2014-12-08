#!/usr/bin/env python3

import os
import sys

with open(sys.argv[1]) as f:
    for p in f:
        try:
            os.makedirs(os.path.join('mock', os.path.dirname(p)))
            open(p, 'a').close()
        except:
            pass
