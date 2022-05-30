import org.eclipse.jdt.core.dom.AST;
import org.eclipse.jdt.core.dom.ASTParser;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

public class Main {
  private static String readFile(String path) {
    try {
      return String.join(System.lineSeparator(), Files.readAllLines(Path.of(path)));
    } catch (IOException e) {
      e.printStackTrace();
      return null;
    }
  }

  public static void main(String[] args) {
    String tcPath = "/home/ahmad/workspace/TCP-CI-backup/feature-extraction/datasets/Angel-ML@angel/angel/angel-ps/core/src/test/java/com/tencent/angel/master/AppTest.java";
    String code = readFile(tcPath);
    System.out.println(code);
//    ASTParser parser = ASTParser.newParser(AST.JLS17);
//    parser.setSource(code.get().toCharArray());
//    parser.setKind(ASTParser.K_COMPILATION_UNIT);
//    parser.setResolveBindings(true);
//    parser.setEnvironment(null, new String[] {""}, new String[] {"UTF-8"}, true);
//    parser.setUnitName("");
  }
}
