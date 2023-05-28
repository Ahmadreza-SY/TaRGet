class Config:
    __conf = {
        "repo": None,
        "output_path": None,
        "repo_path": None,
        "java_home": None,
        "jparser_path": "assets/jparser.jar",
        "selogger_path": "assets/selogger.jar",
        "m2_path": None,
    }

    __setters = ["repo", "output_path", "repo_path", "java_home", "jparser_path", "selogger_path", "m2_path"]

    @staticmethod
    def get(name):
        return Config.__conf[name]

    @staticmethod
    def set(name, value):
        if name in Config.__setters:
            Config.__conf[name] = value
        else:
            raise NameError(f"The config {name} is not allowed to set")
