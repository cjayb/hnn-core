"""Class to handle the dipoles."""

# Authors: Mainak Jas <mainak.jas@telecom-paristech.fr>
#          Sam Neymotin <samnemo@gmail.com>

import warnings
import numpy as np
from copy import deepcopy
from numpy import convolve, hamming

from .viz import plot_dipole


def _hammfilt(x, winsz):
    """Convolve with a hamming window."""
    win = hamming(winsz)
    win /= sum(win)
    return convolve(x, win, 'same')


# Savitzky-Golay filtering, lifted and adapted from mne-python (0.22)
def _savgol_filter(data, h_freq, sfreq):
    """Filter the data using Savitzky-Golay polynomial method.

    Parameters
    ----------
    data : array-like
        The data to filter (1D)
    h_freq : float
        Approximate high cutoff frequency in Hz. Note that this
        is not an exact cutoff, since Savitzky-Golay filtering
        is done using polynomial fits
        instead of FIR/IIR filtering. This parameter is thus used to
        determine the length of the window over which a 5th-order
        polynomial smoothing is applied.
    sfreq : float
        Sampling rate

    Returns
    -------
    filt_data : array-like
        The filtered data
    """  # noqa: E501
    from scipy.signal import savgol_filter

    h_freq = float(h_freq)
    if h_freq >= sfreq / 2.:
        raise ValueError('h_freq must be less than half the sample rate')

    # savitzky-golay filtering
    window_length = (int(np.round(sfreq / h_freq)) // 2) * 2 + 1
    # loop over 'agg', 'L2', and 'L5'
    filt_data = savgol_filter(data, axis=-1, polyorder=5,
                              window_length=window_length)
    return filt_data


def simulate_dipole(net, n_trials=None, record_vsoma=False,
                    record_isoma=False, postproc=True):
    """Simulate a dipole given the experiment parameters.

    Parameters
    ----------
    net : Network object
        The Network object specifying how cells are
        connected.
    n_trials : int | None
        The number of trials to simulate. If None, the value in
        net.params['N_trials'] is used (must be >0)
    record_vsoma : bool
        Option to record somatic voltages from cells
    record_isoma : bool
        Option to record somatic currents from cells
    postproc : bool
        If False, no postprocessing applied to the dipole

    Returns
    -------
    dpls: list
        List of dipole objects for each trials
    """

    from .parallel_backends import _BACKEND, JoblibBackend

    if _BACKEND is None:
        _BACKEND = JoblibBackend(n_jobs=1)

    if n_trials is None:
        n_trials = net.params['N_trials']
    if n_trials < 1:
        raise ValueError("Invalid number of simulations: %d" % n_trials)

    # XXX needed in mpi_child.py:run()#L103; include fix in #211 or later PR
    net.params['N_trials'] = n_trials
    net._instantiate_drives(n_trials=n_trials)

    if isinstance(record_vsoma, bool):
        net.params['record_vsoma'] = record_vsoma
    else:
        raise TypeError("record_vsoma must be bool, got %s"
                        % type(record_vsoma).__name__)

    if isinstance(record_isoma, bool):
        net.params['record_isoma'] = record_isoma
    else:
        raise TypeError("record_isoma must be bool, got %s"
                        % type(record_isoma).__name__)

    dpls = _BACKEND.simulate(net, n_trials, postproc)

    return dpls


def read_dipole(fname, units='nAm'):
    """Read dipole values from a file and create a Dipole instance.

    Parameters
    ----------
    fname : str
        Full path to the input file (.txt)

    Returns
    -------
    dpl : Dipole
        The instance of Dipole class
    """
    dpl_data = np.loadtxt(fname, dtype=float)
    dpl = Dipole(dpl_data[:, 0], dpl_data[:, 1:4])
    if units == 'nAm':
        dpl.units = units
    return dpl


def average_dipoles(dpls):
    """Compute dipole averages over a list of Dipole objects.

    Parameters
    ----------
    dpls: list of Dipole objects
        Contains list of dipole objects, each with a `data` member containing
        'L2', 'L5' and 'agg' components

    Returns
    -------
    dpl: instance of Dipole
        A new dipole object with each component of `dpl.data` representing the
        average over the same components in the input list
    """
    # need at least one Dipole to get times
    if len(dpls) < 2:
        raise ValueError("Need at least two dipole object to compute an"
                         " average")

    for dpl_idx, dpl in enumerate(dpls):
        if dpl.nave > 1:
            raise ValueError("Dipole at index %d was already an average of %d"
                             " trials. Cannot reaverage" %
                             (dpl_idx, dpl.nave))

    agg_avg = np.mean(np.array([dpl.data['agg'] for dpl in dpls]), axis=0)
    L2_avg = np.mean(np.array([dpl.data['L2'] for dpl in dpls]), axis=0)
    L5_avg = np.mean(np.array([dpl.data['L5'] for dpl in dpls]), axis=0)

    avg_dpl_data = np.c_[agg_avg,
                         L2_avg,
                         L5_avg]

    avg_dpl = Dipole(dpls[0].times, avg_dpl_data)

    # set nave to the number of trials averaged in this dipole
    avg_dpl.nave = len(dpls)

    return avg_dpl


class Dipole(object):
    """Dipole class.

    Parameters
    ----------
    times : array (n_times,)
        The time vector (in ms)
    data : array (n_times x 3)
        The data. The first column represents 'agg',
        the second 'L2' and the last one 'L5'
    nave : int
        Number of trials that were averaged to produce this Dipole. Defaults
        to 1

    Attributes
    ----------
    times : array
        The time vector
    sfreq : float
        The sampling frequency (in Hz)
    data : dict of array
        The dipole with keys 'agg', 'L2' and 'L5'
    nave : int
        Number of trials that were averaged to produce this Dipole
    """

    def __init__(self, times, data, nave=1):  # noqa: D102
        self.units = 'fAm'
        self.N = data.shape[0]
        self.times = times
        self.data = {'agg': data[:, 0], 'L2': data[:, 1], 'L5': data[:, 2]}
        self.nave = nave
        self.sfreq = 1000. / (times[1] - times[0])  # NB assumes len > 1

    def copy(self):
        """Return a copy of the Dipole instance

        Returns
        -------
        dpl_copy : instance of Dipole
            A copy of the Dipole instance.
        """
        return deepcopy(self)

    def post_proc(self, N_pyr_x, N_pyr_y, winsz, fctr):
        """ Apply baseline, unit conversion, scaling and smoothing

       Parameters
        ----------
        N_pyr_x : int
            Number of Pyramidal cells in x direction
        N_pyr_y : int
            Number of Pyramidal cells in y direction
        winsz : int
            Smoothing window
        fctr : int
            Scaling factor
        """
        self.baseline_renormalize(N_pyr_x, N_pyr_y)
        self.convert_fAm_to_nAm()
        self.scale(fctr)
        # XXX window_len given in samples in HNN GUI, but smooth expects
        # milliseconds
        window_len = winsz / (1e-3 * self.sfreq)
        self.smooth(window_len=window_len)

    def convert_fAm_to_nAm(self):
        """ must be run after baseline_renormalization()
        """
        for key in self.data.keys():
            self.data[key] *= 1e-6
        self.units = 'nAm'

    def scale(self, fctr):
        for key in self.data.keys():
            self.data[key] *= fctr
        return self

    def smooth(self, *, window_len=None, h_freq=None):
        """Smooth the dipole waveform using one of two methods

        Pass the window length-argument to convolve the data with a Hamming
        window of the desired length. Alternatively, pass the high frequency
        argument to apply a Savitzky-Golay filter, which will remove frequency
        components above this cutoff value (see `~scipy.signal.savgol_filter).

        Note that this method operates in-place, i.e., it will alter the data.
        If you prefer a filtered copy, consider using the
        `~hnn_core.dipole.copy`-method.

        Parameters
        ----------
        window_len : float or None
            The length (in ms) of a `~numpy.hamming` window to convolve the
            data with.
        h_freq : float or None
            Approximate high cutoff frequency in Hz. Note that this
            is not an exact cutoff, since Savitzky-Golay filtering
            is done using polynomial fits
            instead of FIR/IIR filtering. This parameter is thus used to
            determine the length of the window over which a 5th-order
            polynomial smoothing is applied.

        Returns
        -------
        dpl_copy : instance of Dipole
            A copy of the modified Dipole instance.
        """
        if window_len is None and h_freq is None:
            raise ValueError('either window_len or h_freq must be defined')
        elif window_len is not None and h_freq is not None:
            raise ValueError('set window_len or h_freq, not both')

        if window_len is not None:
            winsz = 1e-3 * window_len * self.sfreq
            if winsz > len(self.times):
                raise ValueError(
                    f'Window length too long: {winsz} samples; data length is '
                    f'{len(self.times)} samples')
            elif winsz <= 1:
                # XXX this is to allow param-files with len==0
                return

            for key in self.data.keys():
                self.data[key] = _hammfilt(self.data[key], winsz)

        elif h_freq is not None:
            if h_freq < 0:
                raise ValueError('h_freq cannot be negative')
            elif h_freq > 0.5 * self.sfreq:
                raise ValueError(
                    'h_freq must be less than half the sample rate')
            for key in self.data.keys():
                self.data[key] = _savgol_filter(self.data[key],
                                                h_freq,
                                                self.sfreq)
        return self

    def plot(self, tmin=None, tmax=None, layer='agg', decim=None, ax=None,
             units='nAm', scaling=None, show=True):
        """Simple layer-specific plot function.

        Parameters
        ----------
        tmin : float or None
            Start time of plot (in ms). If None, plot entire simulation.
        tmax : float or None
            End time of plot (in ms). If None, plot entire simulation.
        layer : str
            The layer to plot. Can be one of 'agg', 'L2', and 'L5'
        decimate : int
            Factor by which to decimate the raw dipole traces (optional)
        ax : instance of matplotlib figure | None
            The matplotlib axis
        units : str | None
            The physical units of the data, used for axis label. Defaults to
            ``units='nAm'``. Passing ``None`` results in units being omitted
            from plot.
        scaling : float | None
            The scaling to apply to the dipole data in order to achieve the
            specified ``units`` when plotting. Defaults to None, which applies
            unit scaling (1x). For example, use``scaling=1e-6`` to scale fAm to
            nAm.
        show : bool
            If True, show the figure

        Returns
        -------
        fig : instance of plt.fig
            The matplotlib figure handle.
        """
        return plot_dipole(dpl=self, tmin=tmin, tmax=tmax, ax=ax, layer=layer,
                           decim=decim, units=units, scaling=scaling,
                           show=show)

    def baseline_renormalize(self, N_pyr_x, N_pyr_y):
        """Only baseline renormalize if the units are fAm.

        Parameters
        ----------
        N_pyr_x : int
            Nr of cells (x)
        N_pyr_y : int
            Nr of cells (y)
        """
        if self.units != 'fAm':
            print("Warning, no dipole renormalization done because units"
                  " were in %s" % (self.units))
            return

        # N_pyr cells in grid. This is PER LAYER
        N_pyr = N_pyr_x * N_pyr_y
        # dipole offset calculation: increasing number of pyr
        # cells (L2 and L5, simultaneously)
        # with no inputs resulted in an aggregate dipole over the
        # interval [50., 1000.] ms that
        # eventually plateaus at -48 fAm. The range over this interval
        # is something like 3 fAm
        # so the resultant correction is here, per dipole
        # dpl_offset = N_pyr * 50.207
        dpl_offset = {
            # these values will be subtracted
            'L2': N_pyr * 0.0443,
            'L5': N_pyr * -49.0502
            # 'L5': N_pyr * -48.3642,
            # will be calculated next, this is a placeholder
            # 'agg': None,
        }
        # L2 dipole offset can be roughly baseline shifted over
        # the entire range of t
        self.data['L2'] -= dpl_offset['L2']
        # L5 dipole offset should be different for interval [50., 500.]
        # and then it can be offset
        # slope (m) and intercept (b) params for L5 dipole offset
        # uncorrected for N_cells
        # these values were fit over the range [37., 750.)
        m = 3.4770508e-3
        b = -51.231085
        # these values were fit over the range [750., 5000]
        t1 = 750.
        m1 = 1.01e-4
        b1 = -48.412078
        # piecewise normalization
        self.data['L5'][self.times <= 37.] -= dpl_offset['L5']
        self.data['L5'][(self.times > 37.) & (self.times < t1)] -= N_pyr * \
            (m * self.times[(self.times > 37.) & (self.times < t1)] + b)
        self.data['L5'][self.times >= t1] -= N_pyr * \
            (m1 * self.times[self.times >= t1] + b1)
        # recalculate the aggregate dipole based on the baseline
        # normalized ones
        self.data['agg'] = self.data['L2'] + self.data['L5']

    def write(self, fname):
        """Write dipole values to a file.

        Parameters
        ----------
        fname : str
            Full path to the output file (.txt)

        Outputs
        -------
        A tab separatd txt file where rows correspond
            to samples and columns correspond to
            1) time (s),
            2) aggregate current dipole (scaled nAm),
            3) L2/3 current dipole (scaled nAm), and
            4) L5 current dipole (scaled nAm)
        """

        if self.nave > 1:
            warnings.warn("Saving Dipole to file that is an average of %d"
                          " trials" % self.nave)

        X = np.r_[[self.times, self.data['agg'], self.data['L2'],
                   self.data['L5']]].T
        np.savetxt(fname, X, fmt=['%3.3f', '%5.4f', '%5.4f', '%5.4f'],
                   delimiter='\t')
