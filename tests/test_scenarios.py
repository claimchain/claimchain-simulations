import pytest

from simulations.scenarios import *


@pytest.mark.parametrize('params', [
    SimulationParams(chain_update_buffer_size=0),
    SimulationParams(key_update_every_nb_sent_emails=50)])
def test_public_claimchain(context, params):
    with params.as_default():
        enc_status_data, _, _, _ = simulate_public_claimchain(context)
        print(enc_status_data.value_counts())
