# Phone ↔ Watch connectivity checklist

## Separate concerns

- **Polar H10 ↔ iPhone** uses Bluetooth LE. Drops here are unrelated to WatchConnectivity.
- **Apple Watch ↔ iPhone** uses mirrored `HKWorkoutSession` on supported OS versions, with **WatchConnectivity** as a fallback path in `SessionTransportFactory`.

## WatchConnectivity (fallback transport)

- `WCSession` activates on both sides; check logs for `[WC] activation` and any activation error.
- When not `isReachable`, envelopes use `transferUserInfo` (queued delivery). When reachable, `sendMessageData` is used.
- `updateApplicationContext` stores the last `start` / `stop` `session_id` for late wake scenarios.

## Mirrored workout transport (primary on device)

- iPhone should stay **foreground** during critical capture phases when possible.
- Watch charged, on wrist, companion app installed; Bluetooth and Wi‑Fi enabled on iPhone.
- Use the in-app **Reconnect** control if the mirrored session stalls after a timeout.

## Field debugging

1. Confirm Polar connected in the Polar UI before blaming the watch path.
2. Confirm `[WorkoutTransportIOS]` log lines for mirror start vs `[WC]` lines to see which transport is active.
3. If only WC is active, verify HealthKit permissions and OS version for workout mirroring.
