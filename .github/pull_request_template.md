## What and why

## Checklist
- [ ] `python run_tests.py` passes
- [ ] If I changed behaviour: every engine agrees, and there's a regression test
- [ ] If I changed syntax: `grammar.ebnf`, both parsers, and `SPEC.md` (`python build_spec.py`) are updated
- [ ] If I added a keyword: it's documented (`docs_content.py`) and in the editor keyword lists
- [ ] I ran a fuzzer for a while (`python fuzz.py 3000`, `python spec_fuzz.py 3000`)

See CONTRIBUTING.md for the full feature checklist.
