# Physical Node Safety Contract

Issue: https://github.com/omarespejel/accountable-swarm/issues/3

The first physical-device path is trace-only by default. It must not move
SO-101, a camera rig, or any other hardware unless a later PR adds explicit
operator arming and device-specific safety checks.

## Defaults

- low-speed mode required;
- workspace bounds required;
- emergency stop path required;
- autonomous setup motion disabled;
- operator arming required for non-hold actions;
- `hold` is the only action accepted by the default trace-only sink.

## Non-Claims

This contract does not prove:

- SO-101 connectivity;
- safe physical operation;
- trained ACT policy;
- hardware readiness;
- demo readiness.

It only prevents the initial physical-node code path from silently becoming a
motion-capable API.
