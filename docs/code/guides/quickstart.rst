Quick start
===========

Installation
------------

.. code-block:: bash

   pip install okflint
   # or with uv:
   uv add okflint

Auditing a base
---------------

.. code-block:: bash

   okflint audit --bundle /path/to/base --vault /path/to/vault

Displays a summary: file count, OKF status, broken links, split candidates.
Add ``--apply`` to write the JSON report to ``.okflint/``.

Validation (CI gate)
--------------------

.. code-block:: bash

   okflint validate --manifest okf-base.yaml docs/

Returns exit 0 if all files are conformant, exit 1 otherwise.
Add ``--json`` for machine-readable JSON output suitable for CI.

Validating a manifest alone
----------------------------

.. code-block:: bash

   okflint validate-manifest okf-base.yaml

Checks the manifest's own structure, without scanning the base it declares.
Returns exit 0 if valid, exit 2 otherwise (never exit 1). Add ``--json`` for
machine-readable output.
