#!/bin/env python3
"""
Krunner dbus service to access secretservice enabled password managers.
"""

import logging
from typing import List, Tuple, Dict

import dbus.service

from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

import secret
import clipboard

logging.basicConfig(level=logging.INFO)
log_init = logging.getLogger('init')
log_search = logging.getLogger('search')
log_secret = logging.getLogger('secret')


DBusGMainLoop(set_as_default=True)

APPNAME = 'miSecretserviceKrunner'
OBJPATH = "/mi/secretservice/krunner"
BUSNAME = 'mi.secretservice.krunner'
IFACE = "org.kde.krunner1"

CLIPBOARD_TIMEOUT = 5  # s before clearing password from clipboard
REFRESH_TERMS_TIMEOUT = 50  # s before invalidating search terms
TRIGGER = 'pass '
EXCLUDE_ATTRIBUTES = ('Path', 'Notes', 'Title', 'Uuid')  # don't query these item attributes

MAX_NR_OF_MATCHES = 4

ICON = 'changes-allow-symbolic'

UNLOCK = '_UNLOCK_'


class Runner(dbus.service.Object):
    """Krunner dbus service to query secretservice"""
    def __init__(self):
        dbus.service.Object.__init__(self,
                                     dbus.service.BusName(BUSNAME, dbus.SessionBus()),
                                     object_path=OBJPATH)
        self.refresh_timer = None
        self.clear_clipboard_timer = None
        self.terms = None
        self.update_terms(unlock=False)


    def run(self):
        "Start main loop"
        log_init.info('%s service started', APPNAME)
        GLib.MainLoop().run()


    def refresh_timeout(self):
        "Clear terms refresh timer on timeout"
        log_search.info('terms are old, try to refresh next time')
        self.refresh_timer = None


    def update_terms(self, unlock=False):
        "fetch and store possible search terms from secretservice provider"
        if self.refresh_timer is not None:
            GLib.source_remove(self.refresh_timer)
        else:
            updated_terms = secret.get_terms(EXCLUDE_ATTRIBUTES, unlock=unlock)
            if updated_terms:
                self.terms = updated_terms
            else:
                if not unlock:
                    log_search.warning('Not updated, locked')
                    return
                log_search.error('Cannot unlock and fetch terms')
                log_search.error('maybe no active secretservice password manager enabled')
                # add timer to not strain service in case of errors
        self.refresh_timer = GLib.timeout_add_seconds(REFRESH_TERMS_TIMEOUT, self.refresh_timeout)


    @dbus.service.method(IFACE, in_signature='s', out_signature='a(sssida{sv})')
    def Match(self, query: str):
        """Search for query in terms and respond with matches to display in krunner"""
        if len(query) < len(TRIGGER) + 3:  #  pass 123 at least three characters before querying
            return []
        if not query.startswith(TRIGGER):
            return []

        if not self.terms:
            log_search.info('Ask for unlock')
            return [(UNLOCK, 'Unlock password manager', ICON, 80, 1, {},)]

        query = query[len(TRIGGER):].strip()
        if not query:
            return []

        self.update_terms(unlock=False)

        if not self.terms:
            return [('', 'No password manager found', ICON, 10, 0.1, {},)]

        match: secret.PathPrioMatches
        out: List[Tuple[str, str, str, int, float, Dict[str, str]]] = []
        for match in secret.search(self.terms, query)[:MAX_NR_OF_MATCHES]:
            label = None
            attvals: List[Tuple[str, str]] = []
            term: secret.Term
            for term in match.terms:
                assert not label or label == term.label
                label = term.label
                attvals.append((term.attr, term.value,))
            assert label is not None
            attrvals = ', '.join(['%s:%s' % (attr, val) for attr, val in attvals])
            text = label + ' ' + attrvals
            # 1 data - password
            # 2 display text - description
            # 3 icon
            # 4 MATCH (Plasma::QueryType)
            #   NONE=0 COMPLETION=10 POSSIBLE=30 INFORMATIONAL=50 HELPER=70 COMPLETE=100
            # 5 relevance (0-1) - sort order
            # 6 properties - dict {subtext: category and urls}
            out.append((
                match.path, label, ICON, 100, 0.5, {'subtext': attrvals,},))
            log_search.debug('matched %s %s', text, match.path)
        return out

    @dbus.service.method(IFACE, out_signature='a(sss)')
    def Actions(self):
        "Description of actions available"
        # TODO where is this shown?
        # id description icon
        return [(
            APPNAME,
            "Copy passwords to clipboard (from secret service enabled application)",
            ICON)]

    def clear_clipboard(self):
        "Clear clipboard and clipboard timer on timeout"
        clipboard.clear()
        self.clear_clipboard_timer = None

    @dbus.service.method(IFACE, in_signature='ss')
    def Run(self, data: str, action_id: str):
        "Run an action, action_id is empty for default action"
        log_secret.debug('activate %s (%s)', data, action_id)
        if data == UNLOCK:
            self.update_terms(unlock=True)
        else:
            secret.unlock_all()
            password = secret.get_secret(item_path=data)
            clipboard.put(password)

            if self.clear_clipboard_timer is not None:
                GLib.source_remove(self.clear_clipboard_timer)
            self.clear_clipboard_timer = GLib.timeout_add_seconds(CLIPBOARD_TIMEOUT,
                                                                  self.clear_clipboard)

