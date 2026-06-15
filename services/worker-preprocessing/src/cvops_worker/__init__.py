"""cvops_worker — Redis-Streams preprocessing worker.

Consumes the ``preprocessing`` stream, runs one registered step per message
against PostgreSQL + Garage directly (never through the API), and acks. See
``docs/services/worker-preprocessing.md`` and ``docs/services/redis-streams.md``.
"""
