**What changes**
<!-- A short description. If the layout itself changed, list the key, the shift
     state and the code points involved. -->

**Checklist**
- [ ] `python3 tools/generate.py` has been run, so every platform file matches the layout
- [ ] `python3 tools/validate.py` passes
- [ ] If the layout changed: the `version` in `layout/us-intl-scientific.toml` is bumped
- [ ] If the layout changed: the affected table in `README.md` is updated

<!-- The overview picture rebuilds itself: CI runs tools/render.py on every push
     and commits the result if it changed. -->
