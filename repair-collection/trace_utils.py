import xml.etree.ElementTree as ET
from pathlib import Path
import xml.dom.minidom as minidom
import os
import json
import pandas as pd


def parse_trace(trace_path, project_path):
    project_path = project_path.absolute()
    covered_lines = {}
    trace_file = trace_path / "trace.json"
    classes_file = trace_path / "classes.txt"
    if not trace_file.exists():
        return {}

    trace = json.load(open(str(trace_file)))
    classes = pd.read_csv(classes_file)
    src_module_path = dict(
        zip(
            classes["ClassName"].apply(lambda cn: cn.split("$")[0] + ".java"),
            classes["LoadedFrom"].apply(lambda lf: Path(lf.replace("file:", "")).parent.parent),
        )
    )
    line_events = [event for event in trace["events"] if event["event"] == "LINE_NUMBER"]
    for line_event in line_events:
        src_path = line_event["cname"].split("$")[0] + ".java"
        covered_lines.setdefault(src_path, [])
        covered_lines[src_path].append(line_event["line"])

    # Get project level paths
    final_covered_lines = {}
    for k, v in covered_lines.items():
        module_path = src_module_path[k]
        common_path = os.path.commonpath([str(module_path), str(project_path)])
        if common_path != str(project_path):
            continue
        src_path = next(module_path.glob(f"**/{k}"), None)
        if src_path is None:
            # ignoring auto-generated src files by Antlr
            if "/autogen/" not in k:
                print(f"Covered source file not found: {k} {module_path}")
            continue
        src_path = src_path.relative_to(project_path)
        final_covered_lines[str(src_path)] = v

    return final_covered_lines


ns = {"xmlns": "http://maven.apache.org/POM/4.0.0", "schemaLocation": "http://maven.apache.org/xsd/maven-4.0.0.xsd"}


def update_surefire_config(root):
    surefire_plugins = root.findall(".//xmlns:plugin/[xmlns:artifactId='maven-surefire-plugin']", ns)
    for surefire_plugin in surefire_plugins:
        argline = surefire_plugin.find("./xmlns:configuration/xmlns:argLine", ns)
        if argline is not None and "${argLine}" not in argline.text:
            argline.text = "${argLine} " + argline.text


def save_pom(root, output_path):
    ET.register_namespace("", ns["xmlns"])
    xml_string = ET.tostring(root, xml_declaration=True, encoding="utf-8", method="xml")
    pretty_xml = minidom.parseString(xml_string).toprettyxml(indent="    ")
    pretty_xml = os.linesep.join([s for s in pretty_xml.splitlines() if s.strip()])
    with open(str(output_path), "w") as f:
        f.write(pretty_xml)


def configure_pom(project_path):
    pom_path = project_path / "pom.xml"
    if not pom_path.exists():
        return None
    pom_tree = ET.parse(str(pom_path))
    root = pom_tree.getroot()

    update_surefire_config(root)
    save_pom(root, pom_path)
    return pom_path
