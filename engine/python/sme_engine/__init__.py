"""Moteur métier de SuiviEvalLab.

Le moteur est un processus enfant lancé par l'application de bureau. Il reçoit
des requêtes JSON-RPC 2.0 sur son entrée standard (une requête par ligne) et
répond sur sa sortie standard. Les journaux partent sur la sortie d'erreur.
"""

__version__ = "0.1.0"
