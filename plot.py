import math
import argparse

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from glob import glob

from scipy import stats

parser = argparse.ArgumentParser(description='Plot fping/iperf delay distribution.')
parser.add_argument('--iperf', type=str, help='iperf .csv file.')
parser.add_argument('--fping', type=str, help='fping .csv file.')
parser.add_argument('--utc-offset', type=float, default=2, help='Hours offset from UTC.')

def load_df(pattern, utc_offset=None, min_hour=0, max_hour=24):
    '''Load all .csv files matching pattern, concatenate them, and return as a df.'''
    df = pd.concat(pd.read_csv(filename) for filename in glob(pattern))
    df.rename(columns=lambda x: x.strip(), inplace=True)
    if 'ms' in df and 'seconds' not in df:
        df['seconds'] = df['ms']/1e3
    if 'bytes' in df:
        df['KB'] = df['bytes'] / 1e3
        df['MB'] = df['bytes'] / 1e6

        # bin by kb
        max_bin = math.ceil(df['KB'].max())
        df['bin_kb'] = pd.cut(df['KB'], max_bin, labels=False)

        # bin by MB
        max_bin = math.ceil(df['MB'].max())
        df['bin_mb'] = pd.cut(df['MB'], max_bin, labels=False)

    # convert timestamp time to datetime
    if utc_offset:
        df['timestamp'] += utc_offset*3600
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df['hour'] = df['timestamp'].dt.hour

    # drop samples outside min_hour, max_hour
    df.drop(df[df['hour'] < min_hour].index, inplace=True)
    df.drop(df[df['hour'] > max_hour].index, inplace=True)

    return df

def pdf_from_series(series, bins='fd'):
    '''Return the PDF of the data samples in the series.'''
    pdf, bin_edges = np.histogram(series, bins=bins, density=True)
    pdf = np.insert(pdf, 0, 0)
    return pdf, bin_edges

def cdf_from_series(series):
    '''Return the CDF of the data samples in series.'''
    pdf, bin_edges = pdf_from_series(series)
    cdf = pdf.cumsum()
    cdf /= cdf[-1]
    return cdf, bin_edges

def fit_exponential(series, q=0.01):
    '''Fit an exponential RV to the sampels in series.'''
    loc0 = series.quantile(q=q) # filter outliers
    scale0 = series.mean() - loc0
    series = series.loc[series > loc0]
    series = series.loc[series < series.quantile(0.99)]
    loc, scale = stats.expon.fit(series)
    return loc, scale

def plot_distribution(df, type='ccdf', label=None, fit_distribution=True, plotf=None):
    '''Plot network delay histogram.'''
    assert type in ['pdf', 'cdf', 'ccdf']
    if plotf is None:
        plotf = plt.loglog
    if type == 'pdf':
        y, x = pdf_from_series(df['seconds'])
    elif type == 'cdf':
        y, x = cdf_from_series(df['seconds'])
    elif type == 'ccdf':
        cdf, x = cdf_from_series(df['seconds'])
        y = 1-cdf
    p = plotf(x, y, '.-', label=label)
    if fit_distribution:
        assert type == 'ccdf', 'not implemented'
        loc, scale = fit_exponential(df['seconds'])
        print(f'loc={loc} scale={scale}, fitted mean={loc+scale}, empirical mean: {df["seconds"].mean()}')
        plotf(
            x, 1-stats.expon.cdf(x, loc=loc, scale=scale),
            '--', color=p[-1].get_color(),
        )

def main():
    args = parser.parse_args()
    fping_df = None
    if args.fping:
        fping_df = load_df(args.fping)
    iperf_df = None
    if args.iperf:
        iperf_df = load_df(args.iperf)

    # delay histograms
    distribution_type = 'ccdf'
    fit_distribution = False
    plotf = plt.loglog
    plt.figure()

    if fping_df is not None:
        plot_distribution(
            fping_df, label='Ping', plotf=plotf,
            type=distribution_type, fit_distribution=fit_distribution,
        )

    if iperf_df is not None:
        bs = [1, 2, 3, 10]
        for b in bs:
            g = iperf_df.loc[iperf_df['bin_mb'] == b]
            print(f'{b} MB: {len(g)} samples')
            plot_distribution(
                g, label=f'{b} MB', plotf=plotf,
                type=distribution_type, fit_distribution=fit_distribution,
            )

    plt.xlim(1e-5, 1)
    plt.ylim(1e-4, 1)
    plt.title('Network delay')
    plt.xlabel('Delay t [s]')
    plt.ylabel('Pr(delay > t)')
    plt.grid()
    plt.legend()
    plt.show()
    return

if __name__ == '__main__':
    main()
