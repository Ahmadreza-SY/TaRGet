class Config:
    __conf = {
        "repo": None,
        "output_path": None,
        "java_home": None,
        "jparser_path": "assets/jparser.jar",
        "gh_clones_path": "./api_cache/clones",
    }

    __setters = ["repo", "output_path", "java_home", "jparser_path", "gh_clones_path"]

    @staticmethod
    def get(name):
        return Config.__conf[name]

    @staticmethod
    def set(name, value):
        if name in Config.__setters:
            Config.__conf[name] = value
        else:
            raise NameError(f"The config {name} is not allowed to set")
