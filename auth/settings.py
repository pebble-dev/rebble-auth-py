from os import environ

config = {
    'SECRET_KEY': environ['SECRET_KEY'],
    'DOMAIN_ROOT': environ['DOMAIN_ROOT'],
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
    'LIGHTSTEP_KEY': environ.get('LIGHTSTEP_KEY', None),
}

if 'PEBBLE_CONSUMER_KEY' in environ and 'PEBBLE_CONSUMER_SECRET' in environ:
    config['AUTH_PEBBLE'] = {
        'consumer_key': environ['PEBBLE_CONSUMER_KEY'],
        'consumer_secret': environ['PEBBLE_CONSUMER_SECRET']
    }
