Manifest format
===============

The ``okf-base.yaml`` manifest declares the conventions of the documentary base.

Structure
---------

.. code-block:: yaml

   okf_version: "0.1"

   base:
     name: My Base
     roots:
       - path: docs/
     reserved_files:
       index: index.md
       log: log.md
     link_resolution:
       external_refs:
         - Wikipedia

   profile:
     types:
       concept:
         required: [type, title]
         optional: [status, tags]
         status_values: [draft, validated, archived]
       reference:
         required: [type]
     date_fields: [created, updated]

   hygiene:
     broken_links: warn
     split_candidates: warn
     reserved_files: error
     unknown_fields: off

Sections
--------

**base** (required)
   Base roots, reserved files, external references.

**profile** (optional)
   Concept types with their required/optional fields. Any property may
   declare a controlled vocabulary via a ``<prop>_values`` key (e.g.
   ``status_values`` for a ``status`` property); this only constrains the
   value when the property is present, independently of whether it is
   required or optional.

**hygiene** (optional)
   Control levels for each rule family: ``off`` | ``warn`` | ``error``.
