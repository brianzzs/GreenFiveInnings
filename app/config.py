import os

class Config:
    """Base configuration."""
    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    TESTING = False

class ProductionConfig(Config):
    pass # Inherits DEBUG=False, TESTING=False from Config

config_by_name = dict(
    dev=DevelopmentConfig,
    test=TestingConfig,
    prod=ProductionConfig,
    default=DevelopmentConfig
) 