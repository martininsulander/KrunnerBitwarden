#!/usr/bin/python3
"""
Krunner dbus service to access bitwarden command line password manager.
"""

import os
import logging
from typing import List, Tuple, Dict, overload, Final, Literal
import json
import time
import dbus.service  # type: ignore

from dbus.mainloop.glib import DBusGMainLoop  # type: ignore
from gi.repository import GLib  # type: ignore

import clipboard
from bwcli import Bwcli, Entry

log_init = logging.getLogger('init')
log_search = logging.getLogger('search')
log_secret = logging.getLogger('secret')


DBusGMainLoop(set_as_default=True)

APPNAME = 'mi_krunner_bwcli'
OBJPATH = "/mi/bitwarden/krunner"
BUSNAME = 'mi.bitwarden.krunner'
IFACE = "org.kde.krunner1"

CLIPBOARD_TIMEOUT = 5  # s before clearing password from clipboard
BWCLI_SYNC_TIMEOUT = 600  # 10 min between syncing bwcli
TRIGGER = 'pass '
EXCLUDE_ATTRIBUTES = ('Path', 'Notes', 'Title', 'Uuid')  # don't query these item attributes

MAX_NR_OF_MATCHES = 4

ACTION_2 = 'trigger_shift_alternative'  # shift+enter or icon

ICON = 'changes-allow-symbolic'


STATUS = Literal['ok',
                 'Unlock password manager',
                 'Found no SecretService password manager',]
STATUS_OK: Final[STATUS] = 'ok'
STATUS_LOCKED: Final[STATUS] = 'Unlock password manager'
STATUS_NO_SECRETSERVICE: Final[STATUS] = 'Found no SecretService password manager'
STATUS_NO_USERNAME = 'No username'

log_init.info('Setting up Krunner plugin')



class Runner(dbus.service.Object):
    """Krunner dbus service to query secretservice"""

    def __init__(self):
        dbus.service.Object.__init__(self,
                                     dbus.service.BusName(BUSNAME, dbus.SessionBus()),
                                     object_path=OBJPATH)
        self.refresh_timer = None  # used to tell when to sync bw
        self.clear_clipboard_timer = None
        self.bwcli: Bwcli = Bwcli()
        log_init.debug('Runner init')

    def run(self):
        "Start main loop"
        log_init.info('%s service started', APPNAME)
        GLib.MainLoop().run()


    def refresh_timeout(self):
        "Clear terms refresh timer on timeout"
        self.refresh_timer = None
        log_search.info('sync bwcli')
        self.bwcli.sync()
        self.refresh_timer = GLib.timeout_add_seconds(BWCLI_SYNC_TIMEOUT, self.refresh_timeout)


    @dbus.service.method(IFACE, in_signature='s', out_signature='a(sssida{sv})')
    def Match(self, query: str) -> List[Tuple[str, str, str, int, float, Dict[str, str]]]:
        """Search for query in terms and respond with matches to display in krunner

        Main krunner-method for showing results and errors:
        * no secretservice password manager
        * unlock password manager
        * show matching entries"""

        # wait until matching the trigger word
        if not query.startswith(TRIGGER):
            return []

        if not self.bwcli.has_session():
            return [(STATUS_LOCKED, STATUS_LOCKED, ICON, 80, 1, {},)]

        query = query[len(TRIGGER):].strip()
        if not query:
            return []

        log_search.debug('Match query: %s', query)

        entry: Entry
        out: List[Tuple[str, str, str, int, float, Dict[str, str]]] = []
        for prio, entry in list(self.bwcli.search(query))[:MAX_NR_OF_MATCHES]:
            # 1 data - username, password - pickled as a list
            # 2 display text - description
            # 3 icon
            # 4 MATCH (Plasma::QueryType)
            #   NONE=0 COMPLETION=10 POSSIBLE=30 INFORMATIONAL=50 HELPER=70 COMPLETE=100
            # 5 relevance (0-1) - sort order
            # 6 properties - dict {subtext: category and urls}
            if prio > 0.75:
                match_type = 100
            elif prio > 0.5:
                match_type = 70
            else:
                match_type = 10
            data = json.dumps([entry.username, entry.password])
            out.append((data, entry.name, ICON, match_type, prio, {'subtext': entry.subtext,},))
            log_search.debug('matched %f %s %s', prio, entry.name, entry.subtext)#, match.path)
        return out

    @dbus.service.method(IFACE, out_signature='a(sss)')
    def Actions(self):
        "Setup alternative actions"
        # action-id description icon
        # runs at first query
        # log_search.debug('Actions triggered')
        return [(
            ACTION_2,
            "Copy username",
            ICON)]
            # (ACTION3, "possible with more alternatives, but without kbd shortcut")

    def clear_clipboard(self):
        "Clear clipboard and clipboard timer on timeout"
        clipboard.clear()
        self.clear_clipboard_timer = None

    @dbus.service.method(IFACE, in_signature='ss')
    def Run(self, data: str, action_id: str):
        """Run an action
        
        action_id is empty for default action,
        ACTION_2 for second action"""
        log_secret.debug('activate %s (%s)', data, action_id)

        # new action so reset timer. TODO: clear ev password entry
        if self.clear_clipboard_timer is not None:
            GLib.source_remove(self.clear_clipboard_timer)

        if data == STATUS_LOCKED:
            self.bwcli.login()

        else:
            username, password = json.loads(data.encode())

            if action_id == ACTION_2:
                clipboard.put(username)
            else:
                clipboard.put(password)
                self.clear_clipboard_timer = GLib.timeout_add_seconds(CLIPBOARD_TIMEOUT,
                                                                    self.clear_clipboard)



logging.basicConfig(level=logging.INFO)
for key, value in os.environ.items():
    if key.startswith('LOG_'):
        name = key.split('_', 1)[1]
        logging.getLogger(name).setLevel(value)

Runner().run()
