package edu.ahrsy.jparser.utils;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.opencsv.bean.CsvToBeanBuilder;
import com.opencsv.bean.StatefulBeanToCsv;
import com.opencsv.bean.StatefulBeanToCsvBuilder;
import com.opencsv.exceptions.CsvDataTypeMismatchException;
import com.opencsv.exceptions.CsvRequiredFieldEmptyException;

import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

public class IOUtils {
  public static void saveFile(Path filePath, String content) {
    try {
      Files.createDirectories(filePath.getParent());
      Files.write(filePath, content.getBytes());
    } catch (IOException e) {
      throw new RuntimeException(e);
    }
  }

  public static <T> void toCsv(List<T> rows, String outputFile) {
    try (Writer writer = new FileWriter(outputFile)) {
      StatefulBeanToCsv<T> beanToCsv = new StatefulBeanToCsvBuilder<T>(writer).build();
      beanToCsv.write(rows);
    } catch (IOException | CsvRequiredFieldEmptyException | CsvDataTypeMismatchException e) {
      throw new RuntimeException(e);
    }
  }

  public static <T> List<T> readCsv(String inputFile, Class<T> type) {
    try {
      return new CsvToBeanBuilder<T>(new FileReader(inputFile))
              .withType(type)
              .build()
              .parse();
    } catch (FileNotFoundException e) {
      throw new RuntimeException(e);
    }
  }

  public static String readFile(Path path) {
    try {
      return Files.readString(path);
    } catch (IOException e) {
      throw new RuntimeException(e);
    }
  }

  public static Gson createGsonInstance() {
    return new GsonBuilder().disableHtmlEscaping().create();
  }
}
