"""Use Alembic to bring migrations up to date"""
# Python script that will apply the migrations up to head
# from https://stackoverflow.com/questions/42383400/python-packaging-alembic-migrations-with-setuptools
import alembic.config
import os

here = os.path.dirname(os.path.abspath(__file__))

alembic_args = ["-c", os.path.join(here, "alembic.ini"), "upgrade", "head"]


def main():
    alembic.config.main(argv=alembic_args)
