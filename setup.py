from setuptools import setup, find_packages


setup(
    name='payment-terminal',
    url='https://github.com/bwhmather/python-payment-terminal',
    version='0.1.0',
    author='Ben Mather',
    author_email='bwhmather@bwhmather.com',
    license='BSD',
    description="Library for interacting with card readers",
    long_description=__doc__,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Hardware :: Hardware Drivers',
        'Topic :: System :: Hardware :: Card Readers',
        'Topic :: Office/Business :: Financial :: Point-Of-Sale',
        'Topic :: Payment',
    ],
    install_requires=[
    ],
    packages=find_packages(),
    package_data={
        '': ['*.*'],
    },
    test_suite='payment_terminal.tests.suite',
)
