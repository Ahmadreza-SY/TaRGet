class Config:
    __conf = {
        "repo": None,
        "output_path": None,
        "jparser_path": "assets/jparser.jar",
        "gh_cache_path": "./api_cache",
        "gh_clones_path": "./api_cache/clones",
    }

    __setters = ["repo", "output_path", "gh_api_token"]

    @staticmethod
    def get(name):
        return Config.__conf[name]

    @staticmethod
    def set(name, value):
        if name in Config.__setters:
            Config.__conf[name] = value
        else:
            raise NameError(f"The config {name} is not allowed to set")