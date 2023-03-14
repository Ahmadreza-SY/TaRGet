import os
import sys

class Config:
    __conf = {
        "repo": None,
        "output_path": None,
        "repo_path": None,
        "java_home": None,
        "jparser_path": os.path.join(os.path.dirname(sys.path[0]), "repair-collection/assets/jparser.jar"),
    }

    __setters = ["repo", "output_path", "repo_path", "java_home", "jparser_path"]

    @staticmethod
    def get(name):
        return Config.__conf[name]

    @staticmethod
    def set(name, value):
        if name in Config.__setters:
            Config.__conf[name] = value
        else:
            raise NameError(f"The config {name} is not allowed to set")
