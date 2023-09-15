from setuptools import setup

setup(
    name="marzban-node-cli",
    version="0.1",
    py_modules=["marzban_node_cli"],
    install_requires=[
        "click",
    ],
    entry_points={
        "console_scripts": [
            "marzban-node=marzban_node_cli:install_marzban_node",
        ],
    },
)


