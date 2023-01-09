import re


def auto_str(cls):
    def __str__(self):
        return "%s(%s)" % (type(self).__name__, ", ".join("%s=%s" % item for item in vars(self).items()))

    cls.__str__ = __str__
    return cls


def save_file(content, file_path):
    if file_path.exists():
        return
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)


def decompose_full_method_name(full_method_name):
    items = full_method_name.split(".")
    class_full_name = ".".join(items[:-1])
    class_name = items[-2]
    method_short_name = re.sub("\(.*\)", "", items[-1])
    return class_full_name, class_name, method_short_name


def is_test_class(file_content):
    junit_import = r"import\s+org\.junit\.(Test|\*|jupiter\.api\.(\*|Test))"
    test_annotation = r"@Test"
    return bool(re.search(junit_import, file_content)) and bool(re.search(test_annotation, file_content))
