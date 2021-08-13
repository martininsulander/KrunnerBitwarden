#!/usr/bin/python3
import logging
import os

logging.basicConfig(level=logging.INFO)
logging.getLogger('search.ratio').setLevel(logging.INFO)
# LOG_=DEBUG ./install.sh

for key, value in os.environ.items():
    if key.startswith('LOG_'):
        name = key.split('_', 1)[1]
        logging.getLogger(name).setLevel(value)

from krunner import Runner

Runner().run()
