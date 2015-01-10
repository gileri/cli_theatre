from setuptools import setup, find_packages

setup(
    name='theatre',
    version='0.1.0',
    #packages=[''],
    #package_dir={'': 'theatre'},
    dependency_links = [
        'https://github.com/Diaoul/subliminal/tarball/master#egg=subliminal-0.8.0-dev',
    ],
    install_requires=[
        'guessit>=0.9',
        'pyxdg>=0.25',
        'pony>=0.6',
        'click>=3.3',
        'subliminal>=0.8.0-dev',
        'babelfish>=0.5.1',
    ],
    url='',
    license='',
    author='twix',
    author_email='',
    description='',
    entry_points={
        'console_scripts': [
            'theatre=theatre.theatre:cli',
        ],
    },
)
