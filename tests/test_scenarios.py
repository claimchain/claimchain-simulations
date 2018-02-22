import sys
import pytest
import logging

from simulations.scenarios import *
from simulations.agent import *


# TODO: Investigate why this differs by one from dummies.
PUBLIC_NB_PLAINTEXTS = 721
PRIVATE_NB_PLAINTEXTS = 743


@pytest.mark.parametrize('agent_setting', [
    AgentSettings(introduction_policy=public_contacts_policy),
    AgentSettings(introduction_policy=public_contacts_policy,
                  key_update_every_nb_sent_emails=10),
    AgentSettings(introduction_policy=public_contacts_policy,
                  key_update_every_nb_sent_emails=50),
    AgentSettings(introduction_policy=public_contacts_policy,
                  key_update_every_nb_days=7),
    AgentSettings(introduction_policy=public_contacts_policy,
                  key_update_every_nb_days=30),
    AgentSettings(introduction_policy=public_contacts_policy,
                  key_update_every_nb_days=90),
    AgentSettings(introduction_policy=public_contacts_policy,
                  key_update_every_nb_days=365),
    ])
def test_public_claimchain(context, agent_setting):
    with agent_setting.as_default():
        reports = simulate_claimchain(context)
        enc_stats = reports.encryption_status_data.value_counts()
        logger.info(enc_stats)
        assert enc_stats[EncStatus.plaintext] == PUBLIC_NB_PLAINTEXTS


@pytest.mark.parametrize('agent_setting', [
    AgentSettings(),
    AgentSettings(key_update_every_nb_sent_emails=10),
    AgentSettings(key_update_every_nb_sent_emails=50),
    AgentSettings(key_update_every_nb_days=7),
    AgentSettings(key_update_every_nb_days=30),
    AgentSettings(key_update_every_nb_days=90),
    AgentSettings(key_update_every_nb_days=365),
    ])
def test_private_claimchain(context, agent_setting):
    with agent_setting.as_default():
        reports = simulate_claimchain(context)
        userset_mask = reports.participants_type_data == \
                ParticipantsTypes.userset
        enc_stats = reports.encryption_status_data.value_counts()
        logger.info(enc_stats)
        assert enc_stats[EncStatus.plaintext] == PRIVATE_NB_PLAINTEXTS
