from setuptools import setup

setup(
    name='marzban-node',
    version='1.0.0',
    entry_points={
        'console_scripts': [
            'marzban-node = marzban_node_cli:cli',
        ],
    },
)



