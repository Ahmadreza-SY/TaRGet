import re
import xml.etree.ElementTree as ET
import json
from config import Config
import traceback
from pathlib import Path


class JavaVersionDetector:
    ns = {"xmlns": "http://maven.apache.org/POM/4.0.0", "schemaLocation": "http://maven.apache.org/xsd/maven-4.0.0.xsd"}
    plugins = ["maven-compiler-plugin", "maven-enforcer-plugin"]
    plugin_config_paths = {
        "maven-compiler-plugin": [
            "./xmlns:configuration/xmlns:release",
            "./xmlns:configuration/xmlns:source",
            "./xmlns:configuration/xmlns:target",
            "./xmlns:executions/xmlns:execution/xmlns:configuration/xmlns:release",
            "./xmlns:executions/xmlns:execution/xmlns:configuration/xmlns:source",
            "./xmlns:executions/xmlns:execution/xmlns:configuration/xmlns:target",
            "./xmlns:configuration/xmlns:jdkToolchain/xmlns:version",
        ],
        "maven-enforcer-plugin": [
            "./xmlns:executions/xmlns:execution/xmlns:configuration/xmlns:rules/xmlns:requireJavaVersion/xmlns:version",
        ],
    }
    version_prop_names = [
        "java.version",
        "version.java",
        "javaVersion",
        "jdk.version",
        "jre.version",
        "compiler.level",
        "maven.compiler.release",
        "maven.compiler.testRelease",
        "maven.compiler.source",
        "maven.compiler.target",
    ]
    default_home = "11"

    def __init__(self, pom_path):
        self.java_homes = json.load(open(Config.get("java_homes_path")))
        self.root = None
        try:
            if pom_path.exists():
                self.root = ET.fromstring(pom_path.read_text().strip())
        except Exception:
            print(f"\nError in parsing {pom_path.absolute()}:\n", traceback.format_exc())

    def get_tag_value(self, tag):
        if tag is None or tag.text is None:
            return None
        match = re.compile(r"\$\{(.+)\}").search(tag.text)
        if not match:
            if is_float(tag.text):
                return tag.text
            match = re.compile(r"\[(.+),.*").search(tag.text)
            if match and is_float(match.group(1)):
                return match.group(1)
            return None
        prop = self.root.find(f"./xmlns:properties/xmlns:{match.group(1)}", JavaVersionDetector.ns)
        if prop is not None and is_float(prop.text):
            return prop.text
        return None

    def extract_versions(self, plugin, paths):
        versions = []
        for path in paths:
            found_tag = plugin.find(path, JavaVersionDetector.ns)
            tag_value = self.get_tag_value(found_tag)
            if tag_value is not None:
                versions.append(tag_value)
        return versions
    
    def detect_java_versions(self):
        if self.root is None:
            return []

        main_plugin_paths = [
            "./xmlns:build/xmlns:pluginManagement/xmlns:plugins/xmlns:plugin/[xmlns:artifactId='maven-compiler-plugin']",
            "./xmlns:build/xmlns:plugins/xmlns:plugin/[xmlns:artifactId='maven-compiler-plugin']"
        ]
        for main_path in main_plugin_paths:
            main_compiler_plugin = self.root.find(main_path, JavaVersionDetector.ns)
            if main_compiler_plugin is not None:
                main_versions = self.extract_versions(main_compiler_plugin, JavaVersionDetector.plugin_config_paths['maven-compiler-plugin'])
                if len(main_versions) > 0:
                    return main_versions[:1]

        versions = []
        for plugin in JavaVersionDetector.plugins:
            for found_plugin in self.root.findall(f".//xmlns:plugin/[xmlns:artifactId='{plugin}']", JavaVersionDetector.ns):
                found_versions = self.extract_versions(found_plugin, JavaVersionDetector.plugin_config_paths[plugin])
                versions.extend(found_versions)

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
        unique_versions = set([int(float(v.replace("1.", ""))) for v in java_versions])
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
