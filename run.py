# run.py
from server import make_server

if __name__ == "__main__":
    server = make_server()
    try:
        server.launch()      # blocks until Ctrl+C
    except KeyboardInterrupt:
        print("Shutting down server...")
        # The process will exit here, freeing the port.
        pass