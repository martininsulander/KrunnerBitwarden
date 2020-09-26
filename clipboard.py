#!/usr/bin/python3
from typing import List, NamedTuple, Tuple, Dict
import logging

import dbus

log_clip = logging.getLogger('clipboard')

KLIPPER = 'org.kde.klipper'
KLIPPER_OBJPATH = '/klipper'
KLIPPER_IFACE = 'org.kde.klipper.klipper'


def klipper():
    bus = dbus.SessionBus()
    return bus.get_object(KLIPPER, KLIPPER_OBJPATH)

def clear():
    log_clip.info('clear clipboard')
    klipper().clearClipboardContents(dbus_interface=KLIPPER_IFACE)
    log_clip.debug('clipboard cleared from klipper')

def put(text):
    log_clip.info('put password')
    klipper().setClipboardContents(text, dbus_interface=KLIPPER_IFACE)
    log_clip.debug('password put to klipper')
