"""A2 — Frame-timestamp integrity, stereo sync, IMU stream integrity and
camera-IMU rotation / time-offset check.

Inputs (derived, in ODL_DATA): svh_*_{left,right}.npy (per-frame SEI timestamps:
svh_pts, exposure_start_us, exposure_us, strobe_seq, flags), *.imu (ZXIMU v6),
det_*.json (ChArUco detections).
Run: PYTHONPATH=. python3 a2_sync_imu.py RAW_IMU_DIR out_dir
"""
import sys, os, glob, json
import numpy as np, pandas as pd, cv2
from odl_calib import load, best, obj, device_calib, DATA
from read_zximu import load as imuload

RAW = sys.argv[1]; OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
recs = sorted({os.path.basename(p)[13:-9] for p in glob.glob(f'{DATA}/svh_20261026_*_left.npy')})
rows = []
for rec in recs:
    L = np.load(f'{DATA}/svh_20261026_{rec}_left.npy'); R = np.load(f'{DATA}/svh_20261026_{rec}_right.npy')
    cL = L[:, 1] + L[:, 2] / 2; cR = R[:, 1] + R[:, 2] / 2; k = min(len(cL), len(cR))
    dt = np.diff(cL); d = cR[:k] - cL[:k]
    row = dict(recording=rec, frames_left=len(L), frames_right=len(R), duration_s=(cL[-1] - cL[0]) / 1e6,
               frame_interval_median_us=np.median(dt), frame_interval_max_us=dt.max(), dropped_frames=int(np.sum(np.round(dt / 33333.3) - 1)),
               strobe_seq_consecutive=bool(np.all(np.diff(L[:, 3]) == 1) and np.all(np.diff(R[:, 3]) == 1)),
               lr_delta_median_us=np.median(d), lr_delta_p1_us=np.percentile(d, 1), lr_delta_p99_us=np.percentile(d, 99), lr_delta_max_abs_us=np.abs(d).max(),
               exposure_median_us=np.median(L[:, 2]), exposure_p5_us=np.percentile(L[:, 2], 5), exposure_p95_us=np.percentile(L[:, 2], 95),
               exposure_lag1_autocorr=np.corrcoef(L[:-1, 2], L[1:, 2])[0, 1])
    imu_name = rec.split('_')[0] + '_00000'
    p = f'{RAW}/20261026_{imu_name}.imu'
    if os.path.exists(p):
        r, _ = imuload(p); g = r[r['k1'] == 2]; a = r[r['k1'] == 4]
        gd = np.diff(g['ts'].astype(np.int64))
        row.update(imu_file=os.path.basename(p), imu_gyro_samples=len(g), imu_acc_samples=len(a), imu_rate_hz=1e6 / np.median(gd),
                   imu_max_gap_us=int(gd.max()), imu_seq_breaks=int(np.sum(np.diff(r['seq'].astype(np.int64)) != 1)),
                   video_start_minus_imu_start_ms=(cL[0] - g['ts'][0]) / 1e3, video_end_inside_imu=bool(cL[-1] <= g['ts'][-1] + 2000))
    rows.append(row)
TS = pd.DataFrame(rows); TS.round(3).to_csv(f'{OUT}/a2_timestamp_integrity.csv', index=False)
print(TS[['recording', 'frames_left', 'frames_right', 'dropped_frames', 'lr_delta_median_us', 'lr_delta_max_abs_us', 'imu_rate_hz', 'imu_max_gap_us']].to_string())

# ---- camera-IMU rotation and time offset from session C (hand-held rotations in front of a wall target)
dc = device_calib(); K, D = dc['cam0']['K'], dc['cam0']['D']; Rdev = dc['cam0']['T_cam_imu'][:3, :3]
def kabsch(A, B):
    U, S, Vt = np.linalg.svd(A.T @ B); return Vt.T @ np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))]) @ U.T
