# Video script, under 3 minutes, recorded against the live demo

Production timing rule: record when deliverables reach 9 of 10 or on 2026-11-10, whichever comes first. Every shot below is the real deployed page at the public demo URL. No mockups. Freeze commit must be named in the workspace STATE.md before recording.

| Beat | Time | On screen | Narration (owner voice, short sentences) |
|---|---|---|---|
| 1 Hook | 0:00-0:12 | Live page header, Elena line | Elena runs finance for a 14-person studio. Five supplier payouts. Three currencies. Seventy-two hours. |
| 2 Problem | 0:12-0:30 | Balances and reserve floors table | The balance she approved against this morning is gone by tonight. One late deposit and her spreadsheet lies. |
| 3 Approve | 0:30-0:55 | Approve USD and EUR payouts, open one spoken receipt | She approves two payouts. Each approval is locked to a hash of its exact evidence. The receipt can be read aloud. It is sealed. Change one character and the seal breaks. |
| 4 Hero | 0:55-1:25 | Land deposit EUR 500. EUR row turns INVALIDATED, USD stays VALID | A EUR deposit lands. Watch. Only the EUR approval falls, because only its evidence changed. The USD approval is untouched. Nobody re-plans the batch by hand. |
| 5 Refusal | 1:25-1:50 | Execute USD (pays), try stale EUR (409 reason on screen) | The good payout executes. The stale one refuses, and says why, next to the button. A stale approval cannot pay. Not by policy. By construction. |
| 6 Proof | 1:50-2:20 | Terminal: benchmark and gates commands with output | The deterministic engine scores 74 of 74 on the frozen benchmark. A hosted model alone scores 28 of 62 on the same rule cases. Run both commands from the README and check us. |
| 7 Close | 2:20-2:40 | Findings list, then the one sentence full screen | Archon Treasury recalculates Airwallex FX and supplier payouts when a deposit lands, invalidating stale approvals so cross-border teams never breach their cash reserve floor. |

Capture notes: reset the demo before beat 3. Keep the synthetic-mode banner visible in beat 1; honesty is part of the pitch. If sandbox credentials land before recording, re-shoot beat 4 against the live transport and say so in one line.
