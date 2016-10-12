from setuptools import setup

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except (IOError, ImportError):
    long_description = ''

version = '1.2.1'

setup(
    name='docker-compose-swarm-mode',
    py_modules=['docker_compose_swarm_mode'],
    version=version,
    author='Dmitry Drozdov',
    url='https://github.com/ddrozdov/docker-compose-swarm-mode',
    download_url='https://github.com/ddrozdov/docker-compose-swarm-mode/tarball/' + version,
    description='Drop in replacement for docker-compose that works with swarm mode introduced in Docker 1.12.',
    long_description=long_description,
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
