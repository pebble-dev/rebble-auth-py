from gevent.monkey import patch_all; patch_all()
from gevent.wsgi import WSGIServer
import os
from auth import app

http_server = WSGIServer(('', int(os.environ.get('PORT', '5000'))), app)
http_server.serve_forever()
