from os import environ

config = {
    'SECRET_KEY': environ['SECRET_KEY'],
    'SERVER_NAME': environ.get('SERVER_NAME'),
    'SQLALCHEMY_DATABASE_URI': environ['DATABASE_URL'],
    'AUTH_GOOGLE': {
        'consumer_key': environ['GOOGLE_CONSUMER_KEY'],
        'consumer_secret': environ['GOOGLE_CONSUMER_SECRET'],
    },
    'AUTH_TWITTER': {
        'consumer_key': environ['TWITTER_CONSUMER_KEY'],
        'consumer_secret': environ['TWITTER_CONSUMER_SECRET'],
    },
}
