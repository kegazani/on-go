# Source

Runtime-код signal-processing-worker находится в пакете `src/signal_processing_worker`:

1. `service.py` - preprocessing pipeline: sync, clean, quality flags.
2. `repository.py` - SQL-доступ к metadata и quality report в `Postgres`.
3. `storage.py` - чтение raw и запись clean artifacts в `MinIO/S3`.
4. `main.py` - CLI entrypoint запуска worker-а.
