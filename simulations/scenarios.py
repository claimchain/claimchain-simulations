"""
Simulations of ClaimChain key distribution.
"""

import sys
import logging
from collections import defaultdict
from enum import Enum

import pandas as pd

from attr import asdict
from msgpack import packb
from tqdm import tqdm

from .agent import Agent, AgentSettings
from .utils import *


logger = logging.getLogger(__name__)


class GlobalState(object):
    """Current state of a simulation at a point in time."""
    def __init__(self, context):
        self.context = context
        self.agents = {}
        self.sent_email_count = 0
        self.encrypted_email_count = 0
        for user in self.context.senders:
            self.agents[user] = Agent(user)
        self.recipients_by_sender = defaultdict(set)


class SimulationReports(object):
    """Simulation results."""
    def __init__(self, context):
        self.encryption_status_data = pd.Series()
        self.participants_type_data = pd.Series()
        self.link_status_data = pd.DataFrame(
                columns=[opt.name for opt in list(LinkStatus)])

        self.cache_size_data = defaultdict(pd.Series)
        self.local_store_size_data = defaultdict(pd.Series)
        self.gossip_store_size_data = defaultdict(pd.Series)
        self.outgoing_bandwidth_data = defaultdict(pd.Series)
        self.incoming_bandwidth_data = defaultdict(pd.Series)
        self.social_evidence_diversity_data = defaultdict(pd.Series)
        self.unique_evidence_data = defaultdict(pd.Series)


class ParticipantsTypes(Enum):
    """Type of participants in an email."""
    userset = 0             # Within Enron.
    userset_to_global = 1   # Enron to outside-of-Enron.
    other = 2               # Anything else.


def get_encryption_status(global_state, sender_email, recipient_emails):
    """Determine encryption status of an email.

    :param global_state: ``GlobalState`` object
    :param sender_email: Sender's email
    :param recipient_emails: Iterable of recipient emails
    """
    if not recipient_emails:
        return None

    global_state.sent_email_count += 1

    stale = False
    sender = global_state.agents[sender_email]
    for recipient_email in recipient_emails:
        view = sender.committed_views.get(recipient_email)

        # If sender does not know of a recipient's enc key, the email is
        # sent in clear text
        if view is None:
            return EncStatus.plaintext

        view_enc_key = view.payload.metadata.identity_info
        true_enc_key = global_state.agents[recipient_email].state.identity_info

        if view_enc_key is None:
            return EncStatus.plaintext
        elif recipient_email in global_state.context.senders and \
            view_enc_key != true_enc_key:
            stale = True

    if not stale:
        global_state.encrypted_email_count += 1
        return EncStatus.encrypted
    else:
        return EncStatus.stale


def get_participants_type(global_state, sender_email, recipient_emails):
    """Determine the type of participants in an email."""
    userset_recipient_emails = recipient_emails.intersection(
            global_state.context.userset)
    recipients_in_userset = userset_recipient_emails == recipient_emails
    sender_in_userset = sender_email in global_state.context.userset
    if not sender_in_userset:
        return ParticipantsTypes.other
    elif recipients_in_userset:
        return ParticipantsTypes.userset
    else:
        return ParticipantsTypes.userset_to_global


def get_link_status(global_state, sender_email, recipient_emails):
    """Deprecated."""
    link_statuses = {}
    link_status_summary = {opt.name: 0 for opt in list(LinkStatus)}

    sender = global_state.agents[sender_email]
    past_recipients = global_state.recipients_by_sender[sender_email]

    for recipient_email in recipient_emails:
        recipient_view = sender.get_latest_view(recipient_email, save=False)

        if recipient_view is None and recipient_email not in past_recipients:
            link_statuses[recipient_email] = LinkStatus.greeting
            link_status_summary[LinkStatus.greeting.name] += 1

        elif recipient_view is None and recipient_email in past_recipients:
            link_statuses[recipient_email] = LinkStatus.followup
            link_status_summary[LinkStatus.followup.name] += 1

        elif recipient_view is not None:
            link_statuses[recipient_email] = LinkStatus.completed
            link_status_summary[LinkStatus.completed.name] += 1

    return link_status_summary, link_statuses


def do_simulation_step(index, email, global_state, reports):
    """Simulate single email."""

    recipient_emails = (email.To | email.Cc | email.Bcc) - {email.From}
    if len(recipient_emails) == 0:
        return global_state, reports

    sender = global_state.agents[email.From]

    # Send the email
    message_metadata = sender.send_message(recipient_emails, email.mtime)

    # Check if the email is plaintext, encrypted, or stale
    enc_status = get_encryption_status(
            global_state, email.From, recipient_emails)
    link_status, _ = get_link_status(
            global_state, email.From, recipient_emails)
    participants_type = get_participants_type(
            global_state, email.From, recipient_emails)
    reports.encryption_status_data.loc[index] = enc_status
    reports.link_status_data.loc[index] = link_status
    reports.participants_type_data.loc[index] = participants_type

    # Record bandwidth and cache size
    packed_message_metadata = packb([
            message_metadata.head,
            list(message_metadata.public_contacts),
            serialize_store(message_metadata.store)])
    reports.outgoing_bandwidth_data[email.From].loc[index] = \
           len(packed_message_metadata)
    packed_sender_cache = packb(serialize_caches(
            sender.sent_object_keys_to_recipients))
    reports.cache_size_data[email.From].loc[index] = \
           len(packed_sender_cache)


    # Record social evidence diversity
    relevant_recipients = recipient_emails.intersection(
            global_state.context.senders)
    unique_evidence_sizes = []
    diversity_values = []

    for recipient_email in relevant_recipients:
        own_views, views_by_friend = sender.get_social_evidence(
                recipient_email)
        evidence = list(own_views) + list(views_by_friend.values())
        diversity_values.append(len(evidence))
        unique_evidence_sizes.append(len(set(evidence)))

    reports.social_evidence_diversity_data[email.From].loc[index] = \
        diversity_values
    reports.unique_evidence_data[email.From].loc[index] = \
        unique_evidence_sizes

    # Update states of recipients
    for recipient_email in relevant_recipients:
        recipient = global_state.agents[recipient_email]
        recipient.receive_message(email.From, message_metadata,
                recipient_emails - {recipient_email})

        # Record receiver store sizes
        packed_recipient_local_store = \
                packb([serialize_store(recipient.chain_store),
                       serialize_store(recipient.tree_store)])
        reports.local_store_size_data[recipient_email].loc[index] = \
                len(packed_recipient_local_store)

        packed_recipient_gossip_store = \
                packb(serialize_store(recipient.gossip_store))
        reports.gossip_store_size_data[recipient_email].loc[index] = \
                len(packed_recipient_gossip_store)

        # Record incoming bandwidth
        reports.incoming_bandwidth_data[recipient_email].loc[index] = \
                len(packed_message_metadata)

    global_state.recipients_by_sender[email.From] |= recipient_emails
    return global_state, reports


def init_simulations(context):
    """Initialize simulation state and reports."""
    global_state = GlobalState(context)
    reports = SimulationReports(context)
    return global_state, reports


def simulate_claimchain(context, pbar=None):
    """Run simulations."""
    logger.info('Simulating ClaimChain')
    logger.info('Common agent settings: %s', AgentSettings.get_default())

    state, reports = init_simulations(context)

    if pbar is None:
        pbar = tqdm

    for index, email in pbar(list(enumerate(context.log))):
        global_state, reports = do_simulation_step(
                index, email, state, reports)

    logging.info('Emails: Sent: %d, Encrypted: %d',
            global_state.sent_email_count,
            global_state.encrypted_email_count)

    return reports
