package edu.ahrsy.jparser.graph.dto;

public class CGNodeDTO {
  Integer id;
  String name;
  String path;
  Integer depth;

  public CGNodeDTO(Integer id, String name, String path, Integer depth) {
    this.id = id;
    this.name = name;
    this.path = path;
    this.depth = depth;
  }
}
