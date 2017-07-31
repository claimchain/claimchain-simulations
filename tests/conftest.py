import pytest
import pickle

from scripts.parse_enron import Message
from simulations.utils import Context

import __main__
__main__.Message = Message


parsed_logs_folder = 'Enron/parsing/'
log_entries_lim = 1000


@pytest.fixture
def log():
    with open(parsed_logs_folder + "replay_log.pkl", "rb") as f:
        yield pickle.load(f)[:log_entries_lim]


@pytest.fixture
def social_graph():
    with open(parsed_logs_folder + "social.pkl", "rb") as f:
        yield pickle.load(f)


@pytest.fixture
def context(log, social_graph):
    return Context(log, social_graph)

