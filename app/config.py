import os

class Config:
    """Base configuration."""
    # Read SECRET_KEY from environment variable
    SECRET_KEY = os.environ.get('SECRET_KEY')
    DEBUG = False
    TESTING = False
    # Add any other base configs here

class DevelopmentConfig(Config):
    # DEBUG=True might be better for dev config
    DEBUG = True # Typically True for development

class TestingConfig(Config):
    TESTING = True
    # Example: SECRET_KEY = 'testing_key' # Can override if needed

class ProductionConfig(Config):
    # Inherits SECRET_KEY = os.environ.get('SECRET_KEY')
    # Inherits DEBUG=False, TESTING=False
    pass

config_by_name = dict(
    dev=DevelopmentConfig,
    test=TestingConfig,
    prod=ProductionConfig,
    default=DevelopmentConfig
) 