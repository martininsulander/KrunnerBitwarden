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
import logging
import difflib  # for comparing strings
from contextlib import closing
from secretstorage import dbus_init, Item, get_all_collections
from secretstorage.exceptions import SecretServiceNotAvailableException

log_search = logging.getLogger('search')
log_secret = logging.getLogger('secret')


class Term(NamedTuple):
    "For searching, connecting value to a path and some extra info"
    label: str
    path: str
    attr: str
    value: str


def unlock_all():
    "Unlock all collections"
    log_secret.info('Unlock password manager')
    get_collections(unlock=True)


def get_collections(unlock=False, connection=None):
    "get all collections, unlock them if requested"
    collections = []
    if not connection:
        connection = dbus_init()
    count = 0
    for count, col in enumerate(get_all_collections(connection)):
        if col.is_locked():
            if not unlock:
                continue
            if col.unlock():
                # failed to unlock
                log_secret.warning('Failed to unlock %s', col.collection_path)
                continue
        collections.append(col)
    if not connection:
        connection.close()
        log_secret.debug("No dbus connection for getting collections")
    else:
        log_secret.debug('Found %d collections', count)
    return collections


def get_terms(exclude_attributes: List[str], unlock=False) -> List[Term]:
    "get attributes and values to use for searching later"
    log_search.info('Updating search terms')
    terms: List[Term] = []
    try:
        with closing(dbus_init()) as connection:
            for col in get_collections(connection=connection, unlock=unlock):
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
    return terms


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

    matches: List[PathPrioMatches] = []

    if search_term.islower():
        strfix = lambda s: s.lower()
    else:
        strfix = lambda s: s

    diff = difflib.SequenceMatcher(a=search_term)
    for term in terms:
        for compare_with in [term.label, term.value]:
            diff.set_seq2(strfix(compare_with))
            ratio = diff.quick_ratio()
            if ratio > 0.3:
                for match in matching_terms:
                    if term.path == match.path:
                        path_match = match
                        break
                else:
                    path_match = PathPrioMatches(term.path)
                    matches.append(path_match)
                if path_match.prio < ratio:
                    path_match.prio = ratio
                path_match.terms.append(term)

    return sorted(matches, key=lambda m: m.prio)


def get_secret(item_path: str) -> Optional[str]:
    "fetch secret from dbus item path"
    log_secret.debug('Get secret for %s', item_path)
    try:
        with closing(dbus_init()) as connection:
            time.sleep(0.2)  # sometimes needed for items to be populated after unlock
            item = Item(connection, item_path)
            return item.get_secret()
    except SecretServiceNotAvailableException:
        log_secret.error('The dbus secretservice provider is not running any more')
        return None


def test():
    "run a test search"
    terms = get_terms(['Path'])
    for match in search(terms, 'martin'):
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
