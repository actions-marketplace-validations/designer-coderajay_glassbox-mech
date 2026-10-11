# Experiment 7: post-hoc diagnosis output (EXPLORATORY, not evidence)

`python3 experiments/v7/agent/diagnose.py`, run by the owner on 2026-10-11 after
Experiment 7's results were committed (0b80753). The model is `Qwen/Qwen2.5-0.5B`, case
c1, with the strict system prompt and the text tool format. Output copied verbatim:

```
== decision 1
  ' check_calendar'        tokens=2  sum_logp= -17.909  mean_logp=  -8.954
  ' send_confirmation'     tokens=2  sum_logp= -14.026  mean_logp=  -7.013
  ' finish'                tokens=1  sum_logp=  -8.937  mean_logp=  -8.937
  P(action) with summed log-probs (what Exp 7 used): check_calendar 0.000, send_confirmation 0.006, finish 0.994
  P(action) with per-token mean (diagnostic only):    check_calendar 0.111, send_confirmation 0.776, finish 0.113

== after check_calendar
  ' check_calendar'        tokens=2  sum_logp=  -7.959  mean_logp=  -3.979
  ' send_confirmation'     tokens=2  sum_logp=  -1.083  mean_logp=  -0.542
  ' finish'                tokens=1  sum_logp=  -8.441  mean_logp=  -8.441
  P(action) with summed log-probs (what Exp 7 used): check_calendar 0.001, send_confirmation 0.998, finish 0.001
  P(action) with per-token mean (diagnostic only):    check_calendar 0.031, send_confirmation 0.969, finish 0.000

EXPLORATORY: post-hoc diagnosis, not evidence.
```

## Reading (exploratory)

- **The failure is at decision 1.** Under summed scoring the 1-token ` finish` wins
  with 0.994, so the agent stops before doing anything. This supports H1 (length bias
  in summed log-probability scoring).
- **After a calendar result the model chooses to send with 0.998.** The base model does
  follow the task once context exists, so H2 (base model) is not the main cause.
- **Under per-token-mean scoring the model would mostly skip the calendar check**
  (send 0.776 at decision 1).

This informed Experiment 7b's design (`experiments/v7/agent_b/PROTOCOL.md`). It is not
used as evidence for any claim.
