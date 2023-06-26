import re
import xml.etree.ElementTree as ET
import json
from config import Config
import traceback

class JavaVersionDetector:
    ns = {"xmlns": "http://maven.apache.org/POM/4.0.0", "schemaLocation": "http://maven.apache.org/xsd/maven-4.0.0.xsd"}
    config_paths = ["./xmlns:configuration", "./xmlns:executions/xmlns:execution/xmlns:configuration"]
    version_tags = ["source", "target", "release"]
    version_prop_names = [
        "java.version",
        "javaVersion",
        "jdk.version",
        "jre.version",
        "compiler.level",
        "maven.compiler.release",
        "maven.compiler.source",
        "maven.compiler.target",
    ]
    default_home = "11"

    def __init__(self, pom_path):
        self.java_homes = json.load(open(Config.get("java_homes_path")))
        try:
            self.root = ET.fromstring(pom_path.read_text().strip())
        except Exception:
            print(f"Error in parsing {pom_path}:", traceback.format_exc())
            self.root = None

    def get_tag_value(self, tag):
        if tag is None or tag.text is None:
            return None
        match = re.compile(r"\$\{(.+)\}").search(tag.text)
        if not match:
            return tag.text if is_float(tag.text) else None
        prop = self.root.find(f"./xmlns:properties/xmlns:{match.group(1)}", JavaVersionDetector.ns)
        if prop is not None and is_float(prop.text):
            return prop.text
        return None

    def detect_java_versions(self):
        if self.root is None:
            return []
        compiler_plugins = self.root.findall(
            ".//xmlns:plugin/[xmlns:artifactId='maven-compiler-plugin']", JavaVersionDetector.ns
        )
        versions = []
        for compiler_plugin in compiler_plugins:
            for config_path in JavaVersionDetector.config_paths:
                for version_tag in JavaVersionDetector.version_tags:
                    for found_tag in compiler_plugin.findall(f"{config_path}/xmlns:{version_tag}", JavaVersionDetector.ns):
                        tag_value = self.get_tag_value(found_tag)
                        if tag_value is not None:
                            versions.append(tag_value)

        if len(versions) == 0:
            for prop_name in JavaVersionDetector.version_prop_names:
                prop = self.root.find(f"./xmlns:properties/xmlns:{prop_name}", JavaVersionDetector.ns)
                if prop is not None and is_float(prop.text):
                    versions.append((prop.text))

        return [v.strip() for v in versions]

    def get_java_home(self):
        java_versions = self.detect_java_versions()
        if len(java_versions) == 0:
            return self.java_homes[JavaVersionDetector.default_home]
        unique_versions = set([int(v.replace("1.", "")) for v in java_versions])
        max_version = max(unique_versions)
        if str(max_version) in self.java_homes:
            return self.java_homes[str(max_version)]
        available_homes = sorted([int(j) for j in self.java_homes.keys()])
        for h in available_homes:
            if h >= max_version:
                return self.java_homes[str(h)]
        return self.java_homes[JavaVersionDetector.default_home]


def is_float(string):
    try:
        float(string.strip())
        return True
    except ValueError:
        return False
