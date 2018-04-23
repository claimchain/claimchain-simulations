"""
Simulated MUA that uses ClaimChain.
"""

import os
import six
import base64
import msgpack
import warnings
import itertools
import logging

from collections import defaultdict
from datetime import datetime

from attr import attrs, attrib
from hippiehug import Chain, Block
from claimchain import State, View, LocalParams
from claimchain.utils import ObjectStore, serialize_object
from defaultcontext import with_default_context


logger = logging.getLogger(__name__)


# For public claims, we assume there exist public DH key pair
# accessible by anybody---for simplicity.
PUBLIC_READER_PARAMS = LocalParams.generate()

PUBLIC_READER_LABEL = 'public'


def serialize_block(block):
    """Encode a block into bytes using msgpack."""
    as_tuple = block.index, block.fingers, block.items, block.aux
    return msgpack.packb(as_tuple,
            use_bin_type=True, encoding="utf-8")


def deserialize_block(serialized_block):
    """Decode a block from msgpack-serialized bytes."""
    as_tuple = msgpack.unpackb(serialized_block, encoding="utf-8")
    index, fingers, items, aux = as_tuple
    return Block(items, index, fingers, aux)


def latest_timestamp_resolution_policy(agent, views):
    """Naive resolution policy that does not check for forks."""
    return max(views, key=lambda view: view.payload.timestamp)


def immediate_chain_update_policy(agent, recipients):
    """Update chain whenever anything relevant to an email is updated.

    Check if any of the contacts or capability entries that are relevant
    to the current message have been updated. If yes, commit a new block with
    the updates before sending the message.
    """

    # * Update chain if any public cap needs to be updated
    if agent.queued_caps.get(PUBLIC_READER_LABEL):
        return True

    public_contacts = agent.committed_caps.get(PUBLIC_READER_LABEL) or set()

    # * Update chain if any relevant private cap needs to be updated
    for recipient in recipients:
        if agent.queued_caps.get(recipient):
            return True

    private_contacts = set()
    for recipient in recipients:
        recipient_caps = agent.committed_caps.get(recipient) or set()
        private_contacts.update(recipient_caps)

    # * Update chain if any contact that is to be shared in this
    # message was updated.
    relevant_contacts = private_contacts | public_contacts
    if len(relevant_contacts.intersection(agent.queued_views)) > 0:
        return True


def implicit_cc_introduction_policy(agent, recipient_emails):
    """Access control policy that gives capabilities to all recipients."""
    for recipient_email in recipient_emails - {agent.email}:
        # NOTE: Friends should be able to see what my belief about them is,
        # so no need to exclude recipient_email from recipient_emails here.
        agent.add_expected_reader(recipient_email, recipient_emails)


def public_contacts_policy(agent, recipient_emails):
    """Access control policy that makes all claims public."""
    new_public_contacts = set() \
                        | agent.committed_views.keys() \
                        | agent.queued_views.keys()    \
                        | agent.expected_views.keys()
    for contact in new_public_contacts:
        agent.queued_views[contact] = agent.get_latest_view(contact)
    agent.queued_caps[PUBLIC_READER_LABEL] |= new_public_contacts


@attrs
class MessageMetadata(object):
    """Simulated embedded data packet."""
    head = attrib()
    public_contacts = attrib()
    store = attrib()


@with_default_context(use_empty_init=True)
@attrs
class AgentSettings(object):
    conflict_resolution_policy = attrib(
            default=latest_timestamp_resolution_policy)
    chain_update_policy = attrib(default=immediate_chain_update_policy)
    introduction_policy = attrib(default=implicit_cc_introduction_policy)
    key_update_every_nb_sent_emails = attrib(default=None)
    key_update_every_nb_days = attrib(default=None)
    optimize_sent_objects = attrib(default=True)


