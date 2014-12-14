from setuptools import setup, find_packages

#from os import path
#here = path.abspath(path.dirname(__file__))
#with open(path.join(here, 'DESCRIPTION.rst'), encoding='utf-8') as f:
#    long_description = f.read()
setup(
    name='cli_theatre',
    version='0.1',
    description='Index and ease access to TV series',
    #long_description=long_description,
    url='https://github.com/gileri/cli_theatre',
    author='Éric Gillet',
    license='Apache',
    keywords='series cli library',
    packages=find_packages(),
    install_requires=open('requirements.txt').readlines(),
    extras_require = {
    },
    package_data={
        #'sample': ['package_data.dat'],
    },
    entry_points={
        'console_scripts': [
            'theatre=theatre.theatre:cli',
        ],
    },
)
