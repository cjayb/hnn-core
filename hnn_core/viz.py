"""Visualization functions."""

# Authors: Mainak Jas <mainak.jas@telecom-paristech.fr>
#          Sam Neymotin <samnemo@gmail.com>

import numpy as np
from itertools import cycle


def _check_scaling_units(scaling, units):
    if not isinstance(scaling, float):
        if scaling is None:
            scaling = 1  # allow implicitly asking for no scaling
        else:
            raise ValueError(f'scaling must be a float, got {type(scaling)}')
    if not isinstance(units, str):
        if units is None:
            units = ''  # allow implicitly asking for no scaling
        else:
            raise ValueError(f'units must be a string, got {type(units)}')
    return scaling, units


def _get_plot_data(dpl, layer, tmin, tmax, scaling=1):
    plot_tmin = dpl.times[0]
    if tmin is not None:
        plot_tmin = max(tmin, plot_tmin)
    plot_tmax = dpl.times[-1]
    if tmax is not None:
        plot_tmax = min(tmax, plot_tmax)

    mask = np.logical_and(dpl.times >= plot_tmin, dpl.times < plot_tmax)
    times = dpl.times[mask]
    data = scaling * dpl.data[layer][mask]

    return data, times


def _decimate_plot_data(decim, data, times, sfreq=None):
    from scipy.signal import decimate
    if isinstance(decim, int):
        decim = [decim]
    if not isinstance(decim, list):
        raise ValueError('the decimation factor must be a int or list'
                         f'of ints; got {type(decim)}')
    for dec in decim:
        data = decimate(data, dec)
        times = times[::dec]

    if sfreq is None:
        return data, times
    else:
        sfreq /= np.prod(decim)
        return data, times, sfreq


def plt_show(show=True, fig=None, **kwargs):
    """Show a figure while suppressing warnings.

    NB copied from :func:`mne.viz.utils.plt_show`.

    Parameters
    ----------
    show : bool
        Show the figure.
    fig : instance of Figure | None
        If non-None, use fig.show().
    **kwargs : dict
        Extra arguments for :func:`matplotlib.pyplot.show`.
    """
    from matplotlib import get_backend
    import matplotlib.pyplot as plt
    if show and get_backend() != 'agg':
        (fig or plt).show(**kwargs)


