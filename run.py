#!/usr/bin/env python3
from server.app import create_app

app, socketio = create_app()

if __name__ == '__main__':
    socketio.run(app, port=5000, debug=True)
