# Console v6 statuses (unqualified)

Wire c1/u4, arena layout, command bounds and ownership rejection predicates remain.
No new retry, bypass, automatic claim, session reset or foreign-response acceptance.
The separate version preserves immutable dev9 source and outcome.

| Status | Rejected evidence |
|---|---|
| -2010 | Normal worker free caller, but task context unavailable |
| -2011 | Unexpected worker free caller |
| -2012 | Copied command length differs |
| -2013 | Copied command bytes differ |
| -2014 | Missing copied CR terminator |
| -2015 | Parser already has pending records; known not-executed rejection, session preserved |
| -2016 | Foreign parser producer invalidated active ownership |
| -2017 | Tag low half did not increase |
| -2018 | Returned pending node outside exact object slots |
| -2019 | Returned tag channel/list association rejected |
| -2020 | Parser returned without final output or pending record |
| -2021 | Owned worker request has no parser; not executed, no object read |

Preserve the first specific rejection when a tag failure returns to the parser.
These codes diagnose a future run; they do not establish which path failed on dev9.
Before build verify ARMv5TE ARM/Thumb1 LE EABI5 softfloat and all native inputs;
then inspect emitted instructions and run rejection-path regressions.
