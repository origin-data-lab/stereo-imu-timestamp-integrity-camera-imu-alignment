"""Export per-frame stereo timestamps (derived from in-stream SEI headers) to CSV.
Columns: recording, frame, left/right exposure start (us, device clock), exposure (us), centre delta."""
import sys, os, glob, numpy as np, pandas as pd
from odl_calib import DATA
OUT = sys.argv[1]; rows = []
for f in sorted(glob.glob(f'{DATA}/svh_20261026_*_left.npy')):
    rec = os.path.basename(f)[13:-9]; L = np.load(f); R = np.load(f.replace('_left', '_right')); k = min(len(L), len(R))
    df = pd.DataFrame(dict(recording=rec, frame=np.arange(k), left_exposure_start_us=L[:k, 1], right_exposure_start_us=R[:k, 1],
                           left_exposure_us=L[:k, 2], right_exposure_us=R[:k, 2]))
    df['start_delta_us'] = df.right_exposure_start_us - df.left_exposure_start_us
    df['centre_delta_us'] = df.start_delta_us + (df.right_exposure_us - df.left_exposure_us) / 2
    df['left_frame_interval_us'] = np.r_[np.nan, np.diff(L[:k, 1] + L[:k, 2] / 2)]
    rows.append(df)
D = pd.concat(rows); D.to_csv(f'{OUT}/a2_frame_timestamps.csv.gz', index=False, compression='gzip')
print(len(D), 'start delta max', D.start_delta_us.abs().max(), 'centre delta max', D.centre_delta_us.abs().max())
