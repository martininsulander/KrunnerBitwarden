#!/bin/env python3
"""
Interface to a secretservice (with the help of secretstorage module)
Provides methods to get search terms, search and get password for an item.

get_terms -> for lookup with search
search -> to find matching items (in Match tuple)
get_secret -> get password from item dbus path

probably
	org.freedesktop.Secret.Service
		OpenSession('plain', input GLib.Variant?)
	-> arg_0, path path != '/' on success
       raise org.freedesktop.DBus.Error.NotSupported

	and then Unlock(path) ??? what path, path or collection path?

TODO
secretstorage
    modes
        no secretservice
        locked secretservice
            pass .... shows an unlock which unlocks pass
        unlocked
            update terms

    on get password
        how to check if locked?
        maybe col from path
"""
import time
import logging
import difflib  # for comparing strings
from typing import List, NamedTuple, Tuple, Any, Final, Literal, Sequence
from contextlib import closing
from secretstorage import dbus_init, Item, get_all_collections
from secretstorage.exceptions import SecretServiceNotAvailableException

log_search = logging.getLogger('search')
log_secret = logging.getLogger('secret')

STATUS = Literal['ok',
                 'Unlock password manager',
                 'Found no SecretService password manager',]
STATUS_OK: Final[STATUS] = 'ok'
STATUS_LOCKED: Final[STATUS] = 'Unlock password manager'
STATUS_NO_SECRETSERVICE: Final[STATUS] = 'Found no SecretService password manager'


class Term(NamedTuple):
    "For searching, connecting value to a path and some extra info"
    label: str
    path: str
    attr: str
    value: str


def get_collections(connection, unlock=False) -> Tuple[bool, List[Any]]:
    "get all collections, unlock them if requested"
    collections = []
    count = 0
    any_locked_collections = False
    for count, col in enumerate(get_all_collections(connection)):
        if col.is_locked():
            if not unlock:
                any_locked_collections = True
                continue
            if col.unlock():
                # failed to unlock
                any_locked_collections = True
                log_secret.warning('Failed to unlock %s', col.collection_path)
                continue
        collections.append(col)
    log_secret.debug('Found %d collections', count)
    return any_locked_collections, collections


def get_terms(exclude_attributes: Sequence[str], unlock=False
        ) -> Tuple[STATUS, List[Term]]:
    "get attributes and values to use for searching later"
    log_search.info('Updating search terms')
    terms: List[Term] = []
    any_locked_collection = False
    try:
        with closing(dbus_init()) as connection:
            any_locked_collection, collections = get_collections(connection, unlock=unlock)
            for col in collections:
                for item in col.get_all_items():
                    for attr, value in item.get_attributes().items():
                        if value and attr not in exclude_attributes:
                            terms.append(
                                Term(
                                    label=item.get_label(),
                                    path=item.item_path,
                                    attr=attr,
                                    value=value))
    except SecretServiceNotAvailableException:
        log_secret.warning('No dbus secretservice provider found')
    if not terms:
        if any_locked_collection:
            log_secret.info('No terms found and some collections where locked')
            return STATUS_LOCKED, []
        else:
            log_secret.warning('No terms found and no unlocked collection,'
                                ' may be missing passwordmanager')
            return STATUS_NO_SECRETSERVICE, []
    return STATUS_OK, terms


class PathPrioMatches:
    "A group of strings (for the same path) with a match priorisation"
    __slot__ = 'prio', 'strings'
    def __init__(self, path):
        self.path: str = path
        self.prio: float = 0
        self.terms: List[Term] = []


def search(terms: List[Term], search_term: str) -> List[PathPrioMatches]:
    "search for a term in prefetched list"
    log_search.debug('Search term: %s', search_term)
    log_ratio = log_search.getChild('ratio')

    matches: List[PathPrioMatches] = []

    if search_term.islower():
        strfix = lambda s: s.lower()
    else:
        strfix = lambda s: s

    count = 0
    diff = difflib.SequenceMatcher(a=search_term, autojunk=False)
    # diff = strsim.NormalizedLevenshtein()
    for count, term in enumerate(terms):
        for compare_with in [term.label, term.value]:
            diff.set_seq2(strfix(compare_with))
            ratio = diff.quick_ratio()
            if ratio < 0.8 and strfix(compare_with).startswith(search_term):
                ratio = 0.8
            if ratio > 0.4:
                log_ratio.debug('%f, text match %s', ratio, compare_with)
                for match in matches:
                    if term.path == match.path:
                        path_match = match
                        break
                else:
                    path_match = PathPrioMatches(term.path)
                    matches.append(path_match)
                if path_match.prio < ratio:
                    path_match.prio = ratio
                path_match.terms.append(term)
            elif ratio > 0:
                log_ratio.debug('%f', ratio)
    log_search.debug('compared %d terms', count)
    return sorted(matches, key=lambda m: m.prio, reverse=True)


def get_secret(item_path: str) -> Tuple[STATUS, bytes]:
    "fetch secret from dbus item path"
    log_secret.debug('Get secret for %s', item_path)
    try:
        with closing(dbus_init()) as connection:
            time.sleep(0.2)  # sometimes needed for items to be populated after unlock
            item = Item(connection, item_path)
            return STATUS_OK, item.get_secret()
    except UnicodeDecodeError:
        log_secret.error('Password cannot be read as UTF-8')
        return STATUS_OK, b''
    except SecretServiceNotAvailableException:
        log_secret.error('The dbus secretservice provider is not running any more')
        return STATUS_NO_SECRETSERVICE, b''


def test():
    "run a test search"
    status, terms = get_terms(['Path'], unlock=True)
    print(status)
    for count, match in enumerate(search(terms, 'martin')):
        if count > 4:
            break
        label = None
        attvals: List[Tuple[str, str]] = []
        for term in match.terms:
            assert not label or label == term.label
            label = term.label
            attvals.append((term.attr, term.value,))
        attvals_str = ', '.join(['%s:%s' % (a, v) for a, v in attvals])
        print(label, attvals_str, match.path)
        #print(get_secret(match.path))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    test()
