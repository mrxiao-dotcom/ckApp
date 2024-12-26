from setuptools import setup, find_packages

setup(
    name="ckApp",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        'pywin32',
        'schedule',
        'flask',
        'flask-sqlalchemy',
        'flask-login',
        'flask-migrate'
    ]
) 