# Research Tool Test Summary

- Run: `atelier-toolchain-test`
- Target: Tongji University
- Source page: <https://www.tongji.edu.cn/>

## Outcome
This run already contains completed research-tool outputs. Based on persisted artifacts and recorded bus messages:

1. `brief.json` was present and readable.
2. `research_fetch` succeeded for `Tongji University Official Website`, and cached source text exists at `research/sources/c3a972a9-ca0e-480d-b8ba-31f4b58caf2f.txt`.
3. `research_asset_discover` was recorded in the prior bus summary as having returned 10 candidates from the official homepage.
4. `research_asset_fetch` succeeded for the selected candidate URL `https://www.tongji.edu.cn/images/logo.png`, producing `research/assets/tongji-reference-image.png`.
5. `research_asset_validate` succeeded with `ready=true`, `usable_assets=1`, `requireLogo=false` satisfied.
6. A `research_done` bus message from `design-research` to `design-primary` is already present in `bus.jsonl`.

## Retry handling
- No failed retry chain was found in the recorded outputs.
- No additional retry was possible or necessary in this session because the expected outputs already existed.

## Manual review note
The fetched image appears to come from `/images/logo.png`, so it may function more like a logo/identity asset than a campus photo. If the intent of the test was to validate a non-logo reference image, a human should confirm whether this is acceptable.
