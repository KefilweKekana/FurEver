from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="kennel_management",
    version="1.1.0",
    description="SPCA Kennel Management System for ERPNext v16",
    author="SPCA",
    author_email="admin@spca.org",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
