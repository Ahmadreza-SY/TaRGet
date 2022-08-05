class Config:
    __conf = {
        "repo": None,
        "output_path": None,
        "jparser_path": "assets/jparser.jar",
        "gh_api_token": None,
        "gh_api_base_url": "https://api.github.com",
        "gh_raw_base_url": "https://raw.githubusercontent.com",
        "gh_cache_path": "./api_cache",
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