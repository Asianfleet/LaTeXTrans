@echo off
call conda run -n latextrans python -c "from src.tui.app import run; run()" %*
