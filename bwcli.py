#!/usr/bin/python3

import logging
from subprocess import run, PIPE
import json
import difflib  # for comparing strings
from typing import Iterable, NamedTuple, Optional, List, Callable, Tuple, Any, Dict, Set, cast


log = logging.getLogger('bwcli')


class Entry:
    """Each entry of a search result"""
    def __init__(self, username:str, password:str, name:str, attributes:Set[str]):
        self.username = username
        self.password = password
        self.name = name
        self.attributes = attributes
        self.prio: float = 0
        self.subtext = ''


class Bwcli:
    """Connection to bitwarden client
    """
    def __init__(self):
        self.__session: 'Optional[str]' = None
        self.cached_names = {}

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
            self.cache_ids()
            log.info('Logged in to bwcli (session key %s...)', self.__session[:5])
        elif proc.returncode == 127:
            log.error('Bitwarden cli not found')
        else:
            log.warning('%s %d', proc.stderr, proc.returncode)
            self.__session = None

    def __call(self, *args: str) -> Optional[Any]:
        """Call bw and return"""
        if not self.__session:
            log.warning('Has no session key, skip searching')
            return None
        cmd = ['bw', '--response', '--nointeraction', '--session', self.__session] + list(args)
        proc = run(cmd, stdout=PIPE, stderr=PIPE)
        if proc.returncode == 0:
            return json.loads(proc.stdout)
        log.error("%s %d", proc.stderr, proc.returncode)
        self.__session = None
        return None

    def cache_ids(self):
        """Cache some id's names; collections and organisations"""
        for collection in self.__call('list', 'collections'):
            self.cached_names[collection['id']] = collection['name']
        for organization in self.__call('list', 'organizations'):
            self.cached_names[organization['id']] = organization['name']

    def sync(self) -> bool:
        """Call bwcli sync and check result
            {'success': True, 'data': {'noColor': False, 'object': 'message', 'title': 'Syncing complete.', 'message': None}}
        """
        if self.has_session():
            log.info('sync')
            response = self.__call('sync')
            if response and response.get('success', False) == True:
                return True
        return False

    def lock(self, _arg=None) -> None:
        """Call bwcli logout and clear session"""
        if self.has_session():
            log.info('lock session')
            self.__session = None
            self.__call('lock')

    def has_session(self) -> bool:
        return bool(self.__session)

    def search(self, search_term: str) -> 'Iterable[Entry]':
        """Search for terms, return a list of matches"""
        response = self.__call("list", "items", "--search", search_term)
        if response:
            try:
                data = cast(List[Dict[str, Any]], response["data"]["data"])
            except KeyError:
                log.error('response is missing [data][data]', response)
                return []
            else:
                return sort_entries(search_term, self.__parse_search(data))
        else:
            return []

    def __parse_search(self, items:List[Dict[str, Any]]) -> 'Iterable[Entry]':
        """
        {'object': 'item', 'id': 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx', 'organizationId': None,
         'folderId': 'yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy', 'type': 1, 'reprompt': 0,
         'name': 'git:https://github.com', 'notes': None, 'favorite': False,
         'fields': [
                {'name': 'FDO_SECRETS_CONTENT_TYPE', 'value': 'plain/text', 'type': 0},
                {'name': 'account', 'value': 'martininsulander', 'type': 0},
                {'name': 'service', 'value': 'git:https://github.com', 'type': 0},
                {'name': 'xdg:schema', 'value': 'com.microsoft.GitCredentialManager', 'type': 0}],
         'login': {
             'uris': [{'match': None, 'uri': 'https://github.com/login'}],  # optional
             'username': 'my@email', 'password': 'my_password', 'totp': None,
             'passwordRevisionDate': None}                
         'collectionIds': [], 'revisionDate': '2021-09-26T10:26:54.736Z'}
        """
        for item in items:
            if not "login" in item:
                continue
            login = item["login"]
            username = login["username"] if "username" in login else ""
            password = login["password"] if "password" in login else ""
            if not username and not password:
                continue
            name = item["name"]
            attributes: Set[str] = set()
            attributes.add(item["name"])
            if 'uris' in login:
                for uri in login["uris"]:
                    attributes.add(uri["uri"])
            for colid in item['collectionIds']:
                if colid in self.cached_names:
                    colname = self.cached_names[colid]
                    attributes.add(colname)
                    name += ' ' + colname
            if item['organizationId'] and item['organizationId'] in self.cached_names:
                attributes.add(self.cached_names[item['organizationId']])

            yield Entry(
                name = name,
                username=username,
                password=password,
                attributes=attributes)


def priority_term(diff: Any, search_term: str, term: str) -> float:
    """Find out ratio/priority of a term"""
    return max(
        diff.set_seq2(term) or 0,
        0.8 if term.startswith(search_term) else 0,
    )


def priority_entry(diff: Any, search_term: str, entry: Entry, strfix: Callable[[str], str]) -> None:
    """Find out ratio/priority of an entry"""
    r_a: List[Tuple[float, str]] = []
    for attribute in entry.attributes:
        r_a.append((priority_term(diff, search_term, strfix(attribute)), attribute,))
    r_a = sorted(r_a, key=lambda r_a: r_a[0], reverse=True)
    entry.prio = r_a[0][0]
    entry.subtext = ' '.join([r_a[1] for r_a in r_a[:3]])


def sort_entries(search_term: str, entries: 'Iterable[Entry]') -> List[Entry]:
    """Sort entries based on priority"""
    selected_entries: 'List[Entry]' = []
    diff: Any = difflib.SequenceMatcher(a=search_term, autojunk=False)
    if search_term.islower():
        strfix = lambda s: s.lower()
        log.info('sort term case insensitive %s', search_term)
    else:
        strfix = lambda s: s
        log.info('sort term %s', search_term)

    count = 0
    for count, entry in enumerate(entries, start=1):
        priority_entry(diff, search_term, entry, strfix)
        if entry.prio > 0.4:
            selected_entries.append(entry)
    log.debug('Accepted %d of %d entries', len(selected_entries), count)
    return sorted(selected_entries, key=lambda e: e.prio, reverse=True)



if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG)
    bw = Bwcli()
    matches = bw.search(sys.argv[1])
    if matches:
        for item in matches:
            print(item)
