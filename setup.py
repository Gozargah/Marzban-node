from setuptools import setup, find_packages

setup(
    name='marzban-node',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'marzban-node = marzban-node.marzban_node_cli:cli',
        ],
    },
)
