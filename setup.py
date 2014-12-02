from setuptools import setup, find_packages


setup(
    name='nm-payment',
    url='github.com/NewmanOnline/nm-payment',
    version='0.1.0',
    author='Newman Team',
    author_email='newman@newmanonline.org.uk',
    maintainer='',
    license='Commercial, All rights reserved.',
    description="",
    long_description=__doc__,
    install_requires=[
    ],
    packages=find_packages(),
    package_data={
        '': ['*.*'],
    },
    zip_safe=False,
    test_suite='nm_payment.tests.suite',
)