res = {}
for rec, kind in [('145719_00000', 'far')]:
    r, _ = imuload(f'{RAW}/20261026_{rec}.imu'); g = r[r['k1'] == 2]
    tg = g['ts'].astype(np.float64) / 1e6; G = np.c_[g['x'], g['y'], g['z']].astype(np.float64)
    gm = np.linalg.norm(G, axis=1); bias = np.median(G[gm < np.percentile(gm, 10)], 0)
    Ld = load(rec, 'left'); sv = np.load(f'{DATA}/svh_20261026_{rec}_left.npy'); tc = (sv[:, 1] + sv[:, 2] / 2) / 1e6
    ts = []; Rs = []; errs = []
    for a in Ld:
        b = best(a, 8)
        if b is None: continue
        o = obj(b['ids'], kind); p = np.array(b['pts'])
        u = cv2.fisheye.undistortPoints(p.reshape(-1, 1, 2), K, D).reshape(-1, 2)
        ok, rv, tv = cv2.solvePnP(o, u, np.eye(3), None, flags=cv2.SOLVEPNP_IPPE)
        ok, rv, tv = cv2.solvePnP(o, u, np.eye(3), None, rv, tv, True, flags=cv2.SOLVEPNP_ITERATIVE)
        pr, _ = cv2.projectPoints(o, rv, tv, np.eye(3), None); e = np.sqrt(np.mean(np.sum((pr.reshape(-1, 2) - u) ** 2, 1))) * K[0, 0]
        if e > 1.5: continue
        ts.append(tc[a['f']]); Rs.append(cv2.Rodrigues(rv)[0]); errs.append(e)
    ts = np.array(ts)
    def gyro_rot(t0, t1, off):
        i0 = np.searchsorted(tg, t0 + off); i1 = np.searchsorted(tg, t1 + off); Rm = np.eye(3)
        for k in range(i0, i1):
            Rm = Rm @ cv2.Rodrigues(((G[k] - bias) * (tg[k + 1] - tg[k])).reshape(3, 1))[0]
        return Rm
    idx = []; i = 0
    while i < len(ts):
        j = np.searchsorted(ts, ts[i] + 0.35)
        if j < len(ts) and ts[j] - ts[i] < 0.6: idx.append((i, j))
        i += 3
    def solve(off):
        A = []; B = []
        for i, j in idx:
            rc = cv2.Rodrigues((Rs[j] @ Rs[i].T).T)[0].ravel(); ri = cv2.Rodrigues(gyro_rot(ts[i], ts[j], off))[0].ravel()
            if np.linalg.norm(ri) < np.radians(4): continue
            A.append(ri); B.append(rc)
        A = np.array(A); B = np.array(B); keep = np.ones(len(A), bool)
        for _ in range(3):
            Rm = kabsch(A[keep], B[keep]); e = np.linalg.norm(B - (Rm @ A.T).T, axis=1)
            keep = e < max(np.radians(1.0), 2.5 * np.median(e))
        Rm = kabsch(A[keep], B[keep]); e = np.linalg.norm(B[keep] - (Rm @ A[keep].T).T, axis=1)
        return Rm, np.degrees(np.median(e)), int(keep.sum()), len(A), np.degrees(np.median(np.linalg.norm(A, axis=1)))
    curve = []
    for off in np.arange(-0.040, 0.0401, 0.002):
        Rm, med, nk, n, amp = solve(off)
        curve.append(dict(offset_ms=round(off * 1000, 1), residual_median_deg=med, pairs_used=nk, pairs_total=n,
                          angle_to_factory_deg=np.degrees(np.linalg.norm(cv2.Rodrigues(Rm @ Rdev.T)[0]))))
    C = pd.DataFrame(curve); C.round(4).to_csv(f'{OUT}/a2_camimu_offset_curve.csv', index=False)
    bestrow = C.loc[C.residual_median_deg.idxmin()]
    # bootstrap the rotation estimate at the best offset
    Rm, med, nk, n, amp = solve(bestrow.offset_ms / 1000)
    rng = np.random.default_rng(0); A = []; B = []
    for i, j in idx:
        rc = cv2.Rodrigues((Rs[j] @ Rs[i].T).T)[0].ravel(); ri = cv2.Rodrigues(gyro_rot(ts[i], ts[j], bestrow.offset_ms / 1000))[0].ravel()
        if np.linalg.norm(ri) < np.radians(4): continue
        A.append(ri); B.append(rc)
    A = np.array(A); B = np.array(B); e = np.linalg.norm(B - (Rm @ A.T).T, axis=1); keep = e < max(np.radians(1.0), 2.5 * np.median(e))
    A = A[keep]; B = B[keep]; bang = []
    for k in range(500):
        s = rng.integers(0, len(A), len(A)); Rb = kabsch(A[s], B[s]); bang.append(np.degrees(np.linalg.norm(cv2.Rodrigues(Rb @ Rdev.T)[0])))
    # half-width of offset interval where residual is within 10% of minimum
    thr = bestrow.residual_median_deg * 1.10; ok = C[C.residual_median_deg <= thr].offset_ms
    res[rec] = dict(views=int(len(ts)), pnp_rms_px_median=float(np.median(errs)), pairs_used=int(nk), pairs_total=int(n),
                    median_pair_rotation_deg=float(amp), best_offset_ms=float(bestrow.offset_ms), offset_within_10pct_ms=[float(ok.min()), float(ok.max())],
                    residual_median_deg=float(bestrow.residual_median_deg), angle_to_factory_deg=float(np.degrees(np.linalg.norm(cv2.Rodrigues(Rm @ Rdev.T)[0]))),
                    angle_to_factory_boot95_deg=[float(np.percentile(bang, 2.5)), float(np.percentile(bang, 97.5))],
                    factory_timeshift_cam0_ms=float(dc['cam0']['shift'] * 1000), gyro_bias_rad_s=bias.tolist())
json.dump(res, open(f'{OUT}/a2_camimu_result.json', 'w'), indent=1)
print(json.dumps(res, indent=1))
