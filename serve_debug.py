from os import environ

from auth import app

app.run(environ.get("HOST", "127.0.0.1"), environ.get("PORT", 5000), debug=True)
