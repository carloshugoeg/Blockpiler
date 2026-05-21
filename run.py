#!/usr/bin/env python3
import os
from server.app import create_app

app, socketio = create_app()

if __name__ == '__main__':
    use_reloader = os.getenv('USE_RELOADER', '1') == '1'
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=use_reloader, allow_unsafe_werkzeug=True)
