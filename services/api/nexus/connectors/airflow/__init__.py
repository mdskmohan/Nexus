"""Airflow connector."""

from nexus.connectors.airflow.client import AirflowClient, AirflowError
from nexus.connectors.airflow.connector import AirflowConnector, TaskFailure

__all__ = ["AirflowClient", "AirflowConnector", "AirflowError", "TaskFailure"]
