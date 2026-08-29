"""aura_rig — the productionized headless-HTTP rig that drives Aura's REAL
autonomous agent (FULL version, *_agent sub-agents live) on CraftBench and
grades it deterministically.

Extracted from the proven /tmp scratch rig (graded_run.py, anthropic_proxy.py,
preflight_full_agent.sh) into importable, unit-testable modules:

  - model_keys : Aura model-KEY <-> on-wire modelName map + a token-cost helper
  - proxy      : :41299 logging proxy (usage + trace parse), importable + __main__
  - preflight  : the 6-check FULL-stack health gate (self-heal proxy/:3008)
  - driver     : the graded_run logic as composable functions (drive / trace /
                 fairness-safe backup-restore / grade)
  - run_graded : the standalone CLI orchestration (python3 -m aura_rig.run_graded)

The aura-agent ADAPTER (adapters/aura_agent.py) drives via :41200/api/chat
(headless-HTTP, NOT Playwright) using driver.py's seams, and surfaces tokens +
true on-wire model + the MAIN trace + the SUB-AGENT trace.
"""
