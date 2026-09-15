# Native console v5: borrowed pointer provenance

Dev12 hardware q1 showed flags17 and callbackClass0. It did not establish a valid
busy queue. This successor adds four32-bit values captured only at the actual
slot12 parser entry: object address, callback at+0x528, head at+0x584, and original
caller LR. It never follows the invalid head or reads additional object offsets.
HTTP returns a stored120-byte q2 snapshot, never dereferencing the parser.
The decoder accepts historical q1 and current q2; context is null for q1.
The old104-byte prefix and all old arena field offsets are unchanged.

The entry bridge reads LR from the existing detour stack frame, preserves
r0–r2 and maintains8-byte AAPCS stack alignment. Ownership/command policy stays
unchanged. Arena3628bytes must be rebuilt for all legacy/native components.
This is a private unqualified diagnostic component, not an AT execution fix.
