import org.eclipse.jdt.core.dom.*;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Collectors;

public class Main {
    private static String readFile(String path) {
        try {
            return String.join(System.lineSeparator(), Files.readAllLines(Path.of(path)));
        } catch (IOException e) {
            e.printStackTrace();
            return null;
        }
    }

    private static void saveFile(Path filePath, String content) {
        try {
            Files.createDirectories(filePath.getParent());
            Files.write(filePath, content.getBytes());
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }

    public static void main(String[] args) {
        String tcPath = args[0];
        String outputPath = args[1];
        String code = readFile(tcPath);
        ASTParser parser = ASTParser.newParser(AST.JLS17);
        if (code == null) {
            System.out.println("Input source code is null!");
            return;
        }
        parser.setSource(code.toCharArray());
        parser.setKind(ASTParser.K_COMPILATION_UNIT);
        parser.setResolveBindings(true);
        parser.setEnvironment(null, new String[]{""}, new String[]{"UTF-8"}, true);
        parser.setUnitName("");
        CompilationUnit cu = (CompilationUnit) parser.createAST(null);
        cu.accept(new ASTVisitor() {

            @Override
            public boolean visit(MethodDeclaration node) {
                List<String> modifiers = ((List<ASTNode>) node.modifiers()).stream().map(ASTNode::toString).collect(Collectors.toList());
                if(modifiers.contains("@Test")) {
                    List<SingleVariableDeclaration> params = node.parameters();
                    String methodSignature = String.format(
                            "%s.%s(%s)",
                            ((TypeDeclaration) node.getParent()).getName().toString(),
                            node.getName().toString(),
                            params.stream().map(p -> p.getType().toString()).collect(Collectors.joining(","))
                    );
                    String methodCode = node.toString();
                    saveFile(Path.of(outputPath, methodSignature), methodCode);
                }
                return super.visit(node);
            }
        });
    }
}
