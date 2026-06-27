Catalogue des règles
====================

Le catalogue complet des règles est maintenu dans :doc:`docs/RULES.md <../../RULES>`.

Étages
------

- **Cœur OKF** (``F001``, ``F002``, ``R001``, ``R002``) — toujours actif, vérifie la
  conformité minimale au standard OKF §9.
- **Profil** (``F101``–``F106``, ``S101``, ``S102``) — actif si un bloc ``profile`` est
  déclaré dans le manifeste.
- **Hygiène** (``F201``, ``L001``–``L003``, ``S201``, ``R201``) — opt-in par clé
  ``hygiene`` dans le manifeste, niveau ``warn`` ou ``error``.

Sévérités
---------

- ``error`` — fait échouer ``okflint validate`` (exit 1)
- ``warning`` — affiché mais n'échoue pas (exit 0)
