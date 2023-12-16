#!/usr/bin/python3

import difflib
import logging
import sys
from subprocess import run
import json
from typing import (
    Iterable,
    Optional,
    List,
    Callable,
    Tuple,
    Any,
    Dict,
    Set,
)

log = logging.getLogger("rbwcli")


class Entry:
    """Each entry of a search result"""

    def __init__(self, username: str, password: str, name: str, attributes: Set[str]):
        self.username = username
        self.password = password
        self.name = name
        self.attributes = attributes
        self.prio: float = 0
        self.subtext = ""


class Rbwcli:
    """Connection to bitwarden client"""

    def __init__(self):
        self.cached_names = {}
        self.__session: "Optional[bool]" = None

    def login(self):
        "Get session cookie"
        command = "rbw unlock"
        proc = run(args=command, shell=False, capture_output=True)
        if proc.returncode == 0:
            self.__session = True
            # self.cache_ids()
            log.info("Logged in to rbwcli")
        elif proc.returncode == 127:
            log.error("rbw not found")
        else:
            log.warning("%s %d", proc.stderr, proc.returncode)

    def __call(self, *args: str) -> Optional[Any]:
        """Call rbw and return"""
        cmd = ["rbw"] + list(args)
        proc = run(cmd, shell=False, capture_output=True)
        if proc.returncode == 0 and proc.stdout:
            return (proc.returncode, json.loads(proc.stdout))
        log.error("%s %d", proc.stderr, proc.returncode)
        return (proc.returncode, proc.stderr)

    def cache_ids(self):
        """Cache some id's names; collections and organisations"""
        for collection in self.__call("list"):
            self.cached_names[list["id"]] = list["name"]

    def sync(self) -> bool:
        """Call rbwcli sync and check result
        {'success': True, 'data': {'noColor': False, 'object': 'message', 'title': 'Syncing complete.', 'message': None}}
        """
        if self.has_session():
            log.info("sync")
            response = self.__call("sync")
            if response[0] == 0:
                return True
        return False

    def lock(self, _arg=None) -> None:
        """Call bwcli logout and clear session"""
        log.info("lock session")
        self.__call("lock")

    def has_session(self) -> bool:
        result = self.__call("unlocked")
        if result[0] == 0:
            return True
        return False

    def search(self, search_term: str) -> "Iterable[Entry]":
        """Search for terms, return a list of matches"""
        response = self.__call("search", "--raw", "--full", search_term)
        if response[0] == 0:
            return sort_entries(search_term, self.__parse_search(response[1]))
        else:
            return []

    def __parse_search(self, items: List[Dict[str, Any]]) -> "Iterable[Entry]":
        """
        [
            {"id":"64266d6b-bada-469c-a98e-4ae7d41ff121",
            "folder":null,
            "name":"My credit card",
            "data":{
                "cardholder_name":"First Last",
                "number":"9999820023689999",
                "brand":"Mastercard",
                "exp_month":"1",
                "exp_year":"2020",
                "code":"999"
                },
            "fields":[],
            "notes":null,
            "history":[]
            },
            {"id":"70c71c46-36d2-4dc5-8017-1126660ece62",
            "folder":"Business",
            "name":"kde.org",
            "data":{
                "username":"my_email@gmail.com",
                "password":"super_secret",
                "totp":null,
                "uris":[{"uri":"https://www.kde.org",
                "match_type":null}]
            },
            "fields":[],
            "notes":"some notes",
            "history":[{
                "last_used_date":"2020-10-07T16:02:05.434Z",
                "password":"oldpass"
            }]}
        ]
        """
        for item in items:
            try:
                if not "username" in item.get("data"):
                    continue
            except:
                continue
            login_data = item.get("data")
            username = login_data.get("username", "")
            password = login_data.get("password", "")
            if not username and not password:
                continue
            name = item["name"]
            attributes: Set[str] = set()
            attributes.add(item["name"])
            if "uris" in login_data:
                for uri in login_data["uris"]:
                    if uri["uri"]:
                        attributes.add(uri["uri"])
            if item.get("org_id") and item["org_id"] in self.cached_names:
                attributes.add(self.cached_names[item["org_id"]])

            yield Entry(
                name=name, username=username, password=password, attributes=attributes
            )


def priority_term(diff: Any, search_term: str, term: str) -> float:
    """Find out ratio/priority of a term"""
    return max(
        diff.set_seq2(term) or 0,
        0.8 if term.startswith(search_term) else 0,
    )


def priority_entry(
    diff: Any, search_term: str, entry: Entry, strfix: Callable[[str], str]
) -> None:
    """Find out ratio/priority of an entry"""
    r_a: List[Tuple[float, str]] = []
    for attribute in entry.attributes:
        r_a.append(
            (
                priority_term(diff, search_term, strfix(attribute)),
                attribute,
            )
        )
    r_a = sorted(r_a, key=lambda r_a: r_a[0], reverse=True)
    entry.prio = r_a[0][0]
    entry.subtext = " ".join([r_a[1] for r_a in r_a[:3]])


def sort_entries(search_term: str, entries: "Iterable[Entry]") -> List[Entry]:
    """Sort entries based on priority"""
    selected_entries: "List[Entry]" = []
    diff: Any = difflib.SequenceMatcher(a=search_term, autojunk=False)
    if search_term.islower():
        strfix = lambda s: s.lower()
        log.info("sort term case insensitive %s", search_term)
    else:
        strfix = lambda s: s
        log.info("sort term %s", search_term)

    count = 0
    for count, entry in enumerate(entries, start=1):
        priority_entry(diff, search_term, entry, strfix)
        if entry.prio > 0.4:
            selected_entries.append(entry)
    log.debug("Accepted %d of %d entries", len(selected_entries), count)
    return sorted(selected_entries, key=lambda e: e.prio, reverse=True)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG)
    bw = Rbwcli()
    matches = bw.search(sys.argv[1])
    if matches:
        for item in matches:
            print(item)
