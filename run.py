"""
Entry point: python run.py
Then open http://localhost:8000
"""
import socket

import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    host = settings.get("app.host", "0.0.0.0")
    port = int(settings.get("app.port", 8000))

    # Give a clear instruction when another app instance already owns the port.
    probe_host = "127.0.0.1" if host == "0.0.0.0" else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if probe.connect_ex((probe_host, port)) == 0:
            print(
                f"The server is already running on http://localhost:{port}. "
                "Close the existing run.py window or stop its process before starting another instance."
            )
            

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
