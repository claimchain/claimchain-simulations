import pickle
import os

from absl import app
from absl import flags
from tqdm import tqdm

from scripts.parse_enron import Message
from simulations import agent
from simulations.scenarios import do_simulation_step, init_simulations
from simulations.utils import Context
from simulations.agent import AgentSettings


FLAGS = flags.FLAGS
flags.DEFINE_integer('max_entries', 10000,
                     'Max number of log entries to simulate.')
flags.DEFINE_integer('log_offset', 98377,
                     'Starting entry in the global log.')
flags.DEFINE_integer('save_every_num', 100,
                     ('Save intermediate simulations reports every '
                      'n emails.'))
flags.DEFINE_integer('key_update_every_nb_days', 90,
                     'Key update frequency in days.')
flags.DEFINE_enum('introduction_policy', 'public_contacts',
                  ['implicit_cc', 'public_contacts'],
                  'Introduction policy.')
flags.DEFINE_string('parsed_enron_path', 'data/enron/parsed',
                    'Path to directory with parsed Enron pickles.')
flags.DEFINE_string('output',
                    'data/reports/public_claimchain_report-98377.pkl',
                    'Path and name of the output pickle.')


def make_agent_settings(key_update_every_nb_days, introduction_policy):
    if introduction_policy == 'implicit_cc':
        policy_fn = agent.implicit_cc_introduction_policy
    elif introduction_policy == 'public_contacts':
        policy_fn = agent.public_contacts_policy
    return AgentSettings(key_update_every_nb_days=key_update_every_nb_days,
                         introduction_policy=policy_fn)


def get_parsed_data(parsed_enron_path):
    with open(os.path.join(parsed_enron_path, 'replay_log.pkl'), 'rb') as h:
        enron_log = pickle.load(h)
    with open(os.path.join(parsed_enron_path, 'social.pkl'), 'rb') as h:
        social_graph = pickle.load(h)
    return enron_log, social_graph


def run_simulations(settings, enron_log, social_graph, max_entries, log_offset,
                    save_every_num, output, pbar=tqdm):
    context = Context(enron_log[log_offset:log_offset+max_entries],
                      social_graph=social_graph)
    state, reports = init_simulations(context)
    with settings.as_default():
        for index, email in pbar(list(enumerate(context.log))):
            state, reports = do_simulation_step(index, email, state, reports)
            if index % save_every_num == 0:
                with open(output, 'wb') as h:
                   pickle.dump(reports, h)

    with open(output, 'wb') as h:
       pickle.dump(reports, h)


def main(argv):
    enron_log, social_graph = get_parsed_data(FLAGS.parsed_enron_path)
    settings = make_agent_settings(FLAGS.key_update_every_nb_days,
                                   FLAGS.introduction_policy)
    report = run_simulations(settings, enron_log, social_graph,
                             FLAGS.max_entries, FLAGS.log_offset,
                             FLAGS.save_every_num, FLAGS.output)


if __name__ == '__main__':
    app.run(main)
