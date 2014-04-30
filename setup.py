from distutils.core import setup

setup(
    name='pybigip',
    version='0.3.1',
    description='Library for managing F5 bigips',
    author='Richard Marshall',
    author_email='richard.marshall@ask.com',
    url='http://github.com/askcom/pybigip',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: Apache Software License',
        'Intended Audience :: Developers',
    ],
    packages=[
        'pybigip',
    ],
    install_requires=[
        'bigsuds',
    ],
)
