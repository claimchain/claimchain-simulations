"""
Misc. utility functions and classes for simulations
"""

from enum import Enum

from attr import attrs, attrib

from defaultcontext import with_default_context
from claimchain.utils.wrappers import serialize_object


class EncStatus(Enum):
    plaintext = 0
    stale = 1
    encrypted = 2


class LinkStatus(Enum):
    greeting = 0   # Initial greeting
    followup = 1   # Greeting sent, but response not received or learned
    completed = 2


def serialize_store(store):
    keys = list(store.keys())
    values = [serialize_object(obj) for obj in store.values()]
    return (keys, values)


def serialize_caches(caches):
    return list(caches)


class Context(object):
    def __init__(self, log, social_graph):
        self.log = log
        self.social_graph = social_graph

        # Set of the dataset users we know the full social graph for
        self.userset = set(self.social_graph.keys())

        # Set of all users that eventually send an email
        self.senders = {email.From for email in self.log}

        self.global_social_graph = {}
        for email in log:
            if email.From not in self.global_social_graph:
                self.global_social_graph[email.From] = {'friends': set()}

            recipients = email.To | email.Cc | email.Bcc - {email.From}
            for recipient in recipients:
                self.global_social_graph[email.From]['friends'].add(recipient)