class Agent(object):
    """
    Simulated ClaimChain user.
    """
    def __init__(self, email):
        self.email = email
        self.params = LocalParams.generate()
        self.chain_store = ObjectStore()
        self.tree_store = ObjectStore()
        self.chain = Chain(self.chain_store)
        self.state = State()

        # Stats
        self.nb_sent_emails = 0
        self.date_of_last_key_update = None

        # Committed views and capabilities
        self.committed_caps = {}
        self.committed_views = {}
        # ...and the ones queued to be committed.
        self.queued_identity_info = None
        self.queued_caps = defaultdict(set)
        self.queued_views = {}
        # Capabilities for unknown yet contacts
        # and views that have no readers.
        self.expected_caps = defaultdict(set)
        self.expected_views = defaultdict(set)

        # Known beliefs of other people about other people.
        self.global_views = defaultdict(dict)
        # Contacts that senders have made available to this agent.
        self.contacts_by_sender = defaultdict(set)

        # Objects that were sent to each recipient.
        self.sent_object_keys_to_recipients = {}
        # Objects that were received from other people.
        self.gossip_store = ObjectStore()

        # Generate initial encryption key, and add first block
        # to the chain
        self.update_key()

    @property
    def head(self):
        """Chain head."""
        return self.chain.head

    @property
    def current_enc_key(self):
        """
        Current encryption key.
        """
        return self.state.identity_info

    @staticmethod
    def generate_public_key():
        """
        Generate (fake) public encryption key.
        """
        # 4096 random bits in base64
        return base64.b64encode(os.urandom(4096 // 8))

    def add_expected_reader(self, reader, contacts):
        """
        Make contacts accessible to the reader.

        No need to know the reader's DH key, and contact
        views at this point. As soon as these will be learned,
        expected capabilities will be moved to the queue.
        """
        if isinstance(contacts, six.string_types):
            # Quick check to prevent a silly bug.
            warnings.warn("Contacts is a string type, an iterable of "
                          "identifiers is expected.")

        if not contacts:
            return

        logger.debug('%s / expected cap / %s: %s', self.email,
                    reader, contacts)
        self.expected_caps[reader].update(contacts)

    def _update_buffer(self):
        """Update claim 'expected' and 'queued' buffers.

        Traverses all claims in the 'expected' buffer, and checks if there
        has been collected enough information to actually make the claims.
        Those for which the information in the gossip store is sufficient,
        are moved to the 'queued' buffer.
        """

        accepted_caps_by_reader = defaultdict(set)

        for reader, contacts in self.expected_caps.items():
            reader_view = self.get_latest_view(reader)
            if reader_view is None and reader != PUBLIC_READER_LABEL:
                continue

            for contact in contacts:
                contact_view = self.get_latest_view(contact)
                if contact_view is not None:
                    # Copy expected cap into queue.
                    self.queued_caps[reader].add(contact)

                    # Move the expected view into queue if needed.
                    if contact in self.expected_views:
                        self.queued_views[contact] = contact_view
                        del self.expected_views[contact]

                    accepted_caps_by_reader[reader].add(contact)

            # Move the reader view into queue if needed.
            if accepted_caps_by_reader[reader]:
                if reader in self.expected_views:
                    self.queued_views[reader] = reader_view
                    del self.expected_views[reader]

        # Clean empty expected_caps entries.
        for reader, contacts in accepted_caps_by_reader.items():
            self.expected_caps[reader] -= contacts
            if not self.expected_caps[reader]:
                del self.expected_caps[reader]

    def get_social_evidence(self, contact):
        """Gather social evidence about the contact."""

        # Collect possible candidates
        own_views = set()
        # ...starting with existing views of the contact.
        if contact in self.committed_views:
            own_views.add(self.committed_views[contact])
        if contact in self.queued_views:
            own_views.add(self.queued_views[contact])
        if contact in self.expected_views:
            own_views.add(self.expected_views[contact])

        # Get a view of the contact in question from every friend.
        current_friends = set(self.committed_views.keys()) \
                        | set(self.queued_views.keys())    \
                        | set(self.expected_views.keys())
        views_by_friend = {}
        for friend in current_friends - {contact, self.email}:
            candidate_view = self.global_views[friend].get(contact)
            if candidate_view is not None:
                views_by_friend[friend] = candidate_view

        return own_views, views_by_friend

    def get_latest_view(self, contact, save=True):
        """Resolve latest view for contact through a social policy.

        Gathers candidate views for contact across local state, and runs
        a social validation policy to decide on the best candidate.

        As a side effect, puts the resolved view in the 'expected' buffer.

        :param contact: Contact identifier
        :param bool save: Whether to save the resolved view to the queue
        """
        own_views, views_by_friend = self.get_social_evidence(contact)
        policy = AgentSettings.get_default().conflict_resolution_policy
        candidate_views = own_views | set(views_by_friend.values())

        if len(candidate_views) == 0:
            return None

        # Resolve conflicts using a policy
        view = policy(self, candidate_views)
        # ...and add the resolved view to the 'expected' buffer.
        self.expected_views[contact] = view

        # Remove from the buffer if the resolved view is the same as committed.
        if save:
            committed_view = self.committed_views.get(contact)
            if view == committed_view:
                del self.expected_views[contact]

        return view

    def send_message(self, recipients, mtime=0):
        """Build an ClaimChain embedded data packet.

        NOTE: May update the chain if required by the update policy.

        :param recipients: An iterable of recipient identifiers (emails)
        :param mtime: Timestamp
        :returns: ``MessageMetadata`` object
        """
        logger.debug('%s -> %s', self.email, recipients)

        if len(recipients) == 0:
            return
        if isinstance(recipients, six.string_types):
            warnings.warn("Recipients is a string type, an iterable of "
                          "identifiers is expected.")
        if not isinstance(recipients, set):
            recipients = set(recipients)

        with self.params.as_default():
            intro_policy = AgentSettings.get_default().introduction_policy
            # Grant accesses according to the introduction policy.
            intro_policy(self, recipients)

            # Move expected views and caps into the queue.
            self._update_buffer()

            # Decide whether to update the encryption key.
            # TODO: Make key update decision a policy.
            nb_sent_emails_thresh = AgentSettings.get_default() \
                    .key_update_every_nb_sent_emails
            min_nb_days = AgentSettings.get_default() \
                    .key_update_every_nb_days

            nb_sent_based_update = nb_sent_emails_thresh is not None and \
                    self.nb_sent_emails >= nb_sent_emails_thresh

            time_based_update = False
            sending_date = datetime.fromtimestamp(mtime)
            if self.date_of_last_key_update is not None:
                days_since_last_update = (
                        sending_date - self.date_of_last_key_update).days
                if min_nb_days is not None:
                    time_based_update = days_since_last_update >= min_nb_days
                time_based_update = min_nb_days is not None and (
                        days_since_last_update >= min_nb_days)
            else:
                self.date_of_last_key_update = sending_date

            if nb_sent_based_update or time_based_update:
                self.update_key(mtime)
                self.nb_sent_emails = 0

            else:
                # Decide whether to update the chain.
                update_policy = AgentSettings.get_default().chain_update_policy
                if update_policy(self, recipients):
                    self.update_chain()

            local_object_keys = set()
            global_object_keys = set()

            # Add own chain blocks.
            # NOTE: Requires that chain and tree use separate stores
            local_object_keys.update(self.chain_store.keys())

            # Add authentication proofs for public claims.
            public_contacts = self.committed_caps.get(PUBLIC_READER_LABEL) \
                              or set()
            for contact in public_contacts:
                object_keys = self.state.compute_evidence_keys(
                        PUBLIC_READER_PARAMS.dh.pk, contact)
                local_object_keys.update(object_keys)
                contact_view = self.committed_views.get(contact)
                # if contact_view is not None:
                #     global_object_keys.add(contact_view.head)

            # Find a minimal amount of proof nodes that need to be included.
            for recipient in recipients:
                accessible_contacts = self.committed_caps.get(recipient) \
                                      or set()
                for contact in accessible_contacts:
                    recipient_view = self.committed_views.get(recipient)
                    if recipient_view is None:
                        continue
                    contact_view = self.committed_views.get(contact)
                    if contact_view is not None:
                        # Add the proof for the cross-reference.
                        recipient_dh_pk = recipient_view.params.dh.pk
                        proof_keys = self.state.compute_evidence_keys(
                                recipient_dh_pk, contact)
                        local_object_keys.update(proof_keys)

            # Find the minimal amount of objects that need to be sent in
            # this message.
            relevant_keys = local_object_keys | global_object_keys
            object_keys_to_send = set()
            for recipient in recipients:
                if recipient not in self.sent_object_keys_to_recipients:
                    if AgentSettings.get_default().optimize_sent_objects:
                        self.sent_object_keys_to_recipients[recipient] = \
                                relevant_keys
                    object_keys_to_send = relevant_keys
                else:
                    object_keys_for_recipient = relevant_keys.difference(
                            self.sent_object_keys_to_recipients[recipient])
                    object_keys_to_send |= object_keys_for_recipient

            # Collect the objects by keys.
            message_store = {}
            # * Local (own) objects...
            for key in local_object_keys.intersection(object_keys_to_send):
                value = self.chain_store.get(key) or self.tree_store.get(key)
                if value is not None:
                    message_store[key] = value

            # * Global objects...
            # for key in global_object_keys.intersection(object_keys_to_send):
            #     value = self.gossip_store.get(key)
            #     if value is not None:
            #         message_store[key] = value

            self.nb_sent_emails += 1
            return MessageMetadata(
                    self.chain.head, public_contacts, message_store)

    def get_accessible_contacts(self, sender, message_metadata,
                                other_recipients=None):
        """
        Get the contacts that are expected to be accessible on sender's chain.
        """
        # NOTE: Assumes other people's introduction policy is the same
        contacts = self.contacts_by_sender[sender]
        other_recipients = set(other_recipients) - {sender, self.email}
        for recipient in other_recipients | message_metadata.public_contacts:
            contacts.add(recipient)
        return contacts

    def receive_message(self, sender, message_metadata,
                        other_recipients=None):
        """Interpret an incoming data packet.

        :param sender: Sender identifier
        :param message_metadata: Additional data obtained by ``send_message``
        :param other_recipients: Identifiers of other known recipients of the
                                 message
        """
        logger.debug('%s <- %s', self.email, sender)
        if other_recipients is None:
            other_recipients = set()

        with self.params.as_default():
            # Merge stores temporarily.
            merged_store = ObjectStore(self.gossip_store)
            for key, obj in message_metadata.store.items():
                merged_store[key] = obj

            sender_head = message_metadata.head
            sender_latest_block = merged_store[sender_head]
            self.gossip_store[sender_head] = \
                    sender_latest_block
            self.expected_views[sender] = View(
                    Chain(self.gossip_store,
                          root_hash=sender_head))
            full_sender_view = View(
                    Chain(merged_store,
                          root_hash=sender_head))
            logger.debug('%s / expected view / %s', self.email, sender)

            # Add relevant objects from the message store.
            contacts = self.get_accessible_contacts(
                    sender, message_metadata, other_recipients)
            for contact in contacts - {self.email}:
                contact_latest_block = self.get_contact_head_from_view(
                        full_sender_view, contact)
                if contact_latest_block is not None:
                    contact_head_hash = contact_latest_block.hid
                    self.gossip_store[contact_head_hash] = contact_latest_block

                    # NOTE: Assumes people send only contacts' latest blocks
                    contact_chain = Chain(self.gossip_store,
                                          root_hash=contact_head_hash)
                    self.global_views[sender][contact] = View(contact_chain)

            # TODO: Needs a special check for contact==self.email.

            # Recompute the latest beliefs.
            for contact in {sender} | contacts:
                self.get_latest_view(contact)

    def get_contact_head_from_view(self, view, contact):
        """
        Try accessing a claim as oneself, and fall back to a public reader.

        :param view: View to query
        :param contact: Contact of interest
        :returns: Contact's head block, or None
        """
        with self.params.as_default():
            claim = view.get(contact)
            if claim is not None:
                return deserialize_block(claim)
        with PUBLIC_READER_PARAMS.as_default():
            claim = view.get(contact)
            if claim is not None:
                return deserialize_block(claim)

    def update_chain(self):
        """Force a chain update.

        Commits views and capabilities in the queues to the chain.
        """
        logger.debug('%s / chain update', self.email)

        with self.params.as_default():
            # Refresh views of all friends and contacts in queued capabilities.
            for friend, contacts in self.queued_caps.items():
                self.get_latest_view(friend)
                for contact in contacts:
                    self.get_latest_view(contact)

            # Add the latest own encryption key.
            if self.queued_identity_info is not None:
                self.state.identity_info = self.queued_identity_info

            # Mark queued views as committed.
            for friend, view in self.queued_views.items():
                self.committed_views[friend] = view

            # Put heads of previously committed views into the state.
            for friend, view in self.committed_views.items():
                latest_block = view.chain.store.get(view.head)
                self.state[friend] = serialize_block(latest_block)
                self.committed_views[friend] = view

            # Collect DH keys for all readers.
            dh_pk_by_reader = {}
            readers = set(self.queued_caps.keys()) | self.committed_caps.keys()
            for reader in readers:
                reader_dh_pk = None
                # If the buffer is for the public reader:
                if reader == PUBLIC_READER_LABEL:
                    reader_dh_pk = PUBLIC_READER_PARAMS.dh.pk

                # Otherwise, try to find the DH key in views.
                else:
                    view = self.get_latest_view(reader, save=False)
                    if view is not None:
                        reader_dh_pk = view.params.dh.pk

                if reader_dh_pk is not None:
                    dh_pk_by_reader[reader] = reader_dh_pk

            # Grant the accesses.
            for reader, contacts in self.queued_caps.items():
                if len(contacts) == 0:
                    continue
                if reader in self.committed_caps:
                    self.committed_caps[reader].update(contacts)
                else:
                    self.committed_caps[reader] = set(contacts)

            for reader, reader_dh_pk in dh_pk_by_reader.items():
                contacts = self.committed_caps[reader]
                self.state.grant_access(reader_dh_pk, contacts)

            # Commit state.
            head = self.state.commit(target_chain=self.chain,
                                     tree_store=self.tree_store)

            # Flush the view and caps queues.
            self.queued_views.clear()
            self.queued_caps.clear()

    def update_key(self, mtime=None):
        """
        Force update of the encryption key, and the chain.
        """
        logger.debug('%s / key update', self.email)
        self.queued_identity_info = Agent.generate_public_key()
        self.update_chain()
        if mtime is not None:
            self.date_of_last_key_update = datetime.fromtimestamp(mtime)

    def __repr__(self):
        return 'Agent("%s")' % self.email

