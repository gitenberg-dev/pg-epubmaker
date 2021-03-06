#
# pypi epubmaker setup
#

from setuptools import setup
from setup_inc import *

setup (
    name = 'epubmaker',
    version = VERSION,
    install_requires = install_requires,
    package_dir  = package_dir,
    packages     = pypi_packages,
    py_modules   = pypi_py_modules,
    package_data = pypi_package_data,
    scripts      = pypi_scripts,
    data_files   = pypi_data_files,

    # metadata for upload to PyPI

    author = author,
    author_email = author_email,
    description = description,
    long_description = long_description,
    license = license,
    keywords = keywords,
    url = url,
    classifiers = classifiers,
    platforms = platforms,
)
