# ResNet50 INT8

The three reference repositories are independent Git checkouts pinned by
`repos.lock.json`; they are intentionally not embedded in this repository.

## Bootstrap a fresh clone

Install Python 3 and Git, then run one command from the repository root:

```powershell
python bootstrap.py
```

The command restores `CGRA_SIM`, `ndp-sim-ref`, and `NDPFuncModel` at their
exact locked commits. It then verifies the commit hashes, clean working-tree
state, configured source URLs, and the SHA-256 hash of tracked external
evidence. A mismatch or inaccessible repository produces a nonzero exit code.

To verify an existing checkout without downloading anything:

```powershell
python tools/sync_repositories.py verify
```

All locked repositories and mirrors are public. The bootstrap process never
advances to a branch tip: it checks out only the full commit IDs recorded in
the lock file.
