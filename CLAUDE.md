# UO_Model3D

3D model of the Ultima Online body (0x190) for generating clothing, armour and weapon animations as `.vd` files. **Goal:** our body reproduces the UO body so that items made on our model fit the original UO model. Judge every change by this.

- Language: documentation, skills and commits are in English (commits: `UOModel3D: <what and why>`). The user may ask to switch to Polish; the conversation is in Polish by default. Keep messages short: result, blocker, decision.
- Work on the branch named at the start of the session and push tested work there (`git push -u origin <branch>`), without asking. Push to `main` only when the user says so. Never push untested work. No PR unless asked. **Never push to `claude/friendly-knuth-44xtfw`.**
- **Measure, don't trust:** base decisions on your own before/after measurements. Metrics: `pipeline/test_items.py` (baseline `docs/qa/items_after_natural_fit.json`, 0.723; all thresholds in `docs/qa/baselines.md`), `body_part_raster.py` + `body_part_qa.py` (IoU 0.899), `pose_naturalness.py` (natural 3D motion).
- Do not commit the user's sketches (kept outside the repo) or their renders.
- Docs: `README.md` (EN), `README_PL.md` (PL), `docs/qa/baselines.md` (QA thresholds and baselines). Details are in the skills `.claude/skills/uo-*` (uo-environment-tests, uo-client-data, uo-body-skeleton, uo-items-render, uo-open-issues); when you change a rule, update the skill.