def plot_dipole(dpl, tmin=None, tmax=None, ax=None, layer='agg', decim=None,
                units='nAm', scaling=None, show=True):
    """Simple layer-specific plot function.

    Parameters
    ----------
    dpl : instance of Dipole | list of Dipole instances
        The Dipole object.
    tmin : float or None
        Start time of plot in milliseconds. If None, plot entire simulation.
    tmax : float or None
        End time of plot in milliseconds. If None, plot entire simulation.
    ax : instance of matplotlib figure | None
        The matplotlib axis
    layer : str
        The layer to plot. Can be one of
        'agg', 'L2', and 'L5'
    decim : int or list of int or None (default)
        Optional (integer) factor by which to decimate the raw dipole traces.
        The SciPy function :func:`~scipy.signal.decimate` is used, which
        recommends values <13. To achieve higher decimation factors, a list of
        ints can be provided. These are applied successively.
    units : str | None
        The physical units of the data, used for axis label. Defaults to
        ``units='nAm'``. Passing ``None`` results in units being omitted from
        plot.
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
    import matplotlib.pyplot as plt
    from .dipole import Dipole

    # NB units_str is applied to the label, includes parentheses: ' (nAm)'
    scaling, units = _check_scaling_units(scaling, units)

    if ax is None:
        fig, ax = plt.subplots(1, 1)

    if isinstance(dpl, Dipole):
        dpl = [dpl]

    for dpl_trial in dpl:
        if layer in dpl_trial.data.keys():

            # extract scaled data and times
            data, times = _get_plot_data(dpl_trial, layer, tmin, tmax,
                                         scaling=scaling)
            if decim is not None:
                data, times = _decimate_plot_data(decim, data, times)

            ax.plot(times, data)

    ax.ticklabel_format(axis='both', scilimits=(-2, 3))
    ax.set_xlabel('Time (ms)')
    ylabel = f'Dipole moment ({units})' if len(units) > 0 else 'Dipole moment'
    ax.set_ylabel(ylabel)
    if layer == 'agg':
        title_str = 'Aggregate (L2 + L5)'
    else:
        title_str = layer
    ax.set_title(title_str)

    plt_show(show)
    return ax.get_figure()


def plot_spikes_hist(cell_response, ax=None, spike_types=None, show=True):
    """Plot the histogram of spiking activity across trials.

    Parameters
    ----------
    cell_response : instance of CellResponse
        The CellResponse object from net.cell_response
    ax : instance of matplotlib axis | None
        An axis object from matplotlib. If None,
        a new figure is created.
    spike_types: string | list | dictionary | None
        String input of a valid spike type is plotted individually.
            Ex: 'poisson', 'evdist', 'evprox', ...
        List of valid string inputs will plot each spike type individually.
            Ex: ['poisson', 'evdist']
        Dictionary of valid lists will plot list elements as a group.
            Ex: {'Evoked': ['evdist', 'evprox'], 'Tonic': ['poisson']}
        If None, all input spike types are plotted individually if any
        are present. Otherwise spikes from all cells are plotted.
        Valid strings also include leading characters of spike types
            Example: 'ev' is equivalent to ['evdist', 'evprox']
    show : bool
        If True, show the figure.

    Returns
    -------
    fig : instance of matplotlib Figure
        The matplotlib figure handle.
    """
    import matplotlib.pyplot as plt
    spike_times = np.array(sum(cell_response._spike_times, []))
    spike_types_data = np.array(sum(cell_response._spike_types, []))

    unique_types = np.unique(spike_types_data)
    spike_types_mask = {s_type: np.in1d(spike_types_data, s_type)
                        for s_type in unique_types}
    cell_types = ['L5_pyramidal', 'L5_basket', 'L2_pyramidal', 'L2_basket']
    input_types = np.setdiff1d(unique_types, cell_types)

    if isinstance(spike_types, str):
        spike_types = {spike_types: [spike_types]}

    if spike_types is None:
        if any(input_types):
            spike_types = input_types.tolist()
        else:
            spike_types = unique_types.tolist()
    if isinstance(spike_types, list):
        spike_types = {s_type: [s_type] for s_type in spike_types}
    if isinstance(spike_types, dict):
        for spike_label in spike_types:
            if not isinstance(spike_types[spike_label], list):
                raise TypeError(f'spike_types[{spike_label}] must be a list. '
                                f'Got '
                                f'{type(spike_types[spike_label]).__name__}.')

    if not isinstance(spike_types, dict):
        raise TypeError('spike_types should be str, list, dict, or None')

    spike_labels = dict()
    for spike_label, spike_type_list in spike_types.items():
        for spike_type in spike_type_list:
            n_found = 0
            for unique_type in unique_types:
                if unique_type.startswith(spike_type):
                    if unique_type in spike_labels:
                        raise ValueError(f'Elements of spike_types must map to'
                                         f' mutually exclusive input types.'
                                         f' {unique_type} is found more than'
                                         f' once.')
                    spike_labels[unique_type] = spike_label
                    n_found += 1
            if n_found == 0:
                raise ValueError(f'No input types found for {spike_type}')

    if ax is None:
        fig, ax = plt.subplots(1, 1)

    color_cycle = cycle(['r', 'g', 'b', 'y', 'm', 'c'])

    bins = np.linspace(0, spike_times[-1], 50)
    spike_color = dict()
    for spike_type, spike_label in spike_labels.items():
        label = "_nolegend_"
        if spike_label not in spike_color:
            spike_color[spike_label] = next(color_cycle)
            label = spike_label

        color = spike_color[spike_label]
        ax.hist(spike_times[spike_types_mask[spike_type]], bins,
                label=label, color=color)
    ax.set_ylabel("Counts")
    ax.legend()

    plt_show(show)
    return ax.get_figure()


def plot_spikes_raster(cell_response, ax=None, show=True):
    """Plot the aggregate spiking activity according to cell type.

    Parameters
    ----------
    cell_response : instance of CellResponse
        The CellResponse object from net.cell_response
    ax : instance of matplotlib axis | None
        An axis object from matplotlib. If None,
        a new figure is created.
    show : bool
        If True, show the figure.

    Returns
    -------
    fig : instance of matplotlib Figure
        The matplotlib figure object.
    """

    import matplotlib.pyplot as plt
    spike_times = np.array(sum(cell_response._spike_times, []))
    spike_types = np.array(sum(cell_response._spike_types, []))
    spike_gids = np.array(sum(cell_response._spike_gids, []))
    cell_types = ['L2_basket', 'L2_pyramidal', 'L5_basket', 'L5_pyramidal']
    cell_type_colors = {'L5_pyramidal': 'r', 'L5_basket': 'b',
                        'L2_pyramidal': 'g', 'L2_basket': 'w'}

    if ax is None:
        fig, ax = plt.subplots(1, 1)

    ypos = 0
    for cell_type in cell_types:
        cell_type_gids = np.unique(spike_gids[spike_types == cell_type])
        cell_type_times, cell_type_ypos = [], []
        for gid in cell_type_gids:
            gid_time = spike_times[spike_gids == gid]
            cell_type_times.append(gid_time)
            cell_type_ypos.append(np.repeat(ypos, len(gid_time)))
            ypos = ypos - 1

        if cell_type_times:
            cell_type_times = np.concatenate(cell_type_times)
            cell_type_ypos = np.concatenate(cell_type_ypos)
        else:
            cell_type_times = []
            cell_type_ypos = []

        ax.scatter(cell_type_times, cell_type_ypos, label=cell_type,
                   color=cell_type_colors[cell_type])

    ax.legend(loc=1)
    ax.set_facecolor('k')
    ax.set_xlabel('Time (ms)')
    ax.get_yaxis().set_visible(False)
    ax.set_xlim(left=0)

    plt_show(show)
    return ax.get_figure()


def plot_cells(net, ax=None, show=True):
    """Plot the cells using Network.pos_dict.

    Parameters
    ----------
    net : instance of NetworkBuilder
        The NetworkBuilder object.
    ax : instance of matplotlib Axes3D | None
        An axis object from matplotlib. If None,
        a new figure is created.
    show : bool
        If True, show the figure.

    Returns
    -------
    fig : instance of matplotlib Figure
        The matplotlib figure handle.
    """
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 unused import

    if ax is None:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

    colors = {'L5_pyramidal': 'b', 'L2_pyramidal': 'c',
              'L5_basket': 'r', 'L2_basket': 'm'}
    markers = {'L5_pyramidal': '^', 'L2_pyramidal': '^',
               'L5_basket': 'x', 'L2_basket': 'x'}

    for cell_type in net.cellname_list:
        x = [pos[0] for pos in net.pos_dict[cell_type]]
        y = [pos[1] for pos in net.pos_dict[cell_type]]
        z = [pos[2] for pos in net.pos_dict[cell_type]]
        if cell_type in colors:
            color = colors[cell_type]
            marker = markers[cell_type]
            ax.scatter(x, y, z, c=color, marker=marker, label=cell_type)

    plt.legend(bbox_to_anchor=(-0.15, 1.025), loc="upper left")

    plt_show(show)
    return ax.get_figure()


def plot_tfr_morlet(dpl, *, freqs, n_cycles=7., tmin=None, tmax=None,
                    layer='agg', decim=None, padding='zeros', ax=None,
                    colorbar=True, show=True):
    """Plot Morlet time-frequency representation of dipole time course

    NB: Calls `~mne.time_frequency.tfr_array_morlet`, so ``mne`` must be
    installed.

    Parameters
    ----------
    dpl : instance of Dipole | list of Dipole instances
        The Dipole object.
    freqs : array
        Frequency range of interest.
    n_cycles : float or array of float, default 7.0
        Number of cycles. Fixed number or one per frequency.
    tmin : float or None
        Start time of plot in milliseconds. If None, plot entire simulation.
    tmax : float or None
        End time of plot in milliseconds. If None, plot entire simulation.
    layer : str, default 'agg'
        The layer to plot. Can be one of 'agg', 'L2', and 'L5'
    decim : int or list of int or None (default)
        Optional (integer) factor by which to decimate the raw dipole traces.
        The SciPy function :func:`~scipy.signal.decimate` is used, which
        recommends values <13. To achieve higher decimation factors, a list of
        ints can be provided. These are applied successively.
    padding : str or None
        Optional padding of the dipole time course beyond the plotting limits.
        Possible values are: 'zeros' for padding with 0's (default), 'mirror'
        for mirror-image padding.
    ax : instance of matplotlib figure | None
        The matplotlib axis
    colorbar : bool
        If True (default), adjust figure to include colorbar.
    show : bool
        If True, show the figure

    Returns
    -------
    fig : instance of matplotlib Figure
        The matplotlib figure handle.
    """

    import matplotlib.pyplot as plt
    from matplotlib.ticker import ScalarFormatter
    from mne.time_frequency import tfr_array_morlet

    data, times = _get_plot_data(dpl, layer, tmin, tmax)

    sfreq = dpl.sfreq
    if decim is not None:
        data, times, sfreq = _decimate_plot_data(decim, data, times,
                                                 sfreq=sfreq)

    if padding is not None:
        if not isinstance(padding, str):
            raise ValueError('padding must be a string (or None)')
        if padding == 'zeros':
            data = np.r_[np.zeros((len(data) - 1,)), data.ravel(),
                         np.zeros((len(data) - 1,))]
        elif padding == 'mirror':
            data = np.r_[data[-1:0:-1], data, data[-2::-1]]

    # MNE expects an array of shape (n_trials, n_channels, n_times)
    data = data[None, None, :]
    power = tfr_array_morlet(data, sfreq=sfreq, freqs=freqs,
                             n_cycles=n_cycles, output='power')

    if padding is not None:
        # get the middle portion after padding
        power = power[:, :, :, times.shape[0] - 1:2 * times.shape[0] - 1]

    if ax is None:
        fig, ax = plt.subplots(1, 1)

    im = ax.pcolormesh(times, freqs, power[0, 0, ...], cmap='inferno',
                       shading='auto')
    ax.set_xlabel('Time (ms)')
    ax.set_ylabel('Frequency (Hz)')

    if colorbar:
        fig = ax.get_figure()
        fig.subplots_adjust(right=0.8)
        l, b, w, h = ax.get_position().bounds
        cb_h = 0.8 * h
        cb_b = b + (h - cb_h) / 2
        cbar_ax = fig.add_axes([l + w + 0.05, cb_b, 0.03, cb_h], label='cbax')
        xfmt = ScalarFormatter()
        xfmt.set_powerlimits((-2, 2))
        fig.colorbar(im, cax=cbar_ax, format=xfmt)

    plt_show(show)
    return ax.get_figure()


def plot_psd(dpl, *, fmin=0, fmax=None, tmin=None, tmax=None, layer='agg',
             ax=None, units='nAm', scaling=None, show=True):
    """Plot power spectral density (PSD) of dipole time course

    Applies `~scipy.signal.periodogram` with ``window='hamming'``. Note that
    no spectral averaging is applied, as most ``hnn_core`` simulations are
    short-duration.

    Parameters
    ----------
    dpl : instance of Dipole
        The Dipole object.
    fmin : float
        Minimum frequency to plot (in Hz). Default: 0 Hz
    fmax : float
        Maximum frequency to plot (in Hz). Default: None (plot up to Nyquist)
    tmin : float or None
        Start time of data to include (in ms). If None, use entire simulation.
    tmax : float or None
        End time of data to include (in ms). If None, use entire simulation.
    layer : str, default 'agg'
        The layer to plot. Can be one of 'agg', 'L2', and 'L5'
    ax : instance of matplotlib figure | None
        The matplotlib axis.
    units : str | None
        The physical units of the data, used for axis label. Defaults to
        ``units='nAm'``. Passing ``None`` results in units being omitted from
        the plot.
    scaling : float | None
        The scaling to apply to the dipole data in order to achieve the
        specified ``units`` when plotting. Defaults to None, which applies
        unit scaling (1x). For example, use``scaling=1e-6`` to scale fAm to
        nAm.
    show : bool
        If True, show the figure

    Returns
    -------
    fig : instance of matplotlib Figure
        The matplotlib figure handle.
    """
    import matplotlib.pyplot as plt
    from scipy.signal import periodogram

    # NB units_str is applied to the label, includes parentheses: ' (nAm)'
    scaling, units = _check_scaling_units(scaling, units)

    sfreq = dpl.sfreq
    data, times = _get_plot_data(dpl, layer, tmin, tmax)

    freqs, Pxx = periodogram(data, sfreq, window='hamming', nfft=len(data))
    if ax is None:
        fig, ax = plt.subplots(1, 1)

    # ax.plot(freqs, np.sqrt(Pxx))
    ax.plot(freqs, Pxx)
    if fmax is not None:
        ax.set_xlim((fmin, fmax))
    ax.ticklabel_format(axis='both', scilimits=(-2, 3))
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel(f'Power ({units}' + r'$^2 \ Hz^{-1}$)')

    plt_show(show)
    return ax.get_figure()


# from mne-python, v/0.23dev0
def _check_nfft(n, n_fft, n_per_seg, n_overlap):
    """Ensure n_fft, n_per_seg and n_overlap make sense."""
    if n_per_seg is None and n_fft > n:
        raise ValueError(('If n_per_seg is None n_fft is not allowed to be > '
                          'n_times. If you want zero-padding, you have to set '
                          'n_per_seg to relevant length. Got n_fft of %d while'
                          ' signal length is %d.') % (n_fft, n))
    n_per_seg = n_fft if n_per_seg is None or n_per_seg > n_fft else n_per_seg
    n_per_seg = n if n_per_seg > n else n_per_seg
    if n_overlap >= n_per_seg:
        raise ValueError(('n_overlap cannot be greater than n_per_seg (or '
                          'n_fft). Got n_overlap of %d while n_per_seg is '
                          '%d.') % (n_overlap, n_per_seg))
    return n_fft, n_per_seg, n_overlap


# inspired by mne-python (time_frequency.psd_array_welch), v/0.23dev0
def plot_psd_welch(dpl, *, fmin=0, fmax=None, n_fft=2**14, n_overlap=0,
                   n_per_seg=2**12, tmin=None, tmax=None, layer='agg',
                   ax=None, show=True):
    """Plot Power Spectral Density of dipole time course using Welch's method

    Applies `~scipy.signal.welch` with ``window='hamming'``.

    Parameters
    ----------
    dpl : instance of Dipole
        The Dipole object.
    fmin : float
        Minimum frequency to plot (in Hz). Default: 0 Hz
    fmax : float
        Maximum frequency to plot (in Hz). Default: None (plot up to Nyquist)
    n_fft : int
        The length of FFT used, must be ``>= n_per_seg`` (default: 2**14).
        The segments will be zero-padded if ``n_fft > n_per_seg``.
    n_overlap : int
        The number of points of overlap between segments. Will be adjusted
        to be <= n_per_seg. The default value is 0.
    n_per_seg : int | None
        Length of each Welch segment (windowed with a Hamming window). Defaults
        to None, which sets n_per_seg equal to n_fft.
    tmin : float or None
        Start time of data to include (in ms). If None, use entire simulation.
    tmax : float or None
        End time of data to include (in ms). If None, use entire simulation.
    layer : str, default 'agg'
        The layer to plot. Can be one of 'agg', 'L2', and 'L5'
    ax : instance of matplotlib figure | None
        The matplotlib axis.
    show : bool
        If True, show the figure

    Returns
    -------
    fig : instance of matplotlib Figure
        The matplotlib figure handle.
    """
    import matplotlib.pyplot as plt
    from scipy.signal import welch

    sfreq = dpl.sfreq
    data, times = _get_plot_data(dpl, layer, tmin, tmax)
    n_fft, n_per_seg, n_overlap = _check_nfft(len(times), n_fft, n_per_seg,
                                              n_overlap)

    freqs, Pxx = welch(data, sfreq, nfft=n_fft, noverlap=n_overlap,
                       nperseg=n_per_seg, window='hamming')
    if ax is None:
        fig, ax = plt.subplots(1, 1)

    # ax.plot(freqs, np.sqrt(Pxx))
    ax.plot(freqs, Pxx)
    if fmax is not None:
        ax.set_xlim((fmin, fmax))
    ax.ticklabel_format(axis='both', scilimits=(-2, 3))
    ax.set_xlabel('Frequency (Hz)')
    # ax.set_ylabel(f'Power ({dpl.units} / ' + r'$\sqrt{Hz}$' + ')')
    ax.set_ylabel(f'Power ({dpl.units}' + r'$^2 \ Hz^{-1}$)')

    plt_show(show)
    return ax.get_figure()
