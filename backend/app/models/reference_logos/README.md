# Reference Logos

Drop real screenshots of trusted brands' actual login pages here as
`<brand>.png` (e.g. `paypal.png`, `sbi.png`) — lowercase filename,
matching the `claimed_brand` values your callers will send.

**Don't have real screenshots yet?** Run this to generate synthetic
placeholders and prove the pipeline works end-to-end first:
```bash
python training/generate_placeholder_reference_logos.py
```
Replace them with real screenshots before your final submission/demo —
see `training/README.md` section 3 for how to capture those.

This folder is empty in the repo by default (`.gitkeep` only) so no
placeholder or real brand images ship in version control.
