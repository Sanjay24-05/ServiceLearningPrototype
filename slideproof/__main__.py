"""Start the local web interface."""
import tempfile
import threading
import webbrowser
from pathlib import Path

import uvicorn

from slideproof.web.app import create_app
from slideproof.web.runs import startup_check

HOST, PORT = "127.0.0.1", 8765


def main() -> None:
    for problem in startup_check():
        print(problem)
    app = create_app(Path(tempfile.gettempdir()) / "slideproof")
    threading.Timer(1.0, webbrowser.open,
                    args=(f"http://{HOST}:{PORT}/",)).start()
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
