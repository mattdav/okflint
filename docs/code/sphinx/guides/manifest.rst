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
     status_field: status
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
         status_values: false
     date_fields: [created, updated]

   hygiene:
     broken_links: warn
     split_candidates: warn
     reserved_files: error
     unknown_fields: off

Sections
--------

**base** (required)
   Base roots, reserved files, status field, external references.

**profile** (optional)
   Concept types with their required/optional fields and status vocabularies.
   ``status_values: false`` forbids the status field for that type.

**hygiene** (optional)
   Control levels for each rule family: ``off`` | ``warn`` | ``error``.
