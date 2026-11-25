# Thin wrapper around run.py (works without make too: `python run.py film`)
PY ?= python
.PHONY: film radio-cut smoke keyframes shots music narration assemble experiments costs validate
film:        ; $(PY) run.py film
radio-cut:   ; $(PY) run.py radio-cut
smoke:       ; $(PY) run.py smoke
validate:    ; $(PY) run.py validate
keyframes:   ; $(PY) run.py keyframes
shots:       ; $(PY) run.py shots
music:       ; $(PY) run.py music
narration:   ; $(PY) run.py narration
assemble:    ; $(PY) run.py assemble
experiments: ; $(PY) run.py experiments
costs:       ; $(PY) run.py costs
