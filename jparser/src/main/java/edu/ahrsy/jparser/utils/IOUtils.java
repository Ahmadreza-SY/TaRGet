package edu.ahrsy.jparser.utils;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.opencsv.bean.CsvToBeanBuilder;
import com.opencsv.bean.StatefulBeanToCsv;
import com.opencsv.bean.StatefulBeanToCsvBuilder;
import com.opencsv.exceptions.CsvDataTypeMismatchException;
import com.opencsv.exceptions.CsvRequiredFieldEmptyException;
import sun.misc.Unsafe;

import java.io.*;
import java.lang.reflect.Field;
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
      return new CsvToBeanBuilder<T>(new FileReader(inputFile)).withType(type).build().parse();
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

  public static void disableReflectionWarning() {
    try {
      Field theUnsafe = Unsafe.class.getDeclaredField("theUnsafe");
      theUnsafe.setAccessible(true);
      Unsafe u = (Unsafe) theUnsafe.get(null);

      Class<?> cls = Class.forName("jdk.internal.module.IllegalAccessLogger");
      Field logger = cls.getDeclaredField("logger");
      u.putObjectVolatile(cls, u.staticFieldOffset(logger), null);
    } catch (Exception ignored) {
    }
  }

  public static int countLines(File file) {
    int lines = 0;
    try {
      BufferedReader reader = new BufferedReader(new FileReader(file));
      while (reader.readLine() != null) lines++;
      reader.close();
    } catch (IOException e) {
      throw new RuntimeException(e);
    }
    return lines;
  }
}
