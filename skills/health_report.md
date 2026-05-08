---
name: health_report
description: Generate a trading strategy health report
trigger: /health
---

Run the trading strategy health report on the Master Trader VPS (Elder Brain)
and send its output as the Telegram message.

Execute exactly this command:

  ssh ubuntu@100.96.225.124 /home/ubuntu/master-trader/run-health-report.sh --stdout 2>&1

Send the ENTIRE output as-is to Telegram. Do not summarize, edit, or add commentary.
The wrapper script handles credential injection (pulls REST creds from the running
Freqtrade container) and runs strategy_health_report.py against localhost on the VPS.

Why VPS: bots run on Elder Brain (`ft-keltner-bounce` 8095, `ft-funding-fade` 8096
bound to 127.0.0.1 only). The Mac path was deprecated 2026-04-27.

When this assistant migrates to the VPS, drop the `ssh ubuntu@100.96.225.124`
prefix and run the wrapper directly.
