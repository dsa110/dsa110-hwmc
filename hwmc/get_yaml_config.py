"""get_yaml_config returns a dictionary of configuration parameters from the requested file"""

import yaml


def read_yaml(fname):
    """Read a YAML formatted file.

    Args:
        fname (str): Name of YAML formatted file"

    Returns:
        (dict) on success, 'None' on error
    """

    with open(fname, 'r') as stream:
        try:
            return yaml.load(stream)
        except yaml.YAMLError:
            return None
