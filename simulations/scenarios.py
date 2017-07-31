import sys
import logging
from collections import defaultdict

import pandas as pd

from attr import asdict
from msgpack import packb

from .agent import Agent, AgentSettings
from .utils import *


logger = logging.getLogger(__name__)


class GlobalState(object):
    """
    Current state of simulation at a point in time
    """
    def __init__(self, context):
        self.context = context
        self.agents = {}
        self.sent_email_count = 0
        self.encrypted_email_count = 0
        for user in self.context.senders:
            self.agents[user] = Agent(user)
        self.recipients_by_sender = defaultdict(set)


class SimulationReports(object):
    def __init__(self, context):
        self.key_propagation_data = \
                pd.DataFrame(columns=('Updated', 'Stale'))
        self.head_propagation_data = \
                pd.DataFrame(columns=('Updated', 'Stale'))

        self.encryption_status_data = pd.Series()
        self.link_status_data = pd.DataFrame(
                columns=[opt.name for opt in list(LinkStatus)])

        self.cache_size_data = \
                {sender: pd.Series() for sender in context.senders}
        self.local_store_size_data = \
                {sender: pd.Series() for sender in context.senders}
        self.bandwidth_data = \
                {sender: pd.Series() for sender in context.senders}


def get_encryption_status(global_state, sender_email, recipient_emails,
                          mode='global'):
    """
    Determine encryption status

    :param global_state: ``GlobalState`` object
    :param sender_email: Sender's email
    :param recipient_emails: Iterable of recipient emails
    :param mode: One of ['userset_only', 'userset_to_global', 'global'].
                 * `userset_only`: Only emails from userset senders to
                    userset receivers are considered
                 * `userset_to_global`: Only emails from userset senders are
                    considered.
                 * `global`: All emails are considered.
    """
    if mode not in ['userset_only', 'userset_to_global', 'global']:
        raise ValueError('Incorrect mode')

    if mode in ['userset_only', 'userset_to_global']:
        if sender_email not in global_state.context.userset:
            return None

    if mode == 'userset':
        userset_recipient_emails = recipient_emails.intersection(
                global_state.context.userset)
        if userset_recipient_emails != recipient_emails:
            return None

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


def get_link_status(global_state, sender_email, recipient_emails):
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


def simulate_claimchain(context):
    logger.info('Simulating ClaimChain')
    logger.info('Common agent settings: %s', AgentSettings.get_default())

    global_state = GlobalState(context)
    reports = SimulationReports(context)

    for index, email in enumerate(context.log):
        recipient_emails = (email.To | email.Cc | email.Bcc) - {email.From}
        if len(recipient_emails) == 0:
            continue

        sender = global_state.agents[email.From]

        # Send the email
        message_metadata = sender.send_message(recipient_emails)

        # Check if the email is plaintext, encrypted, or stale
        enc_status = get_encryption_status(
                global_state, email.From, recipient_emails)
        link_status, _ = get_link_status(
                global_state, email.From, recipient_emails)
        reports.encryption_status_data.loc[index] = enc_status
        reports.link_status_data.loc[index] = link_status

        # Record bandwidth and cache size
        if email.From in context.userset:
            packed_message_metadata = packb([
                    message_metadata.head,
                    list(message_metadata.public_contacts),
                    serialize_store(message_metadata.store)])
            reports.bandwidth_data[email.From].loc[index] = \
                   len(packed_message_metadata)

            packed_sender_cache = packb(serialize_caches(
                    sender.sent_object_keys_to_recipients))
            reports.cache_size_data[email.From].loc[index] = \
                   len(packed_sender_cache)

        # Update states of recipients
        for recipient_email in recipient_emails.intersection(context.senders):
            recipient = global_state.agents[recipient_email]
            recipient.receive_message(email.From, message_metadata,
                    recipient_emails - {recipient_email})

            # Record receiver store size
            packed_recipient_stores = \
                    packb([serialize_store(recipient.global_store),
                           serialize_store(recipient.chain_store),
                           serialize_store(recipient.tree_store)])
            reports.local_store_size_data[recipient_email].loc[index] = \
                    len(packed_recipient_stores)

        global_state.recipients_by_sender[email.From] |= recipient_emails

        if index % 1000 == 0:
            logging.debug('Email #%d', index)

    logging.info('Emails: Sent: %d, Encrypted: %d',
            global_state.sent_email_count,
            global_state.encrypted_email_count)

    return reports
