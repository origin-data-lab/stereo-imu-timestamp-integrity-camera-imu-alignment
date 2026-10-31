# Methodology
* SEI payload type 240, 40 bytes, magic 'SVH', version 2: u64 svh_pts, u64 exposure_start_us, u32 exposure_us, u32 strobe_seq, u32 flags (layout inferred; emulation-prevention bytes removed before parsing).
* ZXIMU v6: 184-byte header, 40-byte records (u64 ts_us, u32 seq, u16 type: 2 gyro / 4 accel, ..., 3×f32).
* Frame continuity: exposure-centre interval; dropped = round(dt/33.333 ms) − 1 summed.
* Camera-IMU: PnP (IPPE + LM) per frame on undistorted corners, pairs 0.35–0.6 s apart, gyro integrated with bias from the quietest 10% of samples, Kabsch rotation with 3 rounds of residual trimming, offset sweep −40…+40 ms in 2 ms steps, bootstrap 500×.
