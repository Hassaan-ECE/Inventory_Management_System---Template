# Migration Notes

## What Changed

- Sync moved to a simplified shared-first model.
- One shared DB per variant is now the authoritative source of truth.
- Each source folder keeps its own local cache DB for view/search responsiveness.
- Runtime no longer depends on outbox replay, offline queues, tombstones, or `sync.lock`.
- Disconnected mode remains available for view/search only; edits/imports are disabled until reconnect.
- Background sync loss is surfaced in status messaging only (no modal popup for disconnect state).

## Compatibility Kept

- Existing equipment/import schema is still in place.
- Update checks still read the release manifest from the shared root.

## Expected Behavior

- Startup opens local cache and refreshes it from shared when reachable.
- Connected edits/archive/restore/verify/delete/import actions apply against shared authoritative state.
- Local cache is refreshed to match shared after sync/write cycles.
- Offline/disconnected periods keep view/search available while edit/import actions are disabled.
- Busy/offline communication is status-bar only; background sync loss does not raise modal alerts.

## Test Notes

- `ME_lab` focused sync/UI/dialog tests pass without requiring the Excel import dependency stack.
- Full repo collection still depends on optional packages such as `openpyxl` for import-pipeline tests.
