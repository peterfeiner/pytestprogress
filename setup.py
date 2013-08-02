from setuptools import setup

setup(
    name='pytest-progress',
    packages=['pytestprogress'],
    entry_points={
        'pytest11': ['pytestprogress = pytestprogress']
    },
    package_data={
        'pytestprogress': ['*.html'],
    },
)
