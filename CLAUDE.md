# UO_Model3D

3D model of the Ultima Online body (0x190) for generating clothing, armour and weapon animations as `.vd` files. **Goal:** our body reproduces the UO body so that items made on our model fit the original UO model. Judge every change by this.

- Language: documentation, skills and commits are in English (commits: `UOModel3D: <what and why>`). The user may ask to switch to Polish; the conversation is in Polish by default. Keep messages short: result, blocker, decision.
- Push tested work to `main` without asking (`git push origin main`; if the session mandates another branch, push there, then `git push origin HEAD:main`). Never push untested work. No PR unless asked. **Never push to `claude/friendly-knuth-44xtfw`.**
- **Measure, don't trust:** base decisions on your own before/after measurements. Metrics: `pipeline/test_items.py` (baseline `docs/qa/items_after_head_smooth.json`, 0.722), `body_part_raster.py` + `body_part_qa.py` (IoU 0.899).
- Do not commit the user's sketches (kept outside the repo) or their renders.
- Docs: `README.md` (EN), `README_PL.md` (PL), `docs/PRZEKAZANIE.md` (session handoff, Polish), `docs/qa/`. Details are in the skills `.claude/skills/uo-*` (uo-environment-tests, uo-client-data, uo-body-skeleton, uo-items-render, uo-open-issues); when you change a rule, update the skill.
