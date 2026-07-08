Rules catalogue
===============

The full rules catalogue is maintained in ``config/RULES.md`` at the repository root.

Stages
------

- **OKF core** (``F001``, ``F002``, ``R001``, ``R002``) — always active, checks
  minimal conformance to OKF standard §9.
- **Profile** (``F101``, ``F102``, ``F105``, ``F106``, ``S102``) — active when a
  ``profile`` block is declared in the manifest.
- **Hygiene** (``F201``, ``L001``–``L003``, ``S202``, ``R201``) — opt-in via the
  ``hygiene`` key in the manifest, level ``warn`` or ``error``.

Severities
----------

- ``error`` — causes ``okflint validate`` to fail (exit 1)
- ``warning`` — displayed but does not fail (exit 0)
