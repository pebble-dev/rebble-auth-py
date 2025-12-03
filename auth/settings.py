from os import environ

domain_root = environ.get('DOMAIN_ROOT')
http_protocol = environ.get('HTTP_PROTOCOL', 'https')

config = {
    'SECRET_KEY': environ['SECRET_KEY'],
    'DOMAIN_ROOT': domain_root,
#    'SERVER_NAME': f"auth.{environ['DOMAIN_ROOT']}",
    'SQLALCHEMY_DATABASE_URI': environ['DATABASE_URL'],
    'REDIS_URL': environ['REDIS_URL'],
    'AUTH_GOOGLE': {
        'consumer_key': environ['GOOGLE_CONSUMER_KEY'],
        'consumer_secret': environ['GOOGLE_CONSUMER_SECRET'],
    },
    'AUTH_TWITTER': {
        'consumer_key': environ['TWITTER_CONSUMER_KEY'],
        'consumer_secret': environ['TWITTER_CONSUMER_SECRET'],
    },
    'AUTH_GITHUB': {
        'consumer_key': environ['GITHUB_CONSUMER_KEY'],
        'consumer_secret': environ['GITHUB_CONSUMER_SECRET'],
    },
    'AUTH_FACEBOOK': {
        'consumer_key': environ['FACEBOOK_CONSUMER_KEY'],
        'consumer_secret': environ['FACEBOOK_CONSUMER_SECRET'],
    },
    'STRIPE_SECRET_KEY': environ['STRIPE_SECRET_KEY'],
    'STRIPE_PUBLIC_KEY': environ['STRIPE_PUBLIC_KEY'],
    'STRIPE_WEBHOOK_KEY': environ.get('STRIPE_WEBHOOK_KEY'),
    'STRIPE_MONTHLY_PLAN': environ.get('STRIPE_MONTHLY_PLAN'),
    'STRIPE_ANNUAL_PLAN': environ.get('STRIPE_ANNUAL_PLAN'),
    'HONEYCOMB_KEY': environ.get('HONEYCOMB_KEY', None),
    'DISCOURSE_SECRET': environ.get('DISCOURSE_SECRET', None),
    'DISCOURSE_URL': environ.get('DISCOURSE_URL', f"{http_protocol}://forums.{domain_root}"),
    'RETURN_DEV_PORTAL': f'{http_protocol}://dev-portal.{domain_root}',
    'RETURN_DISCOURSE': environ.get('DISCOURSE_URL', f"{http_protocol}://forums.{domain_root}") + '/login'
}

if 'PEBBLE_CONSUMER_KEY' in environ and 'PEBBLE_CONSUMER_SECRET' in environ:
    config['AUTH_PEBBLE'] = {
        'consumer_key': environ['PEBBLE_CONSUMER_KEY'],
        'consumer_secret': environ['PEBBLE_CONSUMER_SECRET']
    }
