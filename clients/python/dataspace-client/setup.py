from setuptools import setup, find_packages

setup(
    name='dataspace-client',
    version='0.1.3.16',
    author='Anton Gustafsson',
    author_email='anton.gustafsson@ri.se',
    description='Client for a publish/subscribe dataspace (MQTT-based) with convenience helpers.',
    packages=find_packages(),
    python_requires='>=3.8',
    install_requires=[
        'paho-mqtt>=1.5.0',
        'pytz',
        # OBS: inga tunga binärer här
    ],
    extras_require={
        # Installera dataframe-stöd separat
        'dataframe': [
            'pandas>=2.2.2,<3.0',
        ],
        # 3D/visnings-stöd separat (kan dra in numpy)
        'vis': [
            'trimesh>=4.4.9',
        ],
        # allt
        'all': [
            'pandas>=2.2.2,<3.0',
            'trimesh>=4.4.9',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
