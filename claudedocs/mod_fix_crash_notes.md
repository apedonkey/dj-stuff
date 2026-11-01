# Crash notes: Tribe 0.12.6 mod build (2311), as of 2026-10-31

## Where the reviewer's findings are

None on disk. The review folder (backup/mod_fix_work/review/*.diff) holds the port diffs (original to merged), which is what the reviewer was given, not its findings. The reviewer's report never came back to the port job, which ended while still waiting on it.

## Crash risks found by reading the code

1. **Shared busy flag g_in_load (corrected 2026-10-31).** Every site that sets or checks the flag is inside the ProcessEvent hook (repl_pe). A race would need ProcessEvent to run on two threads at once, which nothing so far shows. Still, the check-then-set was not atomic. The atomic version (combo_atomic_2311.apk, not installed) uses an atomic test-and-set (ue_enter / ue_leave / ue_busy) at each site. It compiles with the same 7 warnings. Not device-tested.
2. **Per-frame driver from ProcessEvent.** It runs on the game thread at up to about 60 Hz. About 1,800 runs in the first minute, no crash. It re-enters ProcessEvent through the UE calls it makes; the busy flag above stops that from nesting.
3. **Stream apply on the poll thread.** Agora calls run off the game thread. Agora's API is generally thread-safe, but this has not been tested under load. Poll-thread code only reads memory and writes the stream size between calls.
4. **Stage backdrop.** SetupEnvironmentBackdrop has a new signature. Passing a wrong object type or a null could crash at stage load. The stage loads in tests so far, and the merged build has the null checks.

## Not verified

- Long sessions and crash behavior under load.
- The atomic change on the headset.
- Whether the reviewer's findings (never produced) would have changed any of the above.
