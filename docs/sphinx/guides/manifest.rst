Format du manifeste
===================

Le manifeste ``okf-base.yaml`` déclare les conventions de la base documentaire.

Structure
---------

.. code-block:: yaml

   okf_version: "0.1"

   base:
     name: Ma Base
     roots:
       - path: docs/
     reserved_files:
       index: index.md
       log: log.md
     status_field: statut
     link_resolution:
       external_refs:
         - Wikipedia

   profile:
     types:
       concept:
         required: [type, titre]
         optional: [statut, tags]
         status_values: [brouillon, validé, archivé]
       reference:
         required: [type]
         status_values: false
     date_fields: [created, updated]

   hygiene:
     broken_links: warn
     split_candidates: warn
     reserved_files: error
     unknown_fields: off

Sections
--------

**base** (obligatoire)
   Racines de la base, fichiers réservés, champ de statut, références externes.

**profile** (optionnel)
   Types de concepts avec leurs champs requis/optionnels et vocabulaires de statut.
   ``status_values: false`` interdit le champ de statut pour ce type.

**hygiene** (optionnel)
   Niveaux de contrôle pour chaque famille de règles : ``off`` | ``warn`` | ``error``.
