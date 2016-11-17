#!/usr/bin/env python

"""Calculate basic efficiency statistics for a ztf_sim run."""

import sys
# hack to get the path right
sys.path.append('..')
import numpy as np
from collections import OrderedDict
from sqlalchemy import create_engine
import pandas as pd
from astropy.time import Time
import astropy.coordinates as coord
import astropy.units as u
from ztf_sim.constants import *
from ztf_sim.utils import *


def calc_stats(sim_name):

    df = df_read_from_sqlite(sim_name, tablename='Summary', directory='sims')

    stats = OrderedDict()

    stats['Simulation Name'] = sim_name

    # use max - min because there may be no observations some nights
    stats['Number of Nights'] = df.night.max() - df.night.min() + 1

    # possible nights
    possible_nights = np.linspace(df.night.min(), df.night.max(),
                                  stats['Number of Nights'])

    weathered_out_nights = 0
    actual_nights = df.night.unique()
    for night in possible_nights:
        if night not in actual_nights:
            weathered_out_nights += 1

    stats['Nights completely weathered out'] = weathered_out_nights

    mjds = df.expMJD.apply(np.floor).unique()
    t_mjds = Time(mjds, format='mjd')
    hours_of_darkness = approx_hours_of_darkness(t_mjds).to(u.hour).value

    stats['Average Hours of Darkness'] = np.mean(hours_of_darkness)

    stats['Total Science Time (h)'] = \
        (df.visitExpTime.sum() + df.slewTime.sum()) / 3600.

    stats['Average Science Time per night (h)'] = \
        stats['Total Science Time (h)'] / stats['Number of Nights']

    # time used for science: exposing or slewing/filter changing
    stats['Fraction of time usable'] = stats['Total Science Time (h)'] / \
        (stats['Average Hours of Darkness'] * stats['Number of Nights'])

    stats['Average Number of Exposures per hour'] = \
        len(df) / stats['Total Science Time (h)']

    # leave out NaNs from weather/nightly breaks
    w = np.isfinite(df.slewTime)

    # fraction of usable science time
    stats['Open Shutter Fraction'] = df[w].visitExpTime.sum() / \
        (df[w].visitExpTime.sum() + df[w].slewTime.sum())

    stats['Mean Time Between Exposures (s)'] = df[w].slewTime.mean()
    stats['Mean Slew Distance (deg)'] = np.degrees(df[w].slewDist.mean())

    stats['90% Time Between Exposures (s)'] = np.percentile(df[w].slewTime, 90)
    stats['90% Slew Distance (deg)'] = np.percentile(
        np.degrees(df[w].slewDist), 90)

    stats['Median Airmass'] = df.airmass.median()
    stats['90% Airmass'] = np.percentile(df.airmass, 90)

    # program breakdown
    pgrp = df.groupby('propID')
    stats['Program Fraction'] = (pgrp['fieldID'].agg(len) / len(df)).to_dict()

    # filter breakdown
    fgrp = df.groupby('filter')
    stats['Filter Fraction'] = (fgrp['fieldID'].agg(len) / len(df)).to_dict()

    # add filter ID column
    df['filterID'] = df['filter'].apply(lambda x: FILTER_NAME_TO_ID[x])
    ngrp = df.groupby('night')
    nchanges = ngrp['filterID'].agg(lambda x: np.sum(np.abs(np.diff(x))))
    stats['Average Nightly Filter Exchanges'] = np.mean(nchanges)
    stats['Average Filter Exchanges per hour'] = np.sum(nchanges) / \
        stats['Total Science Time (h)']

    # fraction of completed sequences: by program, by filter, ...
    pgrp = df.groupby(['night', 'propID', 'fieldID'])
    completion = pgrp['requestNumberTonight'].agg(
        np.max) * 1. / pgrp['totalRequestsTonight'].agg(np.max)
    completion.name = 'completion_fraction'
    completion = completion.reset_index()

    ngrp = completion.groupby('night')
    ngrp['completion_fraction'].agg(np.mean)

    pgrp2 = completion.groupby('propID')
    stats['Sequence Completion Fraction by Program'] = pgrp2[
        'completion_fraction'].agg(np.mean).to_dict()

    # average nightly figure of merit
    stats['Average Summed Figure of Merit per Science Hour'] = df.metricValue.sum() \
        / stats['Total Science Time (h)']

    for k, v in stats.iteritems():
        print('{}\t{}'.format(k, v))
    return stats

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: ./analyze_sim.py sim_name')
    else:
        calc_stats(sys.argv[1])
