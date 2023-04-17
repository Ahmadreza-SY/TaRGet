import xml.etree.ElementTree as ET
from pathlib import Path
import xml.dom.minidom as minidom
import os


def extract_covered_lines(packages, covered_lines):
    for pck in packages:
        pck_name = pck.attrib["name"]
        for src in pck.findall("sourcefile"):
            src_name = src.attrib["name"]
            for line in src.findall("line"):
                line_no = int(line.attrib["nr"])
                covered_cnt = int(line.attrib["ci"]) + int(line.attrib["cb"])
                if covered_cnt > 0:
                    src_path = str(Path(pck_name) / src_name)
                    covered_lines.setdefault(src_path, [])
                    covered_lines[src_path].append(line_no)


def parse_jacoco_report(report_path, project_path):
    covered_lines = {}
    report_file = report_path / "jacoco/jacoco.xml"
    if not report_file.exists():
        return {}
    main_tree = ET.parse(str(report_file))
    extract_covered_lines(main_tree.getroot().findall("package"), covered_lines)

    agg_file = report_path / "jacoco-aggregate/jacoco.xml"
    if agg_file.exists():
        agg_tree = ET.parse(str(agg_file))
        for group in agg_tree.getroot().findall("group"):
            extract_covered_lines(group.findall("package"), covered_lines)

    # Get project level paths
    final_covered_lines = {}
    for k, v in covered_lines.items():
        src_path = next(project_path.glob(f"**/{k}"), None)
        if src_path is None:
            continue
        src_path = src_path.relative_to(project_path)
        final_covered_lines[str(src_path)] = v

    return final_covered_lines


ns = {"xmlns": "http://maven.apache.org/POM/4.0.0", "schemaLocation": "http://maven.apache.org/xsd/maven-4.0.0.xsd"}


def add_jacoco_plugin(root):
    new_jacoco_xml = '<plugin xmlns="http://maven.apache.org/POM/4.0.0"><groupId>org.jacoco</groupId><artifactId>jacoco-maven-plugin</artifactId><version>0.8.8</version><configuration><excludes>**/*.jar</excludes></configuration><executions><execution><goals><goal>prepare-agent</goal></goals></execution><execution><id>report</id><goals><goal>report</goal></goals><phase>test</phase></execution><execution><id>report-aggregate</id><goals><goal>report-aggregate</goal></goals><phase>test</phase></execution></executions></plugin>'

    plugins = root.find("./xmlns:build/xmlns:plugins", ns)
    jacoco_plugins = plugins.findall("./xmlns:plugin/[xmlns:artifactId='jacoco-maven-plugin']", ns)
    for jacoco_plugin in jacoco_plugins:
        plugins.remove(jacoco_plugin)

    new_jacoco_plugin = ET.fromstring(new_jacoco_xml)
    plugins.append(new_jacoco_plugin)


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

    add_jacoco_plugin(root)
    update_surefire_config(root)
    save_pom(root, pom_path)
    return pom_path
