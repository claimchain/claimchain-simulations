import os
import six
import base64
import warnings
import itertools
import logging

from collections import defaultdict

from attr import attrs, attrib
from hippiehug import Chain
from claimchain import State, View, LocalParams
from claimchain.utils import ObjectStore
from defaultcontext import with_default_context


logger = logging.getLogger(__name__)


# Instead of using string 'public' as a shared secret for
# public claims, we assume there exist public DH key pair
# accessible by anybody --- for simplicity.
PUBLIC_READER_PARAMS = LocalParams.generate()

PUBLIC_READER_LABEL = 'public'


def latest_timestamp_resolution_policy(agent, views):
    # NOTE: Naive resolution policy that does not check for forks
    return max(views, key=lambda view: view.payload.timestamp)


def immediate_chain_update_policy(agent, recipients):
    # Check if any of the contacts or capability entries
    # that are relevant to the current message have
    # been updated. If yes, commit new block with the updates
    # before sending the message.
    # NOTE: This assumes that claims contain heads

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
    logger.info('%s / intro', agent.email)
    for recipient_email in recipient_emails - {agent.email}:
        # NOTE: Friends should be able to see what my belief about them is,
        # so no need to exclude recipient_email from recipient_emails here.
        agent.add_expected_reader(recipient_email, recipient_emails)



def public_contacts_policy(agent, recipients_emails):
    agent.add_expected_reader(PUBLIC_READER_LABEL,
            agent.committed_views.keys())


@attrs
class MessageMetadata(object):
    head = attrib()
    public_contacts = attrib()
    store = attrib()


@with_default_context(use_empty_init=True)
@attrs
class AgentSettings(object):
    conflict_resolution_policy = attrib(default=latest_timestamp_resolution_policy)
    chain_update_policy = attrib(default=immediate_chain_update_policy)
    introduction_policy = attrib(default=implicit_cc_introduction_policy)
    key_update_every_nb_sent_emails = attrib(default=None)


