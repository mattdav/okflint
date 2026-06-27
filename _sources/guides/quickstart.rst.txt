Démarrage rapide
================

Installation
------------

.. code-block:: bash

   pip install okflint
   # ou avec uv :
   uv add okflint

Audit d'une base
----------------

.. code-block:: bash

   okflint audit --bundle /chemin/base --vault /chemin/vault

Affiche un résumé : nombre de fichiers, statut OKF, liens cassés, candidats au découpage.
Ajouter ``--apply`` pour écrire le rapport JSON dans ``.okflint/``.

Validation (gate CI)
--------------------

.. code-block:: bash

   okflint validate --manifest okf-base.yaml docs/

Retourne exit 0 si tous les fichiers sont conformes, exit 1 sinon.
Ajouter ``--json`` pour une sortie JSON exploitable en CI.
