# Authors: Yousra Bekhti <yousra.bekhti@gmail.com>
#          Alexandre Gramfort <alexandre.gramfort@telecom-paristech.fr>
#
# License: BSD (3-clause)

import os.path as op
import numpy as np

import warnings
from nose.tools import assert_true

import mne
from mne.datasets import testing
from mne.beamformer import rap_music


data_path = testing.data_path(download=False)
fname_ave = op.join(data_path, 'MEG', 'sample', 'sample_audvis-ave.fif')
fname_cov = op.join(data_path, 'MEG', 'sample', 'sample_audvis_trunc-cov.fif')
fname_fwd = op.join(data_path, 'MEG', 'sample',
                    'sample_audvis_trunc-meg-eeg-oct-4-fwd.fif')

warnings.simplefilter('always')  # enable b/c these tests throw warnings

meg, eeg = True, False


def read_forward_solution_meg(fname_fwd, **kwargs):
    fwd = mne.read_forward_solution(fname_fwd, **kwargs)
    return mne.pick_types_forward(fwd, meg=meg, eeg=eeg,
                                  exclude=['MEG 2443', 'EEG 053'])


def _get_data(event_id=1):
    """Read in data used in tests
    """
    # Read evoked
    evoked = mne.read_evokeds(fname_ave, event_id)
    evoked = mne.pick_types_evoked(evoked, meg=meg, eeg=eeg)
    evoked.crop(0, 0.3)

    forward = mne.read_forward_solution(fname_fwd)

    forward_surf_ori = read_forward_solution_meg(fname_fwd, surf_ori=True)
    forward_fixed = read_forward_solution_meg(fname_fwd, force_fixed=True,
                                              surf_ori=True)

    noise_cov = mne.read_cov(fname_cov)

    return evoked, noise_cov, forward, forward_surf_ori, forward_fixed


def simu_data(evoked, forward, noise_cov, n_dipoles, times):
    # Generate the two dipoles data
    mu, sigma = 0.1, 0.005
    s1 = 1 / (sigma * np.sqrt(2 * np.pi)) * np.exp(-(times - mu) ** 2 /
                                                   (2 * sigma ** 2))

    mu, sigma = 0.075, 0.008
    s2 = 1 / (sigma * np.sqrt(2 * np.pi)) * np.exp(-(times - mu) ** 2 /
                                                   (2 * sigma ** 2))
    data = np.array([s1, s2]) * 10e-10

    # data = np.array([s1]) * 10e-10
    src = forward['src']
    rng = np.random.RandomState(42)

    rndi = 100  # rng.randint(len(src[0]['vertno']))
    lh_vertno = src[0]['vertno'][[rndi]]

    rndi = 203  # rng.randint(len(src[1]['vertno']))
    rh_vertno = src[1]['vertno'][[rndi]]

    vertices = [lh_vertno, rh_vertno]
    # vertices = [lh_vertno, np.array([])]
    tmin, tstep = times.min(), 1 / evoked.info['sfreq']
    stc = mne.SourceEstimate(data, vertices=vertices, tmin=tmin, tstep=tstep)

    sim_evoked = mne.simulation.generate_evoked(forward, stc, evoked,
                                                noise_cov, snr=20,
                                                random_state=rng)

    return sim_evoked, stc

evoked, noise_cov, forward, forward_surf_ori, forward_fixed =\
    _get_data()

n_dipoles = 2
sim_evoked, stc = simu_data(evoked, forward_fixed, noise_cov, n_dipoles,
                            evoked.times)


def _check_dipoles(dipoles, fwd, ori=False, n_orient=1):
    src = fwd['src']
    pos1 = fwd['source_rr'][np.where(src[0]['vertno'] ==
                                     stc.vertices[0])]
    pos2 = fwd['source_rr'][np.where(src[1]['vertno'] ==
                                     stc.vertices[1])[0] +
                            len(src[0]['vertno'])]

    # Check the position of the two dipoles
    assert_true(dipoles[0].pos[0] in np.array([pos1, pos2]))
    assert_true(dipoles[1].pos[0] in np.array([pos1, pos2]))

    ori1 = fwd['source_nn'][np.where(src[0]['vertno'] ==
                                     stc.vertices[0])[0]]
    ori2 = fwd['source_nn'][np.where(src[1]['vertno'] ==
                                     stc.vertices[1])[0] +
                            len(src[0]['vertno'])]

    # Check the orientation of the first dipole
    assert_true(np.max(np.abs(np.dot(dipoles[0].ori[0],
                                     np.array([ori1, ori2]).T))) > 0.99)

    assert_true(np.max(np.abs(np.dot(dipoles[1].ori[0],
                                     np.array([ori1, ori2]).T))) > 0.99)

# Check dipoles for fixed ori
dipoles, residual = rap_music(sim_evoked, forward, noise_cov,
                              n_dipoles=n_dipoles, return_residual=True)

sim_evoked.plot(ylim=dict(grad=[-300, 150], mag=[-800, 800]))
residual.plot(ylim=dict(grad=[-300, 150], mag=[-800, 800]))

print dipoles[0].ori[0]
