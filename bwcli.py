#!/usr/bin/python3

import logging
from subprocess import run, PIPE
import json
import difflib  # for comparing strings
from typing import Iterable, NamedTuple, Optional, List, Callable, Tuple, Any
import time

log = logging.getLogger('bwcli')


class Entry(NamedTuple):
    """Each entry of a search result"""
    name: str
    subtext: str
    username: str
    password: str



class Bwcli:
    """Connection to bitwarden client
    """
    def __init__(self):
        self.__session: 'Optional[bytes]' = None

    def login(self):
        "Get session cookie"
        command = 'bw unlock --raw "$(kdialog --password "Unlock your bitwarden")"'
        log.debug('Login to bwcli (%s)', command)
        proc = run(
            args=command,
            shell=True,
            stdout=PIPE,
            stderr=PIPE)
        if proc.returncode == 0:
            self.__session = proc.stdout
            log.info('Logged in to bwcli (session key %s...)', self.__session[:5])
        elif proc.returncode == 127:
            log.error('Bitwarden cli not found')
        else:
            log.warning('%s %d', proc.stderr, proc.returncode)
            self.__session = None

    def sync(self) -> None:
        pass

    def has_session(self) -> bool:
        return bool(self.__session)

    def search(self, search_term: str) -> 'Iterable[Tuple[float, Entry]]':
        """Search for terms, return a list of matches"""
        session = self.__session
        if not session:
            log.warning('Has no session key, skip searching')
            return
        log.debug('getting entries from bwcli')
        proc = run(
            ["bw", "list", "items", "--search", search_term,
             "--response", "--nointeraction", "--session", session],
            stdout=PIPE,
            stderr=PIPE)
        if proc.returncode == 0:
            entries = sort_entries(search_term, self.__parse_search(proc.stdout))
            yield from entries
        else:
            log.error(proc.stderr, proc.returncode)
            self.__session = None

    def __parse_search(self, result_json:bytes) -> 'Iterable[Entry]':
        for item in json.loads(result_json)["data"]["data"]:
            # log.debug(item)
            if not "login" in item:
                continue
            login = item["login"]
            username = login["username"] if "username" in login else ""
            password = login["password"] if "password" in login else ""
            subtext = ''
            # TODO fix better subtext by url or other attributes
            # attrvals = ', '.join(['%s:%s' % (attr, val) for attr, val in attvals])
            # text = label + ' ' + attrvals
            if not username and not password:
                continue
            yield Entry(
                name=item["name"],
                username=username,
                password=password,
                subtext=subtext)



def priority_term(diff: Any, search_term: str, term: str) -> float:
    """Find out ratio/priority of a term"""
    return max(
        diff.set_seq2(term) or 0,
        0.8 if term.startswith(search_term) else 0,
    )


def priority_entry(diff: Any, search_term: str, entry: Entry, strfix: Callable[[str], str]) -> float:
    """Find out ratio/priority of an entry"""
    return max(
        priority_term(diff, search_term, strfix(entry.username)),
        priority_term(diff, search_term, strfix(entry.name)),
        priority_term(diff, search_term, strfix(entry.password)),
    )


def sort_entries(search_term: str, entries: 'Iterable[Entry]') -> List[Tuple[float, Entry]]:
    """Sort entries based on priority"""
    ratio_entry: 'List[Tuple[float, Entry]]' = []
    diff: Any = difflib.SequenceMatcher(a=search_term, autojunk=False)
    if search_term.islower():
        strfix = lambda s: s.lower()
        log.info('sort term case insensitive %s', search_term)
    else:
        strfix = lambda s: s
        log.info('sort term %s', search_term)

    count = 0
    for count, entry in enumerate(entries, start=1):
        prio = priority_entry(diff, search_term, entry, strfix)
        if prio > 0.4:
            ratio_entry.append((prio, entry,))
    log.debug('Accepted %d of %d entries', len(ratio_entry), count)
    return [r_e for r_e in sorted(ratio_entry, key=lambda r_e: r_e[0], reverse=True)]



if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG)
    bw = Bwcli()
    matches = bw.search(sys.argv[1])
    if matches:
        for item in matches:
            print(item)
