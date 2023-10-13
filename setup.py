from setuptools import setup

setup(
    name='marzban-node-cli',
    version='0.1',
    py_modules=['marzban_node_cli'],
    install_requires=[
        'Click',
    ],
    entry_points='''
        [console_scripts]
        marzban-node=marzban_node_cli:cli
    ''',
)