class Agent(object):
    '''
    Simulated claimchain user in the online deployment mode.
    '''
    def __init__(self, email):
        self.email = email
        self.params = LocalParams.generate()
        self.chain_store = ObjectStore()
        self.tree_store = ObjectStore()
        self.chain = Chain(self.chain_store)
        self.state = State()

        # Stats
        self.nb_sent_emails = 0

        # Committed views and capabilities
        self.committed_caps = {}
        self.committed_views = {}
        # ...and the ones queued to be committed.
        self.queued_identity_info = None
        self.queued_caps = {}
        self.queued_views = {}
        # Capabilities for unknown yet readers and of unknown yet contacts
        self.expected_caps = defaultdict(set)

        # Known beliefs of other people about other people.
        self.global_views = defaultdict(dict)
        # Contacts that senders have made available to this agent.
        self.contacts_by_sender = defaultdict(set)

        # Objects that were sent to each recipient.
        self.sent_object_keys_to_recipients = {}
        # Objects that were received from other people.
        self.global_store = ObjectStore()

        # Generate initial encryption key, and add first block
        # to the chain
        self.update_key()

    @property
    def head(self):
        return self.chain.head

    @property
    def current_enc_key(self):
        """
        Current encryption key
        """
        return self.state.identity_info

    @staticmethod
    def generate_public_key():
        """
        Generate (fake) public encryption key
        """
        # 4096 random bits in base64
        return base64.b64encode(os.urandom(4096 // 8))

    def add_expected_reader(self, reader, contacts):
        """
        Add contacts to be accessible by the reader

        No need to know the reader's DH key, and contact
        views at this point. As soon as these will be learned,
        expected capabilities will be moved to the queue.
        """
        if isinstance(contacts, six.string_types):
            warnings.warn("Contacts is a string type, an iterable of "
                          "identifiers is expected.")

        logger.info('%s / cap / %s: %s', self.email,
                    reader, contacts)

        if reader in self.committed_caps:
            for contact in contacts:
                if contact in self.committed_caps[reader]:
                    continue
                if contact in self.queued_caps[reader]:
                    continue
                self.expected_caps[reader].add(contact)
        else:
            self.expected_caps[reader].update(contacts)

        self._update_cap_buffer()

        logger.debug('Expected_caps: %s', self.expected_caps)
        logger.debug('Queued_caps: %s', self.queued_caps)

    def _update_cap_buffer(self):
        buffered_contacts_by_reader = defaultdict(set)

        for reader, contacts in self.expected_caps.items():
            reader_view = self.get_latest_view(reader)
            if reader_view is None and reader != PUBLIC_READER_LABEL:
                continue

            for contact in contacts:
                contact_view = self.get_latest_view(contact)
                if contact_view is not None:
                    if reader not in self.queued_caps:
                        self.queued_caps[reader] = {contact}
                    else:
                        self.queued_caps[reader].add(contact)
                    buffered_contacts_by_reader[reader].add(contact)

        # Clean empty expected_caps entries.
        for reader, contacts in buffered_contacts_by_reader.items():
            self.expected_caps[reader] -= contacts
            if not self.expected_caps[reader]:
                del self.expected_caps[reader]

    def get_latest_view(self, contact, save=True):
        """
        Resolve latest view for contact through social policy

        The method gathers candidate views for contact across local state,
        and runs social validation policy to decide on the best candidate.

        As a side effect, puts the resolved view in the queue.

        :param contact: Contact identifier
        :param save: Whether to save the resolved view to the queue
        """
        policy = AgentSettings.get_default().conflict_resolution_policy

        # Collect possible candidates
        candidate_views = set()
        # ...starting with existing views of the contact.
        if contact in self.committed_views:
            candidate_views.add(self.committed_views[contact])
        if contact in self.queued_views:
            candidate_views.add(self.queued_views[contact])

        # Get a view of contact in question from every friend.
        current_friends = set(self.committed_views.keys()) \
                        | set(self.queued_views.keys())
        for friend in current_friends - {contact}:
            candidate_view = self.global_views[friend].get(contact)
            if candidate_view is not None:
                candidate_views.add(candidate_view)

        # If no candidates, return None.
        if len(candidate_views) == 0:
            return None

        # Otherwise, resolve conflicts using a policy
        view = policy(self, candidate_views)
        # ...and add the resolved view to the queue.
        self.queued_views[contact] = view

        # Remove from queue if resolved view is the same as committed.
        if save:
            committed_view = self.committed_views.get(contact)
            if view == committed_view:
                del self.queued_views[contact]

        return view

    def send_message(self, recipients):
        """
        Compute additional data to be sent to recipients

        NOTE: May update the chain if required by the update policy

        :param recipients: An iterable of recipient identifiers (emails)
        :returns: ``MessageMetadata`` object
        """
        logger.info('%s -> %s', self.email, recipients)

        if len(recipients) == 0:
            return
        if isinstance(recipients, six.string_types):
            warnings.warn("Recipients is a string type, an iterable of "
                          "identifiers is expected.")
        if not isinstance(recipients, set):
            recipients = set(recipients)

        with self.params.as_default():
            intro_policy = AgentSettings.get_default().introduction_policy
            # Grant accesses according to introduction policy.
            intro_policy(self, recipients)

            # Decide whether to update the encryption key
            # TODO: Make key update decision a policy
            nb_sent_emails_thresh = AgentSettings.get_default() \
                    .key_update_every_nb_sent_emails

            if nb_sent_emails_thresh is not None and \
               self.nb_sent_emails > nb_sent_emails_thresh:
                self.update_key()

            else:
                # Decide whether to update the chain
                update_policy = AgentSettings.get_default().chain_update_policy
                if update_policy(self, recipients):
                    self.update_chain()

            local_object_keys = set()
            global_object_keys = set()

            # Add own chain blocks.
            # NOTE: Requires that chain and tree use separate stores
            local_object_keys.update(self.chain_store.keys())

            # Add evidence for public claims.
            public_contacts = self.committed_caps.get(PUBLIC_READER_LABEL) \
                              or set()
            for contact in public_contacts:
                object_keys = self.state.compute_evidence_keys(
                        PUBLIC_READER_PARAMS.dh.pk, contact)
                local_object_keys.update(object_keys)
                contact_view = self.committed_views.get(contact)
                if contact_view is not None:
                    global_object_keys.add(contact_view.head)

            # Compute evidence that needs to be sent to all recipients.
            for recipient in recipients:
                # NOTE: This assumes that claims contain heads
                accessible_contacts = self.committed_caps.get(recipient) \
                                      or set()
                for contact in accessible_contacts:
                    recipient_view = self.committed_views.get(recipient)
                    if recipient_view is None:
                        continue
                    contact_view = self.committed_views.get(contact)
                    if contact_view is not None:
                        # Add evidence for cross-references.
                        recipient_dh_pk = recipient_view.params.dh.pk
                        evidence_keys = self.state.compute_evidence_keys(
                                recipient_dh_pk, contact)
                        local_object_keys.update(evidence_keys)

                        # Add contact's latest block.
                        global_object_keys.add(contact_view.head)

            # Compute the minimal amount of objects that need to be sent in
            # this message.
            relevant_keys = local_object_keys | global_object_keys
            object_keys_to_send = set()
            for recipient in recipients:
                if recipient not in self.sent_object_keys_to_recipients:
                    self.sent_object_keys_to_recipients[recipient] = \
                            relevant_keys
                    object_keys_to_send = relevant_keys
                else:
                    object_keys_for_recipient = relevant_keys.difference(
                            self.sent_object_keys_to_recipients[recipient])
                    object_keys_to_send |= object_keys_for_recipient

            # Gather the objects by keys.
            message_store = {}
            for key in local_object_keys.intersection(object_keys_to_send):
                value = self.chain_store.get(key) or self.tree_store.get(key)
                if value is not None:
                    message_store[key] = value

            for key in global_object_keys.intersection(object_keys_to_send):
                value = self.global_store.get(key)
                if value is not None:
                    message_store[key] = value

            self.nb_sent_emails += 1
            return MessageMetadata(self.chain.head, public_contacts,
                                   message_store)

    def get_accessible_contacts(self, sender, message_metadata,
                                other_recipients=None):
        """
        Get the contacts that are expected to be accessible on sender's chain
        """
        # NOTE: Assumes other people's introduction policy is the same
        contacts = self.contacts_by_sender[sender]
        other_recipients = set(other_recipients) - {sender, self.email}
        for recipient in other_recipients | message_metadata.public_contacts:
            contacts.add(recipient)
        return contacts

    def receive_message(self, sender, message_metadata,
                        other_recipients=None):
        """
        Interpret incoming additional data

        :param sender: Sender identifier
        :param message_metadata: Additional data obtained by ``send_message``
        :param other_recipients: Identifiers of other known recipients of the
                                 message
        """
        logger.info('%s <- %s', self.email, sender)
        if other_recipients is None:
            other_recipients = set()

        with self.params.as_default():
            # Merge stores temporarily.
            merged_store = ObjectStore(self.global_store)
            for key, obj in message_metadata.store.items():
                merged_store[key] = obj

            sender_head = message_metadata.head
            sender_latest_block = merged_store[sender_head]
            self.global_store[sender_head] = \
                    sender_latest_block
            self.queued_views[sender] = View(
                    Chain(self.global_store,
                          root_hash=sender_head))
            full_sender_view = View(
                    Chain(merged_store,
                          root_hash=sender_head))

            # Add relevant objects from the message store.
            contacts = self.get_accessible_contacts(
                    sender, message_metadata, other_recipients)
            for contact in contacts:
                contact_head = self.get_contact_head_from_view(
                        full_sender_view, contact)
                if contact_head is None:
                    continue
                contact_latest_block = message_metadata.store.get(contact_head)
                if contact_latest_block is not None:
                    self.global_store[contact_head] = contact_latest_block

                # NOTE: Assumes people send only contacts' latest blocks
                contact_chain = Chain(self.global_store,
                                      root_hash=contact_head)
                self.global_views[sender][contact] = View(contact_chain)

            # Recompute the latest beliefs.
            for contact in {sender} | contacts:
                self.get_latest_view(contact)

            # TODO: This calls get_latest_view inside, so it can be called
            # twice per contact. Room for optimization here.
            self._update_cap_buffer()

    def get_contact_head_from_view(self, view, contact):
        """
        Try accessing cross-reference claim as yourself, and as a public reader

        :param view: View to query
        :param contact: Contact of interest
        :returns: Contacts head, or None
        """
        with self.params.as_default():
            claim = view.get(contact)
            if claim is not None:
                return claim
        with PUBLIC_READER_PARAMS.as_default():
            claim = view.get(contact)
        return claim

    def update_chain(self):
        """
        Force chain update

        Commits views and capabilities in the queues to the chain
        """
        logger.info('%s / chain update', self.email)

        with self.params.as_default():
            # Refresh views of all friends and contacts in queued capabilities.
            for friend, contacts in self.queued_caps.items():
                self.get_latest_view(friend)
                for contact in contacts:
                    self.get_latest_view(contact)

            # Add the latest own encryption key.
            if self.queued_identity_info is not None:
                self.state.identity_info = self.queued_identity_info

            # Get heads of queued views into the claimchain state.
            for friend, view in self.queued_views.items():
                claim = view.chain.head
                if claim is not None:
                    self.state[friend] = claim

            # Get capabilities in the capability buffer into the claimchain
            # state, for those subjects whose keys are known.
            for friend, contacts in self.queued_caps.items():
                if len(contacts) == 0:
                    continue

                friend_dh_pk = None
                # If the buffer is for the public 'reader':
                if friend == PUBLIC_READER_LABEL:
                    friend_dh_pk = PUBLIC_READER_PARAMS.dh.pk

                # Otherwise, try to find the DH key in views.
                else:
                    view = self.get_latest_view(friend, save=False)
                    if view is not None:
                        friend_dh_pk = view.params.dh.pk

                if friend_dh_pk is not None:
                    self.state.grant_access(friend_dh_pk, contacts)
                    if friend in self.committed_caps:
                        self.committed_caps[friend].update(contacts)
                    else:
                        self.committed_caps[friend] = set(contacts)

                else:
                    # This should not happen
                    raise warnings.warn('Cap reader DH key not known at the '
                                        'time of committing.')

            # Commit state
            head = self.state.commit(target_chain=self.chain,
                                     tree_store=self.tree_store)

            # Flush the view and caps buffers and update current state
            for friend, view in self.queued_views.items():
                self.committed_views[friend] = view

            logger.debug('Committed caps: %s', self.committed_caps)
            logger.debug('Committed views: %s', self.committed_views)
            self.queued_views.clear()
            self.queued_caps.clear()

    def update_key(self):
        """
        Force update of the encryption key, and the chain
        """
        logger.info('%s / key update', self.email)
        self.queued_identity_info = Agent.generate_public_key()
        self.update_chain()
