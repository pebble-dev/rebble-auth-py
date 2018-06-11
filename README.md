rebble-auth
===========

rebble-auth is a hybrid auth server: it acts enough like auth.getpebble.com
to be understood by clients that expect to be talking to that, while
also acting like a completely standard OAuth2 service for new clients.

rebble-auth only accepts authentication via other OAuth providers. It
allows you to connect a single account to multiple identity providers
and log in with any one of them.

rebble-auth can respond to two types of token request, which it
differentiates by the requested `scope`. If the scope includes
`pebble_token`, it will return a valid pebble token that it has
acquired from auth.getpebble.com, which it will also consider valid.
All such requests from all clients will be given the same token for
any given user (because we only have one). If the scope does _not_
include `pebble_token`, a random token will be generated and returned.
These tokens will be unique on each request. Refresh tokens are
supported for these clients, but all tokens are scheduled to expire in
ten years, so this is not a pressing concern.

The design and behaviour of this service is based on
[this document](https://docs.google.com/document/d/14cunTaDJ_C7Fz5DlS1NDWIhZosBMvnLrRfxDivE-inQ/edit#heading=h.cgvcuoyv8gjq).
The currently implemented behaviour is "stage 1", with parts of stage 2
where they do not conflict.

Setup
-----

### Configuration

The server expects to find its configuration in a proliferation of
environment variables (primarily for deployment reasons):

- `SECRET_KEY` should be some securely random string
- `SERVER_NAME` should be the address at which the server is accessed
  (but is optional)
- `DATABASE_URL` is a URL pointing at the database server. The model
  currently assumes that this is a postgres database because it uses
  vendor-specific ARRAY types.
- `GOOGLE_CONSUMER_KEY` and `GOOGLE_CONSUMER_SECRET` are used for
  Google auth.
- `TWITTER_CONSUMER_KEY` and `TWITTER_CONSUMER_SECRET` are used for
  Twitter auth.
- `GITHUB_CONSUMER_KEY` and `GITHUB_CONSUMER_SECRET` are used for
  Github auth.
- `FLASK_APP` isn't used by the app, but is needed if you want `flask`
  commands to work. Set it to `auth/__init__.py`.

Unfortunately, the server will currently not start without most of
these keys set.

### Database

rebble-auth uses [alembic](https://bitbucket.org/zzzeek/alembic) via
[flask-migrate](https://flask-migrate.readthedocs.io/en/latest/) for
migrations. To create or update the database state, run this command:

```
flask db upgrade
```

### Running the server

You can run the server in debug mode:

```
python serve_debug.py
```

This will bring up the server in single-threaded, synchronous mode
with debugging enabled. In production, `serve_gevent` is used instead,
which runs the server in asynchronous mode with debugging disabled.
