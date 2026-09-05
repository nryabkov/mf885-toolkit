# MF885 Community R3.8 return-zero comparator

Community R3.8 is a deliberately minimal native diagnostic comparator. It is
not a functional TTL release and adds no repeater, USSD or IMEI feature.

R3.7 used the stock `diagnostic.post_set` slot to build `output` and `off` on
the callback stack and call the exact stock property setter once. The later
command/argument-only live request proved that removing the accidental client
`output` field was not enough: all 114 request-body bytes were sent once, no
response byte arrived, and the MF885 disappeared from the reviewed USB/RNDIS
identity. That outcome does not prove whether the callback was entered or
whether the setter body failed.

R3.8 keeps the same stock diagnostic row and the same phase-3 `post_set` slot,
but replaces the whole R3.7 callback with the exact four-byte Thumb leaf
`movs r0,#0; bx lr`. The remaining 80 bytes of the former 84-byte reservation
stay zero. There are no calls, loads, stores, property publications, custom
state accesses or packet-hook changes. All other diagnostic callbacks remain
zero, and the stock Engineering, hidden `debugon`, `SystemChannelName`,
forwarding hook and templates remain byte-exact.

The browser keeps TTL visibly locked and sends no TTL or diagnostic request.
The separately authorized live discriminator, if R3.8 is installed, is the
same single authenticated `command=ttl,arg=off` SET. A later diagnostic GET is
allowed only after a complete accepted SET response. A response with stable
identity would clear callback registration/entry/return ABI and implicate the
removed R3.7 setter body. Another disappearance would show that the setter was
not necessary, leaving generic SET dispatch or the non-null `post_set`
boundary. One comparator cannot distinguish those last two hypotheses.
Neither outcome proves TTL.

The retained offline candidate is
`MF885_Community_0.3.8-community-r2-native-r12-cafe-r2.bin`, exactly 8,323,644
bytes, SHA-256
`327941f69cebee6f21422408f0016c18cd5608e5e4fc4b109fd02e9010787642`.
Its 64,962-byte build report hashes to
`7121892f9501b6ac85016e60eb364655e7b29cc3d1626c22a592a5774334eaf9`.
Two builds and reports are byte-identical, the independent container inspector
is green, and all 55 final conditions pass. Exactly six OSLO bytes change
inside the two declared four-byte ranges.

The current substantive firmware set is 15 tests: six native source/machine/
tamper scenarios, three WEBI/source scenarios and six deterministic native-
container/retained scenarios. Live comparator behavior, TTL getter/setter,
packet path, persistence, cold boot, repeatability and rollback remain
unproved. Firmware delivery and the later SET each require fresh exact
operator authorization.
