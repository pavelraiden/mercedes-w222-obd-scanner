"""
Gunicorn configuration for Mercedes W222 OBD Scanner production deployment
"""

import os
import multiprocessing

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes
workers = int(os.environ.get("WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
preload_app = True
timeout = 30
keepalive = 2

# Logging
accesslog = "/app/logs/gunicorn_access.log"
errorlog = "/app/logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "mercedes_obd_scanner"

# Server mechanics
daemon = False
pidfile = "/app/logs/gunicorn.pid"
user = "mercedes"
group = "mercedes"
tmp_upload_dir = None

# SSL (if needed)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Worker process management
worker_tmp_dir = os.getenv("WORKER_TMP_DIR", "/tmp")
worker_class = "uvicorn.workers.UvicornWorker"

# Application
wsgi_module = "web_app.main:app"


def when_ready(server):
    """Called just after the server is started."""
    server.log.info("Mercedes OBD Scanner server is ready. Listening on: %s", server.address)


def worker_int(worker):
    """Called just after a worker has been killed by SIGINT or SIGQUIT."""
    worker.log.info("Worker received INT or QUIT signal")


def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)


def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)


def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    worker.log.info("Worker initialized (pid: %s)", worker.pid)


def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info("Worker received SIGABRT signal")
