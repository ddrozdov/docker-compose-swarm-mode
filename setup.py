import pypandoc
from setuptools import setup

setup(
    name='docker-compose-swarm-mode',
    py_modules=['docker_compose_swarm_mode'],
    version='1.1.0',
    author='Dmitry Drozdov',
    url='https://github.com/ddrozdov/docker-compose-swarm-mode',
    download_url='https://github.com/ddrozdov/docker-compose-swarm-mode/tarball/1.1.0',
    description='Drop in replacement for docker-compose that works with swarm mode introduced in Docker 1.12.',
    long_description=pypandoc.convert('README.md', 'rst'),
    license='MIT',
    install_requires=['yodl>=1.0.0'],
    entry_points={
        'console_scripts': ['docker-compose-swarm-mode=docker_compose_swarm_mode:main']
    },
    keywords=['docker', 'docker-compose', 'swarm'],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4'
    ],
)
