"""Setup pour le package partagé des services Medpost"""

from setuptools import setup, find_packages

setup(
    name="medpost-shared",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "sqlalchemy>=2.0.0",
        "python-dotenv>=1.0.0",
    ],
    author="Medpost",
    description="Modules partagés entre les services Medpost",
)
