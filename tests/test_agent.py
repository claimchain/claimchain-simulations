import pytest

from hippiehug import Chain
from claimchain import View, State, LocalParams

from simulations.agent import *


@pytest.fixture
def global_state(context):
    return GlobalState(context)


def test_agent_send_and_receive_email():
    alice = Agent('alice')
    bob = Agent('bob')

    message_metadata = alice.send_message(['bob'])
    bob.receive_message('alice', message_metadata)

    assert alice.get_latest_view('bob') is None
    assert bob.get_latest_view('alice').head == alice.head

    message_metadata = bob.send_message(['alice'])
    alice.receive_message('bob', message_metadata)

    assert alice.get_latest_view('bob').head == bob.head
    assert bob.get_latest_view('alice').head == alice.head


def test_agent_cross_references():
    alice = Agent('alice')
    bob = Agent('bob')
    carol = Agent('carol')

    # Carol -> Alice
    # Alice learns about Carol
    message_metadata = carol.send_message(['alice'])
    alice.receive_message('carol', message_metadata)

    # Alice -> Bob, and Carol in CC
    message_metadata = alice.send_message(['bob', 'carol'])
    bob.receive_message('alice', message_metadata,
                        other_recipients=['carol'])

    # Bob has learned about Alice...
    assert bob.get_latest_view('alice').head == alice.head
    # ...but not about Carol
    assert bob.get_latest_view('carol') is None

    # Bob -> Alice
    message_metadata = bob.send_message(['alice'])
    alice.receive_message('bob', message_metadata)

    # Alice -> Bob once again
    message_metadata = alice.send_message(['bob'])
    bob.receive_message('alice', message_metadata)

    # Bob has learned about both Alice and Carol
    assert bob.get_latest_view('alice').head == alice.head
    assert bob.get_latest_view('carol').head == carol.head


def test_agent_chain_update():
    alice = Agent('alice')
    bob = Agent('bob')
    carol = Agent('carol')

    # Carol -> Alice
    # Alice learns about Carol
    message_metadata = carol.send_message(['alice'])
    alice.receive_message('carol', message_metadata)

    # Alice -> Bob, and Carol in CC
    alice_head0 = alice.head
    message_metadata = alice.send_message(['bob', 'carol'])
    # Alice updates her chain, because she learned about Carol
    assert alice.head != alice_head0

    bob.receive_message('alice', message_metadata,
                        other_recipients=['carol'])

    # Bob -> Alice
    bob_head0 = bob.head
    message_metadata = bob.send_message(['alice'])
    # Bob updates his chain with Alice's latest view
    assert bob.head != bob_head0

    alice.receive_message('bob', message_metadata)

    # Alice -> Bob once again
    alice_head1 = alice.head
    message_metadata = alice.send_message(['bob'])
    # Alice learned about Bob's head, so she updates
    assert alice.head != alice_head1

    bob.receive_message('alice', message_metadata)

    # Bob -> Alice once again
    bob_head1 = bob.head
    message_metadata = bob.send_message(['alice'])
    assert bob.head != bob_head1


def test_agent_public_contacts_policy():
    public_setting = AgentSettings(
            introduction_policy=public_contacts_policy)
    with public_setting.as_default():
        alice = Agent('alice')
        bob = Agent('bob')
        carol = Agent('carol')

        # Carol -> Alice
        # Alice learns about Carol
        message_metadata = carol.send_message(['alice'])
        alice.receive_message('carol', message_metadata)

        # Alice -> Bob
        message_metadata = alice.send_message(['bob'])
        bob.receive_message('alice', message_metadata)

        # Bob learned about Carol
        assert bob.get_latest_view('carol') is not None
        assert bob.get_latest_view('alice') is not None
        # Carols doesn't know about Bob or Alice yet
        assert carol.get_latest_view('bob') is None
        assert carol.get_latest_view('alice') is None

        # Bob -> Carol
        message_metadata = bob.send_message(['carol'])
        carol.receive_message('bob', message_metadata)

        assert carol.get_latest_view('bob') is not None
        assert carol.get_latest_view('alice') is not None

        # Carol -> Alice
        message_metadata = carol.send_message(['alice'])
        alice.receive_message('carol', message_metadata)

        assert alice.get_latest_view('bob').head is not None
        assert alice.get_latest_view('carol').head is not None

        alice.send_message('whoever')

        assert alice.committed_caps[PUBLIC_READER_LABEL] == {'bob', 'carol'}
        assert bob.committed_caps[PUBLIC_READER_LABEL] == {'alice', 'carol'}
        assert carol.committed_caps[PUBLIC_READER_LABEL] == {'bob', 'alice'}


